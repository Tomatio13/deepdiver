"""Sub-agent runtime (runner, transcripts, resume) for Deepdiver.

This module provides a minimal execution layer for sub-agents:
- Create an isolated `strands.Agent` instance per run
- Apply tool allowlists from sub-agent metadata
- Store conversation transcripts as JSONL
- Resume runs by injecting recent transcript into the prompt (compatibility mode)
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from strands import Agent

from ..config import COLORS, SENSITIVE_KEYS, console
from ..security import DefenderSettings, PromptInjectionDefender
from ..paths import AGENT_ROOT
from ..skills.load import list_skills
from ..skills.paths import get_project_skills_dir, get_user_skills_dir
from ..skills.prompt import build_skills_prompt
from strands.tools.registry import ToolProvider
from .load import SubagentMetadata, read_subagent_definition
from .paths import ensure_user_subagent_runs_dir

_PROMPT_DEFENDER = PromptInjectionDefender(DefenderSettings.from_env())


def _now_ts() -> float:
    return time.time()


def _new_run_id() -> str:
    # short, url-safe, good enough uniqueness for local transcripts
    return uuid.uuid4().hex[:12]


def _tool_name(tool: Any) -> str | None:
    """Best-effort tool name extraction for allowlist filtering."""
    # AgentTool instances
    tool_name = getattr(tool, "tool_name", None)
    if isinstance(tool_name, str) and tool_name.strip():
        return tool_name.strip()

    name = getattr(tool, "name", None)
    if isinstance(name, str) and name.strip():
        name = name.strip()
        return name.split(".")[-1]
    name = getattr(tool, "__name__", None)
    if isinstance(name, str) and name.strip():
        name = name.strip()
        return name.split(".")[-1]
    # MCPClient: prefer its prefix if present
    prefix = getattr(tool, "prefix", None)
    if isinstance(prefix, str) and prefix.strip():
        prefix = prefix.strip()
        return prefix.split(".")[-1]
    return tool.__class__.__name__.split(".")[-1]


def _filter_tools(tools: list[Any], allowed: list[str] | None) -> list[Any]:
    if not allowed:
        return tools
    allowed_set = {a.strip() for a in allowed if isinstance(a, str) and a.strip()}
    if not allowed_set:
        return tools

    kept: list[Any] = []
    for tool in tools:
        name = _tool_name(tool)
        if not name:
            continue

        # Direct allow
        if name in allowed_set:
            kept.append(tool)
            continue

        # Special-case ToolProvider (MCP): allow provider if any allowed tool is under its namespace
        # Example: allowed contains 'taivily_search' -> keep provider 'taivily'
        if isinstance(tool, ToolProvider):
            if any(token == name or token.startswith(f"{name}_") for token in allowed_set):
                kept.append(tool)
                continue
    return kept


def _base_cli_prompt(assistant_id: str) -> str:
    """Mirror `deepdiver.agent._base_cli_prompt` without importing private API."""
    cwd = Path.cwd()
    working_dir = f"{cwd.name}/workspace"
    agent_dir = AGENT_ROOT / assistant_id
    return f"""### CLI Runtime Context

