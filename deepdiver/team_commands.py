"""Team commands for tmux-based multi-agent collaboration."""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from .config import COLORS, console
from .team_bus import initialize_bus, read_messages_from_offset, send_message
from .team_paths import ensure_team_dir, ensure_teams_root, get_team_dir
from .team_worker import run_team_lead_interactive, run_team_worker

DEFAULT_ROLES = ["team-lead", "coder", "reviewer"]


def _parse_roles(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_ROLES)
    out = [x.strip() for x in raw.split(",") if x.strip()]
    return out or list(DEFAULT_ROLES)


def _tmux_exists() -> bool:
    return shutil.which("tmux") is not None


def _tmux(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["tmux", *args], check=True, capture_output=True, text=True)


def _team_meta_path(session_id: str) -> Path:
    return get_team_dir(session_id) / "session.json"


def _write_team_meta(session_id: str, data: dict[str, Any]) -> None:
    p = _team_meta_path(session_id)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_team_meta(session_id: str) -> dict[str, Any] | None:
    p = _team_meta_path(session_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _start(args: argparse.Namespace) -> None:
    if not _tmux_exists():
        console.print("[bold red]Error:[/bold red] tmux not found.")
        return

    session_id = args.session or uuid.uuid4().hex[:8]
    roles = _parse_roles(args.roles)
    lead_role = "team-lead" if "team-lead" in roles else roles[0]
    member_roles = [r for r in roles if r != lead_role]
    assistant_id = args.agent
    lead_width = args.lead_width
    if lead_width < 40:
        lead_width = 40
    if lead_width > 85:
        lead_width = 85
    tmux_session = f"deepdiver-{session_id}"

    ensure_teams_root()
    ensure_team_dir(session_id)
    initialize_bus(session_id, roles)

    cwd = str(Path.cwd().resolve())
    py = shlex.quote(sys.executable)
    qcwd = shlex.quote(cwd)

    def _worker_cmd(role: str, *, interactive: bool = False) -> str:
        # Use the currently running Python interpreter so venv activation is not required.
        interactive_flag = " --interactive" if interactive else ""
        return (
            f"cd {qcwd} && {py} -m deepdiver team worker "
            f"--session {session_id} --role {shlex.quote(role)} --agent {shlex.quote(assistant_id)}"
            f"{interactive_flag}"
        )

    try:
        _tmux("new-session", "-d", "-s", tmux_session, "-n", "team")

        # Pane 0: always reserve for lead role (interactive if role is team-lead).
        lead_cmd = _worker_cmd(lead_role, interactive=(lead_role == "team-lead"))
        _tmux("send-keys", "-t", f"{tmux_session}:0.0", lead_cmd, "C-m")

        # Create panes for members (right-side stack after layout is applied).
        for role in member_roles:
            created = _tmux("split-window", "-v", "-t", f"{tmux_session}:0", "-P", "-F", "#{pane_id}")
            pane_id = created.stdout.strip()
            cmd = _worker_cmd(role, interactive=(role == "team-lead"))
            if pane_id:
                _tmux("send-keys", "-t", pane_id, cmd, "C-m")
            else:
                _tmux("send-keys", "-t", f"{tmux_session}:0", cmd, "C-m")

        # Force layout: lead on left main pane, members stacked on right.
        _tmux("set-window-option", "-t", f"{tmux_session}:0", "main-pane-width", f"{lead_width}%")
        _tmux("select-pane", "-t", f"{tmux_session}:0.0")
        _tmux("select-layout", "-t", f"{tmux_session}:0", "main-vertical")
    except subprocess.CalledProcessError as exc:
        console.print(f"[bold red]tmux error:[/bold red] {exc.stderr or exc}")
        return

    _write_team_meta(
        session_id,
        {
            "session_id": session_id,
            "tmux_session": tmux_session,
            "roles": [lead_role, *member_roles],
            "assistant_id": assistant_id,
        },
    )

    console.print(f"✓ Team session created: {session_id}", style=COLORS["primary"])
    console.print(f"tmux session: {tmux_session}", style=COLORS["dim"])
    console.print(f"roles: {', '.join([lead_role, *member_roles])}", style=COLORS["dim"])
    console.print(f"attach: tmux attach -t {tmux_session}", style=COLORS["dim"])


def _stop(args: argparse.Namespace) -> None:
    session_id = args.session
    meta = _read_team_meta(session_id)
    if not meta:
        console.print(f"[yellow]Session metadata not found: {session_id}[/yellow]")
        return

    tmux_session = str(meta.get("tmux_session", ""))
    if not tmux_session:
        console.print("[yellow]tmux session name is missing in metadata.[/yellow]")
        return

    try:
        _tmux("kill-session", "-t", tmux_session)
    except subprocess.CalledProcessError as exc:
        console.print(f"[yellow]Failed to kill tmux session:[/yellow] {exc.stderr or exc}")
        return

    console.print(f"✓ Stopped team session: {session_id}", style=COLORS["primary"])


def _status(args: argparse.Namespace) -> None:
    session_id = args.session
    meta = _read_team_meta(session_id)
    if not meta:
        console.print(f"[yellow]Session not found: {session_id}[/yellow]")
        return
    console.print(json.dumps(meta, ensure_ascii=False, indent=2), style=COLORS["dim"])


def _send(args: argparse.Namespace) -> None:
    msg = args.message.strip()
    if not msg:
        console.print("[bold red]Error:[/bold red] Empty message.")
        return

    send_message(
        session_id=args.session,
        sender=args.sender,
        receiver=args.to,
        content=msg,
        msg_type=args.type,
    )
    console.print("✓ Sent", style=COLORS["primary"])


def _inbox(args: argparse.Namespace) -> None:
    msgs, _ = read_messages_from_offset(
        session_id=args.session,
        role=args.role,
        offset=0,
    )
    if args.tail > 0:
        msgs = msgs[-args.tail :]

    if not msgs:
        console.print("(no messages)", style=COLORS["dim"])
        return

    for msg in msgs:
        sender = msg.get("from", "?")
        msg_type = msg.get("type", "?")
        content = str(msg.get("content", "")).strip()
        console.print(f"[{msg_type}] {sender}: {content}", style=COLORS["dim"])


def _worker(args: argparse.Namespace) -> None:
    if args.interactive:
        run_team_lead_interactive(
            session_id=args.session,
            role=args.role,
            assistant_id=args.agent,
            poll_seconds=args.poll,
        )
        return
    asyncio.run(
        run_team_worker(
            session_id=args.session,
            role=args.role,
            assistant_id=args.agent,
            poll_seconds=args.poll,
        )
    )


def setup_team_parser(subparsers: Any) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "team",
        help="Manage tmux-based multi-agent teams",
    )
    sp = parser.add_subparsers(dest="team_command", help="Team command")

    start_p = sp.add_parser("start", help="Start a tmux team session")
    start_p.add_argument("--session", help="Session id (default: random)")
    start_p.add_argument("--roles", help="Comma-separated roles")
    start_p.add_argument("--agent", default="agent", help="Agent profile id")
    start_p.add_argument(
        "--lead-width",
        type=int,
        default=58,
        help="Left team-lead pane width percentage (40-85, default: 58)",
    )

    stop_p = sp.add_parser("stop", help="Stop a tmux team session")
    stop_p.add_argument("--session", required=True, help="Session id")

    status_p = sp.add_parser("status", help="Show session metadata")
    status_p.add_argument("--session", required=True, help="Session id")

    send_p = sp.add_parser("send", help="Send a message to a role")
    send_p.add_argument("--session", required=True, help="Session id")
    send_p.add_argument("--from", dest="sender", default="team-lead", help="Sender role")
    send_p.add_argument("--to", required=True, help="Receiver role")
    send_p.add_argument("--type", default="task", help="Message type (task/instruction/...)")
    send_p.add_argument("message", nargs=argparse.REMAINDER, help="Message text")

    inbox_p = sp.add_parser("inbox", help="Read role inbox")
    inbox_p.add_argument("--session", required=True, help="Session id")
    inbox_p.add_argument("--role", required=True, help="Role name")
    inbox_p.add_argument("--tail", type=int, default=20, help="Show last N messages")

    worker_p = sp.add_parser("worker", help="Run a team worker loop")
    worker_p.add_argument("--session", required=True, help="Session id")
    worker_p.add_argument("--role", required=True, help="Role name")
    worker_p.add_argument("--agent", default="agent", help="Agent profile id")
    worker_p.add_argument("--poll", type=float, default=1.0, help="Polling interval seconds")
    worker_p.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive console mode (recommended for team-lead)",
    )

    return parser


def execute_team_command(args: argparse.Namespace) -> None:
    cmd = args.team_command
    if cmd == "start":
        _start(args)
        return
    if cmd == "stop":
        _stop(args)
        return
    if cmd == "status":
        _status(args)
        return
    if cmd == "send":
        parts = list(args.message)
        if parts and parts[0] == "--":
            parts = parts[1:]
        args.message = " ".join(parts).strip()
        _send(args)
        return
    if cmd == "inbox":
        _inbox(args)
        return
    if cmd == "worker":
        _worker(args)
        return

    console.print("Use: deepdiver team [start|stop|status|send|inbox|worker]", style=COLORS["dim"])
