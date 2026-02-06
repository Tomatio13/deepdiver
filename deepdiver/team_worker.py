"""Team worker runtime for tmux-based multi-agent collaboration."""

from __future__ import annotations

import asyncio
import json
import re
import select
import sys
import time
from pathlib import Path
from typing import Any

from strands_tools import calculator, current_time, editor, environment, file_read, file_write, http_request, shell

from .agent import create_agent_with_config
from .config import COLORS, DEEPDIVER_ASCII, console, create_model
from .csv_tool import filter_csv_data
from .mcp_tools import load_mcp_tools
from .subagents.load import get_subagent
from .subagents.runtime import run_subagent
from .team_bus import read_messages_from_offset, send_message
from .team_paths import ensure_team_state_dir, get_team_dir


def _default_tools(assistant_id: str) -> list[Any]:
    tools: list[Any] = [
        file_read,
        file_write,
        editor,
        shell,
        http_request,
        environment,
        calculator,
        current_time,
        filter_csv_data,
    ]
    tools.extend(load_mcp_tools(assistant_id))
    return tools


def _state_path(session_id: str, role: str) -> Path:
    state_dir = ensure_team_state_dir(session_id)
    return state_dir / f"{role}.json"


def _load_offset(session_id: str, role: str) -> int:
    p = _state_path(session_id, role)
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    value = data.get("offset", 0) if isinstance(data, dict) else 0
    return value if isinstance(value, int) and value >= 0 else 0


def _save_offset(session_id: str, role: str, offset: int) -> None:
    p = _state_path(session_id, role)
    p.write_text(json.dumps({"offset": max(offset, 0)}), encoding="utf-8")


async def _invoke_main_agent(agent: Any, task: str) -> str:
    if hasattr(agent, "invoke_async"):
        out = await agent.invoke_async(task)
        return str(out) if out is not None else ""
    return str(agent(task))


async def _run_with_progress(coro: Any, *, role: str, interval: float = 2.0) -> Any:
    """Run coroutine with periodic progress output."""
    task = asyncio.create_task(coro)
    started = time.time()
    tick = 0
    while not task.done():
        await asyncio.sleep(max(interval, 0.5))
        if task.done():
            break
        tick += 1
        elapsed = int(time.time() - started)
        console.print(
            f"[dim][{role}] 作業中... {elapsed}s 経過 (tick={tick})[/dim]",
            style=COLORS["dim"],
        )
    return await task


async def run_team_worker(
    *,
    session_id: str,
    role: str,
    assistant_id: str,
    poll_seconds: float = 1.0,
) -> None:
    """Run a worker loop that processes incoming messages for a role."""
    model = create_model()
    tools = _default_tools(assistant_id)
    main_agent = create_agent_with_config(model, assistant_id, tools)
    subagent = get_subagent(role)

    console.clear()
    console.print(DEEPDIVER_ASCII, style=COLORS["primary"])
    console.print()
    console.print(
        f"[bold]Team worker started[/bold] session={session_id} role={role}",
        style=COLORS["primary"],
    )
    if subagent:
        console.print(
            f"[dim]Role '{role}' mapped to subagent definition: {subagent['path']}[/dim]",
            style=COLORS["dim"],
        )

    offset = _load_offset(session_id, role)
    while True:
        msgs, new_offset = read_messages_from_offset(session_id=session_id, role=role, offset=offset)
        if msgs:
            offset = new_offset
            _save_offset(session_id, role, offset)

        for msg in msgs:
            msg_type = str(msg.get("type", ""))
            sender = str(msg.get("from", "team-lead"))
            content = str(msg.get("content", "")).strip()
            msg_id = str(msg.get("id", ""))
            if not content:
                continue

            if msg_type not in {"task", "instruction"}:
                continue

            console.print(
                f"[cyan]{sender} -> {role}[/cyan] {content[:120]}",
                style=COLORS["agent"],
            )
            console.print(f"[dim][{role}] タスク開始[/dim]", style=COLORS["dim"])

            try:
                if subagent:
                    run, response = await _run_with_progress(
                        run_subagent(
                            subagent=subagent,
                            task=content,
                            assistant_id=assistant_id,
                            model=model,
                            tools=tools,
                        ),
                        role=role,
                    )
                    payload = f"{response}\n\n(run_id: {run.run_id})"
                else:
                    payload = await _run_with_progress(
                        _invoke_main_agent(main_agent, content),
                        role=role,
                    )
            except Exception as exc:  # noqa: BLE001
                payload = f"[error] {exc}"
                console.print(f"[red][{role}] エラー: {exc}[/red]")

            send_message(
                session_id=session_id,
                sender=role,
                receiver=sender,
                content=payload,
                msg_type="response",
                parent_id=msg_id or None,
            )
            console.print(f"[dim][{role}] タスク完了[/dim]", style=COLORS["dim"])
            console.print(f"[green]{role} -> {sender}[/green] replied", style=COLORS["tool"])

        await asyncio.sleep(max(poll_seconds, 0.2))


def _print_incoming(role: str, msg: dict[str, Any]) -> None:
    msg_type = str(msg.get("type", "?"))
    sender = str(msg.get("from", "?"))
    content = str(msg.get("content", "")).strip()
    if not content:
        return
    console.print(f"[{msg_type}] {sender} -> {role}", style=COLORS["primary"])
    console.print(content, style=COLORS["agent"])
    console.print()