- Working directory: `{working_dir}`
- Agent profile directory: `{agent_dir}`
- If working directory is not `{working_dir}`, create it and use it.
- If working directory is `{working_dir}`, use it.
"""


def _build_subagent_system_prompt(
    *,
    assistant_id: str,
    subagent_body: str,
    enable_skills: bool,
) -> str:
    base = _base_cli_prompt(assistant_id)
    if enable_skills:
        skills_prompt = build_skills_prompt(assistant_id)
        if skills_prompt:
            base = f"{base}\n\n{skills_prompt}"
    body = subagent_body.strip()
    if body:
        return f"{base}\n\n<subagent_memory>\n{body}\n</subagent_memory>"
    return base


@dataclass(frozen=True)
class SubagentRun:
    run_id: str
    subagent_name: str
    transcript_path: Path


class TranscriptStore:
    """JSONL transcript store for sub-agent runs."""

    def __init__(self, transcript_path: Path):
        self.transcript_path = transcript_path
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False)
        with self.transcript_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def read_events(self) -> list[dict[str, Any]]:
        if not self.transcript_path.exists():
            return []
        events: list[dict[str, Any]] = []
        for raw in self.transcript_path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                events.append(data)
        return events


def _format_previous_conversation(events: list[dict[str, Any]], *, max_turns: int = 8) -> str | None:
    """Compatibility resume: embed recent transcript into prompt."""
    # keep only user/assistant textual turns
    turns: list[tuple[str, str]] = []
    for e in events:
        role = e.get("role")
        content = e.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            turns.append((role, content.strip()))

    if not turns:
        return None

    # take last N turns
    turns = turns[-max_turns:]

    lines = ["<previous_conversation>"]
    for role, content in turns:
        lines.append(f"{role}: {content}")
    lines.append("</previous_conversation>")
    return "\n".join(lines)


_SKILL_PREFIX_RE = re.compile(
    r"^\s*\$(?P<name>[a-zA-Z0-9_-]+)\b\s*(?P<rest>.*)$", re.DOTALL
)


def _extract_skill_prefix(task: str, assistant_id: str) -> tuple[str | None, str]:
    """Apply the same $skill prefix behavior as the interactive CLI."""
    m = _SKILL_PREFIX_RE.match(task)
    if not m:
        return None, task

    skill_name = m.group("name")
    rest = (m.group("rest") or "").strip()

    skills = list_skills(
        user_skills_dir=get_user_skills_dir(assistant_id),
        project_skills_dir=get_project_skills_dir(),
    )
    skill = next((s for s in skills if s["name"] == skill_name), None)
    if not skill:
        return None, rest or task

    skill_path = Path(skill["path"])
    try:
        skill_content = skill_path.read_text(encoding="utf-8")
    except OSError:
        return None, rest or task

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


def _build_skills_discovery_prompt(assistant_id: str) -> str | None:
    skills = list_skills(
        user_skills_dir=get_user_skills_dir(assistant_id),
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
        lines.append(f"- {skill['name']}: {skill['description']} (path: {skill['path']})")
    return "\n".join(lines)


def _force_allow_file_read(allowed_tools: list[str] | None) -> list[str] | None:
    """If tools are explicitly restricted, ensure file_read is allowed for skills usage."""
    if allowed_tools is None:
        return None
    allowed = [t.strip() for t in allowed_tools if t and t.strip()]
    if "file_read" not in allowed:
        allowed.append("file_read")
    return allowed


def _apply_prompt_defense(task: str) -> tuple[str, bool]:
    if not _PROMPT_DEFENDER.enabled:
        return task, False

    decision = _PROMPT_DEFENDER.evaluate(task)
    categories = ", ".join(decision.categories) if decision.categories else "unknown"
    if decision.action == "block":
        console.print(
            f"[red]Security policy blocked subagent task "
            f"(score={decision.score:.2f}, categories={categories})[/red]"
        )
        return "", True

    if decision.action == "sanitize" and decision.redacted_text is not None:
        console.print(
            f"[yellow]Security policy sanitized subagent task "
            f"(score={decision.score:.2f}, categories={categories})[/yellow]"
        )
        return decision.redacted_text, False

    if decision.action == "warn":
        console.print(
            f"[yellow]Security warning for subagent task "
            f"(score={decision.score:.2f}, categories={categories})[/yellow]"
        )

    return task, False


async def _invoke_agent(agent: Any, prompt: str) -> str:
    if hasattr(agent, "invoke_async"):
        resp = await agent.invoke_async(prompt)
        return str(resp) if resp is not None else ""
    # fallback: sync call in thread not done here (caller should be async context)
    return str(agent(prompt))


async def run_subagent(
    *,
    subagent: SubagentMetadata,
    task: str,
    assistant_id: str,
    model: Any | None,
    tools: list[Any],
    run_id: str | None = None,
    resume_from: str | None = None,
) -> tuple[SubagentRun, str]:
    """Run a sub-agent task and return (run_info, response_text).

    Notes:
    - If `run_id` is None, a new run id is created.
    - If `resume_from` is provided, the transcript is loaded and injected into the prompt.
    """
    run_id = run_id or _new_run_id()
    runs_dir = ensure_user_subagent_runs_dir()
    transcript_path = runs_dir / f"agent-{run_id}.jsonl"
    store = TranscriptStore(transcript_path)
    secured_task, blocked = _apply_prompt_defense(task)

    # Load sub-agent definition body (system prompt memory)
    md_path = Path(subagent["path"])
    _, body = read_subagent_definition(md_path)
    enable_skills = subagent.get("enable_skills", True)
    system_prompt = _build_subagent_system_prompt(
        assistant_id=assistant_id,
        subagent_body=body,
        enable_skills=enable_skills,
    )

    # Tool allowlist from metadata
    allowed_tools = subagent.get("tools")
    if enable_skills:
        allowed_tools = _force_allow_file_read(allowed_tools)
    filtered_tools = _filter_tools(tools, allowed_tools)
    printed_tool_use_ids: set[str] = set()

    def _redact_tool_input(value: Any) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                    out[k] = "***"
                else:
                    out[k] = _redact_tool_input(v)
            return out
        if isinstance(value, list):
            return [_redact_tool_input(v) for v in value]
        return value

    def _subagent_callback(**kwargs: Any) -> None:
        tool_use = kwargs.get("current_tool_use")
        if not isinstance(tool_use, dict):
            return
        tool_name = tool_use.get("name")
        tool_input = tool_use.get("input")
        tool_use_id = tool_use.get("toolUseId")
        if not tool_name or tool_input is None:
            return

        if tool_use_id and str(tool_use_id) in printed_tool_use_ids:
            return

        # Normalize stringified JSON if possible, then redact common secrets.
        normalized: Any = tool_input
        if isinstance(tool_input, str):
            s = tool_input.strip()
            if not s:
                return
            if s.startswith("{") or s.startswith("["):
                try:
                    normalized = json.loads(s)
                except json.JSONDecodeError:
                    # Don't print partial/incomplete JSON fragments.
                    return
            else:
                # Plain strings (non-JSON) are too noisy; skip.
                return
        normalized = _redact_tool_input(normalized)

        try:
            args_json = json.dumps(normalized, ensure_ascii=False, default=str)
        except Exception:
            args_json = str(normalized)

        # Same color as "Loaded MCP server: ..."
        console.print(f"[dim]{args_json}[/dim]")
        if tool_use_id:
            printed_tool_use_ids.add(str(tool_use_id))

    # Create isolated sub-agent instance
    agent_kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "tools": list(filtered_tools),
        "callback_handler": _subagent_callback,
    }
    if model is not None:
        agent_kwargs["model"] = model
    agent = Agent(**agent_kwargs)

    # Build prompt with optional resume
    resume_text = None
    if resume_from:
        resume_path = runs_dir / f"agent-{resume_from}.jsonl"
        resume_events = TranscriptStore(resume_path).read_events()
        resume_text = _format_previous_conversation(resume_events)

    # Apply skills discovery / explicit $skill selection (if enabled)
    skill_prompt = None
    cleaned_task = secured_task
    if enable_skills:
        skill_prompt, cleaned_task = _extract_skill_prefix(secured_task, assistant_id)

    final_prompt = cleaned_task.strip()
    if resume_text:
        final_prompt = f"{resume_text}\n\n{final_prompt}" if final_prompt else resume_text
    if enable_skills:
        if skill_prompt:
            final_prompt = f"{skill_prompt}\n\n{final_prompt}" if final_prompt else skill_prompt
        else:
            discovery = _build_skills_discovery_prompt(assistant_id)
            if discovery:
                final_prompt = f"{discovery}\n\n{final_prompt}" if final_prompt else discovery

    # Transcript: header + turn
    store.append(
        {
            "ts": _now_ts(),
            "event": "run_start",
            "run_id": run_id,
            "subagent": subagent["name"],
            "source": subagent.get("source"),
            "enable_skills": enable_skills,
        }
    )
    if allowed_tools is not None:
        store.append({"ts": _now_ts(), "event": "tools_policy", "tools": allowed_tools})
    if resume_from:
        store.append({"ts": _now_ts(), "event": "resume", "from": resume_from})

    if blocked:
        blocked_msg = "Blocked by security policy before subagent execution."
        store.append(
            {
                "ts": _now_ts(),
                "event": "security_blocked",
                "reason": blocked_msg,
            }
        )
        store.append({"ts": _now_ts(), "role": "assistant", "content": blocked_msg})
        store.append({"ts": _now_ts(), "event": "run_end", "run_id": run_id})
        run = SubagentRun(run_id=run_id, subagent_name=subagent["name"], transcript_path=transcript_path)
        return run, blocked_msg

    store.append({"ts": _now_ts(), "role": "user", "content": final_prompt})

    # Execute
    try:
        response = await _invoke_agent(agent, final_prompt)
    except Exception as exc:  # noqa: BLE001
        # keep error in transcript for postmortem
        store.append(
            {
                "ts": _now_ts(),
                "event": "error",
                "error": str(exc),
            }
        )
        raise

    store.append({"ts": _now_ts(), "role": "assistant", "content": response})
    store.append({"ts": _now_ts(), "event": "run_end", "run_id": run_id})

    run = SubagentRun(run_id=run_id, subagent_name=subagent["name"], transcript_path=transcript_path)
    return run, response


def warn_if_tools_filtered(subagent: SubagentMetadata, tools_before: list[Any], tools_after: list[Any]) -> None:
    """Optional helper for UX (used by CLI layer later)."""
    if subagent.get("tools") and len(tools_after) < len(tools_before):
        console.print(
            f"[dim]Subagent '{subagent['name']}' tools restricted: {len(tools_after)}/{len(tools_before)} allowed[/dim]"
        )
