"""Task execution helpers for the Strands-based CLI."""

from __future__ import annotations

import asyncio
import time
import json
import re
import sys
from pathlib import Path
from collections.abc import Callable
from typing import Any, Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from .config import COLORS, console
from .input import parse_file_mentions
from .skills.load import list_skills
from .skills.paths import get_project_skills_dir, get_user_skills_dir
from .ui import render_todos_panel, toast

_PRINTED_TOOL_PARAMS_IDS: set[str] = set()
_PRINTED_TOOL_PARAMS_KEYS: set[str] = set()
_LAST_TOOL_REQUEST: dict[str, float] = {}
_LAST_TOOL_NAME_REQUEST: dict[str, tuple[float, str]] = {}
_LAST_TOOL_APPROVAL: dict[str, float] = {}


def _normalize_tool_input(tool_input: Any) -> str:
    """Normalize tool input for stable dedupe keys."""
    if tool_input is None:
        return ""
    if isinstance(tool_input, (dict, list)):
        try:
            return json.dumps(tool_input, sort_keys=True, default=str)
        except Exception:
            return str(tool_input)
    if isinstance(tool_input, str):
        s = tool_input.strip()
        if not s:
            return ""
        if s.startswith("{") or s.startswith("["):
            try:
                loaded = json.loads(s)
                return json.dumps(loaded, sort_keys=True, default=str)
            except Exception:
                return s
        return s
    return str(tool_input)


# Debug helpers removed after investigation


def looks_like_markdown(text: str) -> bool:
    """Check if text looks like markdown format.
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains markdown-like patterns
    """
    return any(token in text for token in ("```", "# ", "- ", "* ", "`"))


def extract_todos_from_text(text: str) -> list[dict] | None:
    """Extract todos list from agent output text.
    
    Looks for JSON blocks containing "todos" array in the text.
    Handles various formats including code blocks with extra whitespace.
    
    Args:
        text: Agent output text that may contain JSON todos
        
    Returns:
        List of todo dictionaries if found, None otherwise
    """
    # Try to find JSON block with todos
    # Pattern 1: ```json code block (most common)
    # Pattern 2: ``` generic code block
    # Pattern 3: Inline JSON (less common, more fragile)
    
    # First, try to extract from code blocks (more reliable)
    code_block_patterns = [
        r'```json\s*(\{[\s\S]*?"todos"[\s\S]*?\})\s*```',  # JSON code block
        r'```\s*(\{[\s\S]*?"todos"[\s\S]*?\})\s*```',  # Generic code block
    ]
    
    for pattern in code_block_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                # Clean up whitespace
                cleaned = re.sub(r'\n\s*\n', '\n', match)  # Remove extra blank lines
                data = json.loads(cleaned)
                if "todos" in data and isinstance(data["todos"], list):
                    return data["todos"]
            except json.JSONDecodeError:
                continue
    
    # Fallback: try inline JSON (less reliable due to greedy matching)
    inline_pattern = r'(\{[^{}]*?"todos"[^{}]*?\})'
    matches = re.findall(inline_pattern, text, re.DOTALL | re.IGNORECASE)
    for match in matches:
        try:
            data = json.loads(match)
            if "todos" in data and isinstance(data["todos"], list):
                return data["todos"]
        except json.JSONDecodeError:
            continue
    
    return None


def render_agent_output(raw: str, title: str = "Agent") -> Panel:
    """Render agent output with automatic markdown/ANSI detection.
    
    Args:
        raw: Raw output text from agent
        title: Panel title
        
    Returns:
        Panel with rendered content
    """
    if looks_like_markdown(raw):
        body = Markdown(raw)
    else:
        body = Text.from_ansi(raw) if "\x1b[" in raw else Text(raw)
        body.overflow = "fold"
    return Panel(body, title=title, border_style="cyan", box=box.ROUNDED, padding=(1, 2))