def _parse_lead_command(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text:
        return None
    if text.startswith("@") and " " in text:
        head, body = text.split(" ", 1)
        role = head[1:].strip()
        body = body.strip()
        if role and body:
            return role, body
    return None


def _read_team_roles(session_id: str) -> list[str]:
    meta_path = get_team_dir(session_id) / "session.json"
    if not meta_path.exists():
        return []
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    roles = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(roles, list):
        return []
    out = [str(r).strip() for r in roles if isinstance(r, str) and str(r).strip()]
    return out


def _parse_role_phrase(line: str, roles: list[str], self_role: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text:
        return None

    # Examples:
    # - "coderで 実装して"
    # - "reviewerに 見てほしい"
    m = re.match(r"^\s*([a-zA-Z0-9_-]+)\s*(で|に)\s+(.+?)\s*$", text)
    if m:
        role = m.group(1).strip()
        task = m.group(3).strip()
        if role in roles and role != self_role and task:
            return role, task

    # Example:
    # - "coder: 実装して"
    m2 = re.match(r"^\s*([a-zA-Z0-9_-]+)\s*[:：]\s*(.+?)\s*$", text)
    if m2:
        role = m2.group(1).strip()
        task = m2.group(2).strip()
        if role in roles and role != self_role and task:
            return role, task

    return None


def _infer_role_by_intent(line: str, roles: list[str], self_role: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text:
        return None
    lower = text.lower()

    # Prefer explicit role names if embedded in sentence.
    for role in roles:
        if role == self_role:
            continue
        if role.lower() in lower:
            return role, text

    keyword_map: list[tuple[str, tuple[str, ...]]] = [
        ("coder", ("実装", "修正", "バグ", "コード", "テスト", "build", "run", "fix", "implement")),
        ("reviewer", ("レビュー", "確認", "品質", "指摘", "review", "qa", "audit")),
        ("designer", ("デザイン", "ui", "ux", "レイアウト", "style", "visual")),
    ]
    for role_name, keywords in keyword_map:
        if role_name not in roles or role_name == self_role:
            continue
        if any(k in lower for k in keywords):
            return role_name, text
    return None


def run_team_lead_interactive(
    *,
    session_id: str,
    role: str,
    assistant_id: str = "agent",
    poll_seconds: float = 0.8,
) -> None:
    """Run interactive team-lead console.

    Usage in pane:
    - `@coder <task>`
    - `@reviewer <task>`
    - `/quit`
    """
    model = create_model()
    tools = _default_tools(assistant_id)
    lead_agent = create_agent_with_config(model, assistant_id, tools)

    console.clear()
    console.print(DEEPDIVER_ASCII, style=COLORS["primary"])
    console.print()
    console.print(
        f"[bold]Team lead mode[/bold] session={session_id} role={role}",
        style=COLORS["primary"],
    )
    console.print(
        "[dim]@<role> <message>: メンバーへ送信 / <role>で ...: 自動送信 / 通常: team-lead対話 / /quit: 終了[/dim]",
        style=COLORS["dim"],
    )
    console.print()

    roles = _read_team_roles(session_id)
    if roles:
        console.print(f"[dim]roles: {', '.join(roles)}[/dim]", style=COLORS["dim"])
        console.print()

    offset = _load_offset(session_id, role)
    while True:
        msgs, new_offset = read_messages_from_offset(session_id=session_id, role=role, offset=offset)
        if msgs:
            offset = new_offset
            _save_offset(session_id, role, offset)
            for msg in msgs:
                _print_incoming(role, msg)

        # Non-blocking stdin polling keeps inbox updates visible.
        ready, _, _ = select.select([sys.stdin], [], [], max(poll_seconds, 0.2))
        if not ready:
            continue

        line = sys.stdin.readline()
        if not line:
            time.sleep(0.2)
            continue
        line = line.strip()
        if not line:
            continue

        if line in {"/quit", "/exit", "/q"}:
            console.print("Team lead interactive stopped.", style=COLORS["dim"])
            return
        if line == "/roles":
            console.print(f"roles: {', '.join(roles) if roles else '(unknown)'}", style=COLORS["dim"])
            continue

        parsed = _parse_lead_command(line)
        if parsed:
            to_role, content = parsed
            send_message(
                session_id=session_id,
                sender=role,
                receiver=to_role,
                content=content,
                msg_type="task",
            )
            console.print(f"[green]sent -> {to_role}[/green]", style=COLORS["tool"])
            continue

        # Role phrase routing (e.g. "coderで 実装して")
        routed = _parse_role_phrase(line, roles, role)
        if routed is None:
            routed = _infer_role_by_intent(line, roles, role)
        if routed:
            to_role, content = routed
            send_message(
                session_id=session_id,
                sender=role,
                receiver=to_role,
                content=content,
                msg_type="task",
            )
            console.print(f"[green]auto-routed -> {to_role}[/green]", style=COLORS["tool"])
            continue

        # Plain text behaves like normal team-lead agent chat.
        try:
            response = asyncio.run(_invoke_main_agent(lead_agent, line))
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]agent error:[/red] {exc}")
            continue
        console.print(response, style=COLORS["agent"])
        console.print()
