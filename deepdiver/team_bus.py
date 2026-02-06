"""Filesystem-backed message bus for team workers."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .team_paths import ensure_team_bus_dir


def _now_ts() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _channel_path(session_id: str, role: str) -> Path:
    bus_dir = ensure_team_bus_dir(session_id)
    return bus_dir / f"{role}.jsonl"


def initialize_bus(session_id: str, roles: list[str]) -> None:
    """Initialize message channels for the given roles."""
    for role in roles:
        p = _channel_path(session_id, role)
        if not p.exists():
            p.write_text("", encoding="utf-8")


def send_message(
    *,
    session_id: str,
    sender: str,
    receiver: str,
    content: str,
    msg_type: str = "task",
    parent_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Append a message to a role-specific channel and return message id."""
    msg_id = _new_id()
    payload: dict[str, Any] = {
        "id": msg_id,
        "ts": _now_ts(),
        "type": msg_type,
        "from": sender,
        "to": receiver,
        "content": content,
    }
    if parent_id:
        payload["parent_id"] = parent_id
    if extra:
        payload["extra"] = extra

    channel = _channel_path(session_id, receiver)
    with channel.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return msg_id


def read_messages_from_offset(
    *,
    session_id: str,
    role: str,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Read messages from a byte offset; return (messages, new_offset)."""
    channel = _channel_path(session_id, role)
    if not channel.exists():
        return [], 0

    msgs: list[dict[str, Any]] = []
    with channel.open("r", encoding="utf-8") as f:
        f.seek(max(offset, 0))
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                msgs.append(data)
        new_offset = f.tell()
    return msgs, new_offset

