"""Task execution helpers for the Strands-based CLI."""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich.markdown import Markdown
from rich.panel import Panel

from .config import COLORS, console
from .input import parse_file_mentions


def _assemble_prompt(user_input: str) -> str:
    prompt_text, mentioned_files = parse_file_mentions(user_input)

    if not mentioned_files:
        return prompt_text

    context_parts = [prompt_text, "\n\n## Referenced Files\n"]
    for file_path in mentioned_files:
        try:
            content = file_path.read_text()
            if len(content) > 50000:
                content = content[:50000] + "\n... (file truncated)"
            context_parts.append(
                f"\n### {file_path.name}\nPath: `{file_path}`\n```\n{content}\n```"
            )
        except Exception as exc:  # noqa: BLE001
            context_parts.append(f"\n### {file_path.name}\n[Error reading file: {exc}]")

    return "\n".join(context_parts)


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

def _render_model_delta(event: dict, buffer: list[str]) -> bool:
    """Render model delta and return True if content was rendered."""
    # Strands Agentのドキュメントによると、テキストチャンクは 'data' フィールドに直接ある
    # 'delta' も存在するが、'data' が推奨される
    data = event.get("data")
    if isinstance(data, str) and data:
        buffer.append(data)
        console.print(data, style=COLORS["agent"], end="")
        #console.print(Markdown(data.replace("\n", "")), style=COLORS["agent"],end="")
        # ストリーミング時のリアルタイム表示を改善するため、出力を即座にフラッシュ
        sys.stdout.flush()
        return True
    
    # 後方互換性のため、delta もチェック
    delta = event.get("delta")
    if isinstance(delta, str) and delta:
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


def _render_tool_stream_event(event: dict) -> None:
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
        # ツールからのストリーミングデータを表示
        console.print(
            f"[dim]🔧 Tool '{tool_name}' streaming: {data}[/dim]",
            end=""
        )
        sys.stdout.flush()

def _ask_tool_approval_sync(tool_name: str, tool_data: dict) -> bool:
    """Ask user for approval before executing a tool (synchronous version).
    
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
    
    # Use simple input() for synchronous confirmation
    # This is needed because callback handlers are synchronous
    try:
        response = input("Execute this tool? (y/n): ").strip().lower()
        return response == "y"
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
    
    try:
        # コールバックハンドラーを設定（エージェントがサポートしている場合）
        original_callback = getattr(agent, "callback_handler", None)
        if hasattr(agent, "callback_handler") and session_state:
            # 既存のコールバックハンドラーと統合
            def combined_callback(**kwargs):
                # ツール実行確認
                if "current_tool_use" in kwargs:
                    tool_use = kwargs["current_tool_use"]
                    tool_name = tool_use.get("name")
                    tool_use_id = tool_use.get("toolUseId")
                    
                    # 同じtoolUseIdで既に確認済みの場合はスキップ
                    if tool_use_id and tool_use_id in approved_tool_use_ids:
                        # 既に確認済みなので、元のコールバックのみ呼び出す
                        if original_callback:
                            original_callback(**kwargs)
                        return
                    
                    if tool_name and not session_state.auto_approve:
                        # 同期的に確認を求める（コールバックハンドラーは同期的）
                        approved = _ask_tool_approval_sync(tool_name, tool_use)
                        if approved and tool_use_id:
                            # 確認済みとして記録
                            approved_tool_use_ids.add(tool_use_id)
                        if not approved:
                            console.print("[red]Tool execution rejected by user[/red]")
                            # 注意: Strands Agentのコールバックハンドラーでは、
                            # ツール実行を完全にブロックすることはできない可能性があります
                            # この実装は警告表示のみです
                    elif tool_name and session_state.auto_approve:
                        # auto_approveがONの場合は、確認済みとして記録
                        if tool_use_id:
                            approved_tool_use_ids.add(tool_use_id)
                
                # 元のコールバックハンドラーを呼び出す
                if original_callback:
                    original_callback(**kwargs)
            
            agent.callback_handler = combined_callback
        
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # 強制停止イベントのチェック
            if event.get("force_stop", False):
                reason = event.get("force_stop_reason", "unknown reason")
                console.print(
                    f"\n[yellow]⚠️ Stream force-stopped: {reason}[/yellow]"
                )

            # ライフサイクルイベントの表示（デバッグモードのみ）
            # _render_lifecycle_event(event, debug_mode)

            # ツールイベントの表示
            #_render_tool_event(event)
            
            # ツールストリーミングイベントの表示
            _render_tool_stream_event(event)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            _render_model_delta(event, response_buffer)

            # 最終結果の取得
            # 注意: resultイベントは複数回発生する可能性があるため、
            # 最新のものを保持する
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
            
        # 最終結果があればそれを使用、なければバッファから構築
        # 注意: resultイベントのoutput_textにはストリーミングされた全テキストが含まれるため、
        # 通常はfinal_responseを使用する
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except KeyboardInterrupt:
        # Ctrl+Cで中断された場合
        console.print("\n[yellow]Stream interrupted by user[/yellow]")
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        # エラー時はステータス表示をクリアしてからメッセージを表示
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
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

    final_input = _assemble_prompt(user_input)
    
    # 参考コードのパターンに従い、with文でstatusを管理
    # メッセージの最後に\nを追加して、ステータス終了後に改行が入るようにする

    if hasattr(agent, "stream_async"):
        response_text = await _stream_agent(agent, final_input, session_state)
        # ストリーミング中に既に内容が表示されているため、改行のみ追加
        console.print()
    else:
        response_text = await _invoke_agent(agent, final_input)
        # response_textがNoneの場合は空文字列にフォールバック
        if response_text is None:
            response_text = ""
        
        console.print()
        console.print(Markdown(response_text), style=COLORS["agent"])
        console.print()

