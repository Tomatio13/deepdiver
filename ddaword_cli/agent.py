"""Agent management utilities for the Strands-powered CLI."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Sequence

from strands import Agent

from .config import COLORS, console, get_default_coding_instructions

AGENT_ROOT = Path.home() / ".strands-agents-cli"
MEMORY_DIRNAME = "memories"


def _agent_dir(assistant_id: str) -> Path:
    return AGENT_ROOT / assistant_id


def _ensure_agent_files(assistant_id: str) -> Path:
    agent_dir = _agent_dir(assistant_id)
    agent_dir.mkdir(parents=True, exist_ok=True)

    agent_md = agent_dir / "AGENT.md"
    if not agent_md.exists():
        agent_md.write_text(get_default_coding_instructions())

    memory_dir = agent_dir / MEMORY_DIRNAME
    memory_dir.mkdir(exist_ok=True)

    return agent_dir


def list_agents() -> None:
    """List all available CLI agents."""
    if not AGENT_ROOT.exists() or not any(AGENT_ROOT.iterdir()):
        console.print("[yellow]No agents found.[/yellow]")
        console.print(
            "[dim]Agents will be created in ~/.strands-agents-cli/ when first used.[/dim]",
            style=COLORS["dim"],
        )
        return

    console.print("\n[bold]Available Agents:[/bold]\n", style=COLORS["primary"])

    for agent_path in sorted(AGENT_ROOT.iterdir()):
        if not agent_path.is_dir():
            continue
        agent_name = agent_path.name
        agent_md = agent_path / "AGENT.md"

        if agent_md.exists():
            console.print(f"  • [bold]{agent_name}[/bold]", style=COLORS["primary"])
            console.print(f"    {agent_path}", style=COLORS["dim"])
        else:
            console.print(
                f"  • [bold]{agent_name}[/bold] [dim](incomplete)[/dim]", style=COLORS["tool"]
            )
            console.print(f"    {agent_path}", style=COLORS["dim"])

    console.print()


def reset_agent(agent_name: str, source_agent: str | None = None) -> None:
    """Reset an agent prompt to the default or copy from another agent."""
    target_dir = _agent_dir(agent_name)

    if source_agent:
        source_dir = _agent_dir(source_agent)
        source_md = source_dir / "AGENT.md"
        if not source_md.exists():
            console.print(
                f"[bold red]Error:[/bold red] Source agent '{source_agent}' not found or missing agent.md"
            )
            return
        new_prompt = source_md.read_text()
        action_desc = f"contents of agent '{source_agent}'"
    else:
        new_prompt = get_default_coding_instructions()
        action_desc = "default"

    if target_dir.exists():
        shutil.rmtree(target_dir)
        console.print(f"Removed existing agent directory: {target_dir}", style=COLORS["tool"])

    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "AGENT.md").write_text(new_prompt)
    (target_dir / MEMORY_DIRNAME).mkdir(exist_ok=True)

    console.print(f"✓ Agent '{agent_name}' reset to {action_desc}", style=COLORS["primary"])
    console.print(f"Location: {target_dir}\n", style=COLORS["dim"])


def _base_cli_prompt(agent_dir: Path) -> str:
    memory_dir = agent_dir / MEMORY_DIRNAME
    cwd = Path.cwd()
    working_dir = cwd.name+"/"+"workspace"
    return f"""### CLI Runtime Context

- Working directory: `{working_dir}`
- Agent profile directory: `{agent_dir}`
- Persistent memory directory: `{memory_dir}`
- If working directory is not `{working_dir}`, create it and use it.
- If working directory is `{working_dir}`, use it.
"""


def _build_system_prompt(agent_dir: Path) -> str:
    base_prompt = _base_cli_prompt(agent_dir)
    agent_md = (agent_dir / "AGENT.md").read_text().strip()

    if agent_md:
        return f"{base_prompt}\n\n<agent_memory>\n{agent_md}\n</agent_memory>"
    return base_prompt


def get_agent_directory(assistant_id: str) -> Path:
    """Return the on-disk directory backing the assistant profile."""
    return _ensure_agent_files(assistant_id)


def get_system_prompt(assistant_id: str = "agent") -> str:
    """Return the fully resolved system prompt for the given assistant."""
    agent_dir = _ensure_agent_files(assistant_id)
    return _build_system_prompt(agent_dir)


def create_agent_with_config(model: Any | None, assistant_id: str, tools: Sequence[Any]) -> Agent:
    """Create a Strands Agent configured for the CLI runtime."""
    agent_dir = _ensure_agent_files(assistant_id)
    system_prompt = _build_system_prompt(agent_dir)

    agent_kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "tools": list(tools),
    }
    if model is not None:
        agent_kwargs["model"] = model

    agent = Agent(**agent_kwargs)

    # Expose CLI-related paths so other modules can reuse them without recomputation.
    setattr(
        agent,
        "cli_context",
        {
            "agent_dir": agent_dir,
            "memory_dir": agent_dir / MEMORY_DIRNAME,
        },
    )

    return agent
