"""JSONL transcript helpers for main agent runs."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from .paths import AGENT_ROOT

RUNS_DIRNAME = "runs"
SESSIONS_DIRNAME = "sessions"


def _now_ts() -> float:
    return time.time()


def _new_run_id() -> str:
    # short, url-safe, good enough uniqueness for local transcripts
    return uuid.uuid4().hex[:12]


def ensure_agent_runs_dir(assistant_id: str) -> Path:
    d = AGENT_ROOT / assistant_id / RUNS_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass(frozen=True)
class RunTranscript:
    run_id: str
    transcript_path: Path


class TranscriptStore:
    """JSONL transcript store for main agent runs."""

    def __init__(self, transcript_path: Path):
        self.transcript_path = transcript_path
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False)
        with self.transcript_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def transcripts_enabled() -> bool:
    value = os.environ.get("DEEPDIVER_TRANSCRIPT", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def start_run(assistant_id: str) -> tuple[RunTranscript, TranscriptStore]:
    run_id = _new_run_id()
    runs_dir = ensure_agent_runs_dir(assistant_id)
    transcript_path = runs_dir / f"agent-{run_id}.jsonl"
    store = TranscriptStore(transcript_path)
    return RunTranscript(run_id=run_id, transcript_path=transcript_path), store


def append_run_start(store: TranscriptStore, *, run_id: str, assistant_id: str) -> None:
    store.append(
        {
            "ts": _now_ts(),
            "event": "run_start",
            "run_id": run_id,
            "assistant": assistant_id,
            "source": "main",
        }
    )


def append_user_turn(store: TranscriptStore, content: str) -> None:
    store.append({"ts": _now_ts(), "role": "user", "content": content})


def append_assistant_turn(store: TranscriptStore, content: str) -> None:
    store.append({"ts": _now_ts(), "role": "assistant", "content": content})


def append_error(store: TranscriptStore, error: str) -> None:
    store.append({"ts": _now_ts(), "event": "error", "error": error})


def append_run_end(store: TranscriptStore, *, run_id: str) -> None:
    store.append({"ts": _now_ts(), "event": "run_end", "run_id": run_id})


def append_tool_event(store: TranscriptStore, *, event: str, data: dict[str, Any]) -> None:
    payload = {"ts": _now_ts(), "event": event}
    payload.update(data)
    store.append(payload)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _rollout_filename(ts: datetime, session_id: str) -> str:
    safe = ts.strftime("%Y-%m-%dT%H-%M-%S")
    return f"rollout-{safe}-{session_id}.jsonl"


def _ensure_sessions_dir(ts: datetime) -> Path:
    day_dir = AGENT_ROOT / SESSIONS_DIRNAME / ts.strftime("%Y") / ts.strftime("%m") / ts.strftime("%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir


def _deepdiver_version() -> str:
    try:
        import importlib.metadata as metadata
        return metadata.version("deepdiver-cli")
    except Exception:
        return "dev"


@dataclass
class _ToolStart:
    name: str
    is_custom: bool
    started_at: float


class CodexRolloutLogger:
    """Codex-compatible rollout JSONL logger."""

    def __init__(self, *, instructions: str | None = None) -> None:
        self.session_id = uuid.uuid4().hex
        self._session_ts = datetime.now(timezone.utc)
        self._path = _ensure_sessions_dir(self._session_ts) / _rollout_filename(
            self._session_ts, self.session_id
        )
        self._instructions = instructions
        self._tool_starts: dict[str, _ToolStart] = {}
        self._last_tool_for_name: dict[str, str] = {}
        self._last_started_call_id: str | None = None
        self._write_session_meta()

    @property
    def path(self) -> Path:
        return self._path

    def _write(self, record_type: str, payload: dict[str, Any]) -> None:
        data = {
            "timestamp": _now_iso(),
            "type": record_type,
            "payload": payload,
        }
        line = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _write_session_meta(self) -> None:
        payload: dict[str, Any] = {
            "id": self.session_id,
            "timestamp": self._session_ts.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "cwd": str(Path.cwd()),
            "originator": "deepdiver",
            "cli_version": _deepdiver_version(),
        }
        if self._instructions:
            payload["instructions"] = self._instructions
        self._write("session_meta", payload)

    def log_turn_context(
        self,
        *,
        cwd: str,
        approval_policy: str | None = None,
        sandbox_policy: dict[str, Any] | None = None,
        model: str | None = None,
        effort: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"cwd": cwd}
        if approval_policy:
            payload["approval_policy"] = approval_policy
        if sandbox_policy:
            payload["sandbox_policy"] = sandbox_policy
        if model:
            payload["model"] = model
        if effort:
            payload["effort"] = effort
        self._write("turn_context", payload)

    def log_message(self, *, role: str, text: str) -> None:
        content_type = "input_text" if role == "user" else "output_text"
        payload = {
            "type": "message",
            "role": role,
            "content": [{"type": content_type, "text": text}],
        }
        self._write("response_item", payload)

    def log_function_call(self, *, name: str, arguments: str, call_id: str) -> None:
        payload = {
            "type": "function_call",
            "name": name,
            "arguments": arguments,
            "call_id": call_id,
        }
        self._write("response_item", payload)

    def log_function_call_output(self, *, call_id: str, output: str, duration_ms: int | None) -> None:
        payload: dict[str, Any] = {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
        }
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        self._write("response_item", payload)

    def log_custom_tool_call(self, *, name: str, input_data: dict[str, Any], call_id: str) -> None:
        payload = {
            "type": "custom_tool_call",
            "name": name,
            "call_id": call_id,
            "input": input_data,
        }
        self._write("response_item", payload)

    def log_custom_tool_call_output(self, *, call_id: str, output: str, duration_ms: int | None) -> None:
        payload: dict[str, Any] = {
            "type": "custom_tool_call_output",
            "call_id": call_id,
            "output": output,
        }
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        self._write("response_item", payload)

    def start_tool(self, *, name: str, call_id: str, is_custom: bool) -> None:
        self._tool_starts[call_id] = _ToolStart(
            name=name,
            is_custom=is_custom,
            started_at=time.perf_counter(),
        )
        self._last_tool_for_name[name] = call_id
        self._last_started_call_id = call_id

    def finish_tool(self, *, call_id: str, output: str) -> None:
        start = self._tool_starts.get(call_id)
        duration_ms: int | None = None
        if start:
            duration_ms = int((time.perf_counter() - start.started_at) * 1000)
        if start and start.is_custom:
            self.log_custom_tool_call_output(
                call_id=call_id,
                output=output,
                duration_ms=duration_ms,
            )
        else:
            self.log_function_call_output(
                call_id=call_id,
                output=output,
                duration_ms=duration_ms,
            )
        if call_id in self._tool_starts:
            del self._tool_starts[call_id]

    def resolve_call_id(self, *, name: str, tool_use_id: str | None) -> str | None:
        if tool_use_id:
            return tool_use_id
        if name:
            return self._last_tool_for_name.get(name)
        # Fallback: if a single tool is in-flight, use it.
        if len(self._tool_starts) == 1:
            return next(iter(self._tool_starts.keys()))
        return None

    def last_started_call_id(self) -> str | None:
        return self._last_started_call_id