def _assemble_prompt(user_input: str) -> str:
    prompt_text, mentioned_files = parse_file_mentions(user_input)

    if not mentioned_files:
        return prompt_text

    context_parts = [prompt_text, "\n\n## Referenced Files\n"]
    MAX_FILE_CHARS = 20000
    TRUNCATE_HEAD = 10000
    TRUNCATE_TAIL = 10000

    for file_path in mentioned_files:
        try:
            # Check file size before reading to avoid reading massive files into memory
            if file_path.stat().st_size > 10 * 1024 * 1024: # 10MB limit
                context_parts.append(
                    f"\n### {file_path.name}\n[File too large to read (size: {file_path.stat().st_size} bytes). Please use tools to read specific parts.]"
                )
                console.print(f"[yellow]Warning: File {file_path.name} is too large (10MB+), skipped content injection.[/yellow]")
                continue

            content = file_path.read_text()
            if len(content) > MAX_FILE_CHARS:
                original_len = len(content)
                content = (
                    content[:TRUNCATE_HEAD]
                    + f"\n... (file truncated, {original_len - MAX_FILE_CHARS} chars hidden) ...\n"
                    + content[-TRUNCATE_TAIL:]
                )
                console.print(f"[yellow]Warning: File {file_path.name} truncated (kept first/last {TRUNCATE_HEAD//1000}k chars).[/yellow]")
            
            context_parts.append(
                f"\n### {file_path.name}\nPath: `{file_path}`\n```\n{content}\n```"
            )
        except Exception as exc:  # noqa: BLE001
            context_parts.append(f"\n### {file_path.name}\n[Error reading file: {exc}]")
            console.print(f"[red]Error reading {file_path.name}: {exc}[/red]")

    return "\n".join(context_parts)


def _extract_skill_prefix(user_input: str, assistant_id: str | None) -> tuple[str | None, str]:
    match = re.match(r"^\s*\$(?P<name>[a-zA-Z0-9_-]+)\b\s*(?P<rest>.*)$", user_input, re.DOTALL)
    if not match:
        return None, user_input

    skill_name = match.group("name")
    rest = match.group("rest").strip()

    skills = list_skills(
        user_skills_dir=get_user_skills_dir(assistant_id or "agent"),
        project_skills_dir=get_project_skills_dir(),
    )
    skill = next((s for s in skills if s["name"] == skill_name), None)
    if not skill:
        toast(f"Unknown skill: {skill_name}", kind="warning")
        return None, rest or user_input

    skill_path = Path(skill["path"])
    try:
        skill_content = skill_path.read_text()
    except OSError as exc:
        toast(f"Failed to read skill: {skill_path} ({exc})", kind="warning")
        return None, rest or user_input

    skill_prompt = (
        "## Selected Skill\n"
        f"Name: {skill_name}\n"
        f"Source: {skill['source']}\n"
        f"Path: {skill_path}\n\n"
        "<skill_instructions>\n"
        f"{skill_content}\n"
        "</skill_instructions>\n"
    )
    return skill_prompt, rest or ""


def _build_skills_discovery_prompt(assistant_id: str | None) -> str | None:
    skills = list_skills(
        user_skills_dir=get_user_skills_dir(assistant_id or "agent"),
        project_skills_dir=get_project_skills_dir(),
    )
    if not skills:
        return None

    lines = [
        "## Skills (Discovery)",
        "If a skill is relevant, read its SKILL.md before responding.",
        "",
        "Available skills:",
    ]
    for skill in skills:
        lines.append(
            f"- {skill['name']}: {skill['description']} (path: {skill['path']})"
        )

    return "\n".join(lines)


