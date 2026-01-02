"""Tools to delegate work to subagents (Agents as tools pattern)."""

from __future__ import annotations

import asyncio
from typing import Any

from strands import tool
from strands_tools import editor, environment, file_read, file_write, http_request, shell, calculator, current_time

from ..csv_tool import filter_csv_data
from ..mcp_tools import load_mcp_tools
from ..config import create_model
from .load import get_subagent
from .runtime import run_subagent


def _infer_mcp_servers_from_allowed_tools(allowed_tools: list[str] | None) -> set[str] | None:
    if not allowed_tools:
        return None
    allowed = [t.strip() for t in allowed_tools if isinstance(t, str) and t.strip()]
    if not allowed:
        return None
    servers: set[str] = set()
    for t in allowed:
        if t.startswith("taivily_"):
            servers.add("taivily")
        if t.startswith("weather_"):
            servers.add("weather")
        if t.startswith("firecrawl_"):
            servers.add("firecrawl")
    # If allowlist exists but contains no MCP-prefixed tools, this subagent needs no MCP at all.
    return servers


def _default_tools(assistant_id: str, *, only_mcp_servers: set[str] | None = None) -> list[Any]:
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
    # only_mcp_servers:
    # - None: unknown / allow all MCP servers
    # - empty set: explicitly no MCP needed
    # - non-empty: only those servers
    if only_mcp_servers is None:
        tools.extend(load_mcp_tools(assistant_id))
    elif len(only_mcp_servers) > 0:
        tools.extend(load_mcp_tools(assistant_id, only_servers=only_mcp_servers))
    return tools


async def _run_subagent_one(
    *,
    name: str,
    task: str,
    assistant_id: str,
    model: Any | None,
    resume_from: str | None,
    semaphore: asyncio.Semaphore | None,
) -> dict[str, Any]:
    async def _inner() -> dict[str, Any]:
        sub = get_subagent(name)
        if not sub:
            return {"name": name, "ok": False, "error": f"Subagent not found: {name}"}

        # Build tools with only the MCP servers needed for this subagent.
        only_mcp_servers = _infer_mcp_servers_from_allowed_tools(sub.get("tools"))
        tools = _default_tools(assistant_id, only_mcp_servers=only_mcp_servers)

        run, output = await run_subagent(
            subagent=sub,
            task=task,
            assistant_id=assistant_id,
            model=model,
            tools=tools,
            resume_from=resume_from,
        )
        return {
            "name": name,
            "ok": True,
            "run_id": run.run_id,
            "transcript": str(run.transcript_path),
            "output": output,
        }

    if semaphore is None:
        return await _inner()

    async with semaphore:
        return await _inner()


@tool
async def delegate_to_subagent(
    name: str,
    task: str,
    assistant_id: str = "agent",
    resume_from: str | None = None,
) -> str:
    """Delegate a task to a configured subagent and return its output.

    Args:
        name: Subagent name (as defined in subagents directory).
        task: Task/prompt for the subagent.
        assistant_id: Main agent profile id (for skills/mcp scope).
        resume_from: Optional run_id to resume from.

    Returns:
        Subagent output with run_id and transcript path.
    """
    sub = get_subagent(name)
    if not sub:
        return f"Subagent not found: {name}"

    model = create_model()
    tools = _default_tools(assistant_id, only_mcp_servers=_infer_mcp_servers_from_allowed_tools(sub.get("tools")))

    run, output = await run_subagent(
        subagent=sub,
        task=task,
        assistant_id=assistant_id,
        model=model,
        tools=tools,
        resume_from=resume_from,
    )
    return (
        f"[Subagent: {name}]\n"
        f"run_id: {run.run_id}\n"
        f"transcript: {run.transcript_path}\n\n"
        f"{output}"
    )


@tool
async def delegate_to_subagents_parallel(
    requests: list[dict[str, Any]],
    assistant_id: str = "agent",
    max_concurrency: int = 3,
) -> str:
    """Delegate multiple tasks to subagents concurrently and return aggregated results.

    Args:
        requests: List of request objects: {name: str, task: str, resume_from?: str}
        assistant_id: Main agent profile id (for skills/mcp scope).
        max_concurrency: Limit concurrent subagent runs (default: 3).

    Returns:
        Aggregated markdown-ish text with per-subagent outputs and run metadata.
    """
    if not isinstance(requests, list) or not requests:
        return "No requests provided."

    # Clamp concurrency to a sane range
    if not isinstance(max_concurrency, int) or max_concurrency < 1:
        max_concurrency = 1
    if max_concurrency > 10:
        max_concurrency = 10

    model = create_model()
    semaphore = asyncio.Semaphore(max_concurrency)

    tasks: list[asyncio.Task] = []
    for req in requests:
        if not isinstance(req, dict):
            continue
        name = req.get("name")
        task_text = req.get("task")
        resume_from = req.get("resume_from")

        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(task_text, str) or not task_text.strip():
            continue
        if resume_from is not None and not isinstance(resume_from, str):
            resume_from = None

        tasks.append(
            asyncio.create_task(
                _run_subagent_one(
                    name=name.strip(),
                    task=task_text,
                    assistant_id=assistant_id,
                    model=model,
                    resume_from=resume_from,
                    semaphore=semaphore,
                )
            )
        )

    if not tasks:
        return "No valid requests found. Each item must include: {name: str, task: str}."

    results = await asyncio.gather(*tasks, return_exceptions=True)

    lines: list[str] = []
    lines.append("## Subagents (Parallel) Results")
    lines.append(f"- assistant_id: {assistant_id}")
    lines.append(f"- max_concurrency: {max_concurrency}")
    lines.append("")

    for idx, r in enumerate(results, 1):
        if isinstance(r, Exception):
            lines.append(f"### {idx}. (error)")
            lines.append(f"- error: {r}")
            lines.append("")
            continue

        name = r.get("name", "unknown")
        ok = r.get("ok", False)
        lines.append(f"### {idx}. {name}")
        lines.append(f"- ok: {ok}")
        if ok:
            lines.append(f"- run_id: {r.get('run_id')}")
            lines.append(f"- transcript: {r.get('transcript')}")
            lines.append("")
            lines.append(str(r.get("output", "")))
            lines.append("")
        else:
            lines.append(f"- error: {r.get('error')}")
            lines.append("")

    return "\n".join(lines)

