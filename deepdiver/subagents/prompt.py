"""Sub-agents discovery prompt for Deepdiver (progressive disclosure)."""

from __future__ import annotations

from pathlib import Path

from .load import SubagentMetadata, list_subagents
from .paths import get_project_subagents_dir, get_user_subagents_dir


SUBAGENTS_SYSTEM_PROMPT = """

## Subagents System

You have access to a subagents library that provides specialized agent personas.

{subagents_locations}

**Available Subagents:**

{subagents_list}

**How to Use Subagents:**

Subagents follow a **progressive disclosure** pattern:
1. Recognize when a subagent applies based on its description
2. Delegate with the `delegate_to_subagent` tool (preferred)
   - If you have multiple independent subtasks, use `delegate_to_subagents_parallel` to run them concurrently.
3. If needed, read the subagent definition file for details

**Delegation:**
- Use `delegate_to_subagent(name=..., task=...)` when a subagent is a better fit than the main agent.
- Use `delegate_to_subagents_parallel(requests=[...])` when you want to run multiple subagents concurrently.
- Subagents run with an isolated context and may have restricted tools.
"""


def _format_display_path(path: Path) -> str:
    home = str(Path.home())
    s = str(path)
    if s.startswith(home):
        return s.replace(home, "~", 1)
    return s


def _format_locations(user_dir: Path, project_dir: Path | None) -> str:
    loc = [f"**User Subagents**: `{_format_display_path(user_dir)}`"]
    if project_dir:
        loc.append(
            f"**Project Subagents**: `{_format_display_path(project_dir)}` (overrides user subagents)"
        )
    return "\n".join(loc)


def _format_list(subagents: list[SubagentMetadata], user_dir: Path, project_dir: Path | None) -> str:
    if not subagents:
        loc = [_format_display_path(user_dir)]
        if project_dir:
            loc.append(_format_display_path(project_dir))
        return f"(No subagents available yet. You can create subagents in {' or '.join(loc)})"

    user_items = [s for s in subagents if s["source"] == "user"]
    project_items = [s for s in subagents if s["source"] == "project"]

    lines: list[str] = []
    if user_items:
        lines.append("**User Subagents:**")
        for s in user_items:
            lines.append(f"- **{s['name']}**: {s['description']}")
            lines.append(f"  → Read `{s['path']}` for full definition")
        lines.append("")
    if project_items:
        lines.append("**Project Subagents:**")
        for s in project_items:
            lines.append(f"- **{s['name']}**: {s['description']}")
            lines.append(f"  → Read `{s['path']}` for full definition")
    return "\n".join(lines)


def build_subagents_prompt() -> str | None:
    """Build the subagents section for the system prompt."""
    user_dir = get_user_subagents_dir()
    project_dir = get_project_subagents_dir()
    subagents = list_subagents(user_subagents_dir=user_dir, project_subagents_dir=project_dir)
    if not subagents and not user_dir.exists() and not (project_dir and project_dir.exists()):
        return None

    return SUBAGENTS_SYSTEM_PROMPT.format(
        subagents_locations=_format_locations(user_dir, project_dir),
        subagents_list=_format_list(subagents, user_dir, project_dir),
    )