def _stringify_response(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("output_text", "content", "text", "message"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, list):
                joined = "\n".join(str(item) for item in value)
                if joined.strip():
                    return joined
        return str(response)
    if isinstance(response, Iterable) and not isinstance(response, (bytes, bytearray)):
        joined = "\n".join(_stringify_response(item) for item in response)
        return joined
    return str(response)


def _render_tool_event(event: dict) -> None:
    if "current_tool_use" in event and event["current_tool_use"].get("name"):
        tool_name = event["current_tool_use"]["name"]
        data=_stringify_response(event["current_tool_use"])
        console.print()
        console.print(f"🔧 Using tool: {tool_name}")
        console.print(
            Panel(
                _stringify_response(data),
                title="Tool Update",
                border_style=COLORS["tool"],
            )
        )
    # ツールイベント表示後も即座にフラッシュして、表示を遅延させない
    sys.stdout.flush()

def _render_model_delta(event: dict, buffer: list[str], session_state=None) -> bool:
    """Render model delta and return True if content was rendered."""
    # Strands Agentのドキュメントによると、テキストチャンクは 'data' フィールドに直接ある
    # 'delta' も存在するが、'data' が推奨される
    data = event.get("data")
    if isinstance(data, str) and data:
        # テキストがストリーミングされ始めたら、ステータスを即座に停止
        if session_state:
            session_state.clear_status()
        buffer.append(data)
        console.print(data, style=COLORS["agent"], end="")
        #console.print(Markdown(data.replace("\n", "")), style=COLORS["agent"],end="")
        # ストリーミング時のリアルタイム表示を改善するため、出力を即座にフラッシュ
        sys.stdout.flush()
        return True
    
    # 後方互換性のため、delta もチェック
    delta = event.get("delta")
    if isinstance(delta, str) and delta:
        # テキストがストリーミングされ始めたら、ステータスを即座に停止
        if session_state:
            session_state.clear_status()
        buffer.append(delta)
        console.print(delta, style=COLORS["tool"], end="")
        #console.print(Markdown(delta), style=COLORS["agent"],end="")
        sys.stdout.flush()
        return True
    
    return False


def _extract_final_response(event: dict) -> str:
    """Extract final response from event."""
    # Strands Agentのドキュメントによると、最終結果は 'result' フィールドにある
    result = event.get("result")
    if result is not None:
        # AgentResultオブジェクトの場合、output_textやcontentを取得
        if hasattr(result, "output_text"):
            return str(result.output_text)
        if hasattr(result, "content"):
            return _stringify_response(result.content)
        if isinstance(result, dict):
            return _stringify_response(result)
        return _stringify_response(result)
    
    # 後方互換性のため、assistant_response もチェック
    assistant_event = event.get("assistant_response")
    if isinstance(assistant_event, dict):
        return _stringify_response(assistant_event)
    return ""

def _render_lifecycle_event(event: dict, debug_mode: bool = False) -> None:
    """Render lifecycle events (for debugging).
    
    Args:
        event: Event dictionary from agent stream
        debug_mode: Enable debug output for lifecycle events
    """
    if not debug_mode:
        return
    
    # Track event loop lifecycle
    if event.get("init_event_loop", False):
        console.print("[dim]🔄 Event loop initialized[/dim]")
    elif event.get("start_event_loop", False):
        console.print("[dim]▶️ Event loop cycle starting[/dim]")
    elif "message" in event:
        role = event["message"].get("role", "unknown")
        console.print(f"[dim]📬 New message created: {role}[/dim]")
    elif event.get("complete", False):
        console.print("[dim]✅ Cycle completed[/dim]")
    elif event.get("force_stop", False):
        reason = event.get("force_stop_reason", "unknown reason")
        console.print(f"[yellow]🛑 Event loop force-stopped: {reason}[/yellow]")
        sys.stdout.flush()


def _render_tool_stream_event(event: dict, session_state=None) -> None:
    """Render tool streaming event.
    
    Args:
        event: Event dictionary from agent stream
    """
    tool_stream_event = event.get("tool_stream_event")
    if not tool_stream_event:
        return
    
    tool_use = tool_stream_event.get("tool_use", {})
    tool_name = tool_use.get("name", "unknown")
    data = tool_stream_event.get("data")
    
    if data:
        # ステータス表示があると同じ行を上書きしやすいので一時停止する
        restore_tool_status = None
        if session_state and session_state.tool_status:
            restore_tool_status = session_state.tool_status
            session_state.clear_status()
        # ツールからのストリーミングデータを表示
        console.print(
            f"[dim]🔧 Tool '{tool_name}' streaming: {data}[/dim]",
        )
        sys.stdout.flush()
        if restore_tool_status:
            session_state.set_tool_status(restore_tool_status)

def _ask_tool_approval_sync(tool_name: str, tool_data: dict) -> bool:
    """Ask user for approval before executing a tool (synchronous version).
    
    Uses Rich's Confirm prompt with Panel display for better UX.
    Handles Live display conflicts by pausing if active.
    
    Args:
        tool_name: Name of the tool to be executed
        tool_data: Tool execution data/arguments
        
    Returns:
        True if approved, False if rejected
    """
    from contextlib import nullcontext
    
    from rich.prompt import Confirm
    
    from .config import current_live
    
    # Live表示を一時停止（存在する場合）
    cm = (
        current_live.pause() if current_live and hasattr(current_live, "pause") else nullcontext()
    )
    
    with cm:
        console.print()
        body = Text(f"Tool execution requested: {tool_name}", style="bold yellow")
        console.print(Panel(body, border_style="yellow", box=box.ROUNDED, padding=(1, 2)))
        
        try:
            return Confirm.ask("Execute this tool?", default=False)
        except (EOFError, KeyboardInterrupt):
            return False


async def _ask_tool_approval_async(tool_name: str, tool_data: dict) -> bool:
    """Ask user for approval before executing a tool (asynchronous version).
    
    Args:
        tool_name: Name of the tool to be executed
        tool_data: Tool execution data/arguments
        
    Returns:
        True if approved, False if rejected
    """
    console.print()
    console.print(f"[yellow]🔧 Tool execution requested: {tool_name}[/yellow]")
    # console.print(
    #     Panel(
    #         _stringify_response(tool_data),
    #         title="Tool Arguments",
    #         border_style=COLORS["tool"],
    #     )
    # )
    
    # Create a simple prompt session for yes/no input
    kb = KeyBindings()
    
    @kb.add("y")
    @kb.add("Y")
    def accept(event):
        event.current_buffer.text = "y"
        event.current_buffer.validate_and_handle()
    
    @kb.add("n")
    @kb.add("N")
    def reject(event):
        event.current_buffer.text = "n"
        event.current_buffer.validate_and_handle()
    
    session = PromptSession(
        message="Execute this tool? (y/n): ",
        key_bindings=kb,
    )
    
    try:
        response = await session.prompt_async()
        return response.strip().lower() == "y"
    except (EOFError, KeyboardInterrupt):
        return False


def _handle_tool_use(
    tool_use: dict,
    session_state,
    approved_tool_use_ids: set[str],
    approved_tool_use_keys: set[str],
) -> None:
    """Handle tool use event in callback handler.
    
    Args:
        tool_use: Tool use dictionary containing tool name and ID
        session_state: Session state for status management
        approved_tool_use_ids: Set of approved tool use IDs
    """
    tool_name = tool_use.get("name")
    tool_use_id = tool_use.get("toolUseId")
    tool_input = tool_use.get("input")
    # NOTE: tool_use is often delivered multiple times (streaming). We print params once per toolUseId.

    # Debug helpers removed after investigation
    
    # ツール実行開始時: ステータス表示を開始
    if tool_name:
        session_state.set_thinking_status(None)  # 思考ステータスをクリア
        session_state.set_tool_status(f"Tool executing: {tool_name}...")
        # Tool parameters (same style as "Loaded MCP server: ...")
        if tool_input is not None and tool_use_id and tool_use_id not in _PRINTED_TOOL_PARAMS_IDS:
            normalized: Any = tool_input
            if isinstance(tool_input, str):
                s = tool_input.strip()
                if not s:
                    normalized = None
                elif s.startswith("{") or s.startswith("["):
                    try:
                        normalized = json.loads(s)
                    except json.JSONDecodeError:
                        normalized = None  # don't print partial JSON fragments
                else:
                    normalized = None

            if isinstance(normalized, (dict, list)):
                try:
                    args_json = json.dumps(normalized, ensure_ascii=False, default=str)
                except Exception:
                    args_json = str(normalized)
                console.print()
                console.print(f"[dim]{args_json}[/dim]")
                _PRINTED_TOOL_PARAMS_IDS.add(tool_use_id)
        elif tool_input is not None and tool_use_id is None:
            key_input = _normalize_tool_input(tool_input)
            tool_key = f"{tool_name}:{key_input}"
            if tool_key not in _PRINTED_TOOL_PARAMS_KEYS:
                console.print()
                console.print(f"[dim]{tool_key}[/dim]")
                _PRINTED_TOOL_PARAMS_KEYS.add(tool_key)
    
    if tool_name and not session_state.auto_approve:
        # 同期的に確認を求める（コールバックハンドラーは同期的）
        # 確認中はステータスを一時停止
        session_state.set_tool_status(None)
        approved = _ask_tool_approval_sync(tool_name, tool_use)
        if approved and tool_use_id:
            # 確認済みとして記録
            approved_tool_use_ids.add(tool_use_id)
            # ツール実行再開時にステータスを再開
            session_state.set_tool_status(f"Tool executing: {tool_name}...")
        elif approved and tool_use_id is None:
            # toolUseIdが無い場合は、name + input で一意化して確認済み扱い
            key_input = _normalize_tool_input(tool_input)
            tool_key = f"{tool_name}:{key_input}"
            approved_tool_use_keys.add(tool_key)
            session_state.set_tool_status(f"Tool executing: {tool_name}...")
        else:
            if not approved:
                toast("Tool execution rejected by user", kind="error")
            # ツール実行が拒否された場合はステータスを停止
            session_state.set_tool_status(None)
            # 注意: Strands Agentのコールバックハンドラーでは、
            # ツール実行を完全にブロックすることはできない可能性があります
            # この実装は警告表示のみです
    elif tool_name and session_state.auto_approve:
        # auto_approveがONの場合は、確認済みとして記録
        if tool_use_id:
            approved_tool_use_ids.add(tool_use_id)
        else:
            key_input = _normalize_tool_input(tool_input)
            tool_key = f"{tool_name}:{key_input}"
            approved_tool_use_keys.add(tool_key)


def _handle_tool_complete(session_state) -> None:
    """Handle tool completion event in callback handler.
    
    Args:
        session_state: Session state for status management
    """
    # ツール実行完了時: ステータス表示を停止して思考ステータスに切り替え
    session_state.set_tool_status(None)
    session_state.set_thinking_status("Thinking...")


def create_combined_callback(
    session_state,
    approved_tool_use_ids: set[str],
    approved_tool_use_keys: set[str],
    asked_tool_use_ids: set[str],
    asked_tool_use_keys: set[str],
    original_callback: Callable | None,
) -> Callable:
    """Create a combined callback handler for agent tool execution.
    
    Args:
        session_state: Session state for status management
        approved_tool_use_ids: Set of approved tool use IDs
        original_callback: Original callback handler to wrap
        
    Returns:
        Combined callback function
    """
    def combined_callback(**kwargs):
        """Combined callback handler that manages tool execution and status display."""
        # ツール実行確認
        if "current_tool_use" in kwargs:
            tool_use = kwargs["current_tool_use"]
            tool_use_id = tool_use.get("toolUseId")
            tool_name = tool_use.get("name")
            tool_input = tool_use.get("input")

            # Debug helpers removed after investigation

            # 同じtoolUseIdで既に確認済みの場合はスキップ
            if tool_use_id and tool_use_id in approved_tool_use_ids:
                # 既に確認済みなので、元のコールバックのみ呼び出す
                if original_callback:
                    original_callback(**kwargs)
                return
            if tool_use_id and tool_use_id in asked_tool_use_ids:
                if original_callback:
                    original_callback(**kwargs)
                return
            if tool_name:
                key_input = _normalize_tool_input(tool_input)
                tool_key = f"{tool_name}:{key_input}"
                last_approval_at = _LAST_TOOL_APPROVAL.get(tool_key)
                now = time.monotonic()
                # 直近の同一ツール確認は抑制（toolUseIdの有無に関わらず）
                if last_approval_at is not None and now - last_approval_at < 2.0:
                    if original_callback:
                        original_callback(**kwargs)
                    return

            if not tool_use_id and tool_name:
                key_input = _normalize_tool_input(tool_input)
                tool_key = f"{tool_name}:{key_input}"
                if tool_key in approved_tool_use_keys:
                    if original_callback:
                        original_callback(**kwargs)
                    return
                if tool_key in asked_tool_use_keys:
                    if original_callback:
                        original_callback(**kwargs)
                    return
                # 直近の同一ツール呼び出しは再確認しない（ストリーミングの重複イベント対策）
                last_at = _LAST_TOOL_REQUEST.get(tool_key)
                now = time.monotonic()
                if last_at is not None and now - last_at < 2.0:
                    if original_callback:
                        original_callback(**kwargs)
                    return
                # toolUseIdが変わっても、同じツール名 + 同じ入力が短時間で来たら抑制
                last_name = _LAST_TOOL_NAME_REQUEST.get(tool_name)
                if last_name:
                    last_time, last_input = last_name
                    if last_input == key_input and now - last_time < 5.0:
                        if original_callback:
                            original_callback(**kwargs)
                        return
            
            # ツール実行処理
            if tool_name:
                _LAST_TOOL_APPROVAL[tool_key] = time.monotonic()

            if tool_use_id:
                asked_tool_use_ids.add(tool_use_id)
            elif tool_name:
                asked_tool_use_keys.add(tool_key)

            _handle_tool_use(
                tool_use,
                session_state,
                approved_tool_use_ids,
                approved_tool_use_keys,
            )
            if not tool_use_id and tool_name:
                _LAST_TOOL_REQUEST[tool_key] = time.monotonic()
                _LAST_TOOL_NAME_REQUEST[tool_name] = (
                    time.monotonic(),
                    _normalize_tool_input(tool_input),
                )
        
        # AI思考中（ツール実行以外の処理中）の検出
        # イベントストリームで検出するため、ここではツール実行終了時の処理のみ
        if "tool_result" in kwargs or "tool_complete" in kwargs:
            _handle_tool_complete(session_state)
        
        # 元のコールバックハンドラーを呼び出す
        if original_callback:
            original_callback(**kwargs)
    
    # Mark wrapper to avoid double-wrapping across runs
    combined_callback._deepdiver_wrapper = True  # type: ignore[attr-defined]
    combined_callback._deepdiver_original = original_callback  # type: ignore[attr-defined]
    return combined_callback


async def _stream_agent(
    agent: Any, prompt: str, session_state=None, debug_mode: bool = False
) -> str | None:
    """Stream agent response and render events in real-time.
    
    This function implements the async iterator pattern for streaming agent events,
    following Strands Agents best practices.
    
    Args:
        agent: Strands Agent instance
        prompt: User prompt
        session_state: Session state with auto_approve flag
        debug_mode: Enable debug output for lifecycle events
    
    Returns:
        Final response text, or None if no response was generated
    """
    response_buffer: list[str] = []
    final_response = ""
    # 確認済みのツール実行IDを追跡（重複確認を防ぐ）
    approved_tool_use_ids: set[str] = set()
    approved_tool_use_keys: set[str] = set()
    asked_tool_use_ids: set[str] = set()
    asked_tool_use_keys: set[str] = set()
    
    try:
        # コールバックハンドラーを設定（エージェントがサポートしている場合）
        original_callback = getattr(agent, "callback_handler", None)
        if getattr(original_callback, "_deepdiver_wrapper", False):
            original_callback = getattr(original_callback, "_deepdiver_original", None)
        if hasattr(agent, "callback_handler") and session_state:
            # 既存のコールバックハンドラーと統合
            combined_callback = create_combined_callback(
                session_state,
                approved_tool_use_ids,
                approved_tool_use_keys,
                asked_tool_use_ids,
                asked_tool_use_keys,
                original_callback,
            )
            agent.callback_handler = combined_callback
        
        # ストリーミング開始時: AI思考中のステータスを開始
        if session_state:
            session_state.set_thinking_status("AI Thinking...")
        
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # 強制停止イベントのチェック
            if event.get("force_stop", False):
                reason = event.get("force_stop_reason", "unknown reason")
                toast(f"⚠️ Stream force-stopped: {reason}", kind="warning")

            # ライフサイクルイベントの表示（デバッグモードのみ）
            # _render_lifecycle_event(event, debug_mode)

            # ツールイベントの表示
            #_render_tool_event(event)
            
            # ツールストリーミングイベントの表示
            _render_tool_stream_event(event, session_state)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            # テキストがストリーミングされている場合は、思考中のステータスを停止
            # 注意: _render_model_delta内で既にステータスを停止している
            _render_model_delta(event, response_buffer, session_state)

            # 最終結果の取得
            # 注意: resultイベントは複数回発生する可能性があるため、
            # 最新のものを保持する
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
                    # 最終結果が取得されたらステータスを停止
                    if session_state:
                        session_state.clear_status()
            
        # 最終結果があればそれを使用、なければバッファから構築
        # 注意: resultイベントのoutput_textにはストリーミングされた全テキストが含まれるため、
        # 通常はfinal_responseを使用する
        # ステータス表示を停止
        if session_state:
            session_state.clear_status()
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except KeyboardInterrupt:
        # Ctrl+Cで中断された場合
        if session_state:
            session_state.clear_status()
        toast("Stream interrupted by user", kind="warning")
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        # エラー時はステータス表示をクリアしてからメッセージを表示
        if session_state:
            session_state.clear_status()
        toast(f"Streaming unavailable, falling back to blocking call ({exc})", kind="warning")
        return await _invoke_agent(agent, prompt)


async def _invoke_agent(agent: Any, prompt: str) -> str:
    # ステータス表示中はconsole.print()を呼び出さない
    if hasattr(agent, "invoke_async"):
        response = await agent.invoke_async(prompt)
        return _stringify_response(response)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: agent(prompt))
    return _stringify_response(response)

async def execute_task(
    user_input: str,
    agent: Any,
    assistant_id: str | None,
    session_state,
):
    """Execute a task by delegating to the Strands agent."""

    skill_prompt, cleaned_input = _extract_skill_prefix(user_input, assistant_id)
    final_input = _assemble_prompt(cleaned_input)

    if skill_prompt:
        final_input = f"{skill_prompt}\n\n{final_input}" if final_input else skill_prompt
    else:
        discovery_prompt = _build_skills_discovery_prompt(assistant_id)
        if discovery_prompt:
            final_input = (
                f"{discovery_prompt}\n\n{final_input}" if final_input else discovery_prompt
            )
    
    # 参考コードのパターンに従い、with文でstatusを管理
    # メッセージの最後に\nを追加して、ステータス終了後に改行が入るようにする

    if hasattr(agent, "stream_async"):
        response_text = await _stream_agent(agent, final_input, session_state)
        # ストリーミング中に既に内容が表示されているため、改行のみ追加
        console.print()
        
        # ストリーミング完了後、ToDoリストを抽出して表示
        if response_text:
            todos = extract_todos_from_text(response_text)
            if todos:
                console.print()
                console.print(render_todos_panel(todos, max_completed=3))
                console.print()
    else:
        response_text = await _invoke_agent(agent, final_input)
        # response_textがNoneの場合は空文字列にフォールバック
        if response_text is None:
            response_text = ""
        
        # Markdown/ANSI自動判別を使用して出力をレンダリング
        if response_text:
            console.print()
            console.print(render_agent_output(response_text, title="Agent"))
            
            # ToDoリストを抽出して表示
            todos = extract_todos_from_text(response_text)
            if todos:
                console.print()
                console.print(render_todos_panel(todos, max_completed=3))
            
            console.print()
