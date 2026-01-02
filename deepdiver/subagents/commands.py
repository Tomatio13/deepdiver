"""CLI commands for sub-agent management.

Commands to add:
- deepdiver subagents list [--project]
- deepdiver subagents create <name> [--project]
- deepdiver subagents info <name> [--project]
- deepdiver subagents run <name> --agent <agent> -- <task...>
- deepdiver subagents resume <run_id> <name> --agent <agent> -- <task...>
"""

from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path
from typing import Any

from strands_tools import editor, environment, file_read, file_write, http_request, shell, calculator, current_time

from ..config import COLORS, console, create_model
from ..csv_tool import filter_csv_data
from ..mcp_tools import load_mcp_tools
from .load import get_subagent, list_subagents, read_subagent_definition
from .paths import ensure_project_subagents_dir, ensure_user_subagents_dir, get_project_subagents_dir, get_user_subagents_dir
from .runtime import run_subagent


def _validate_name(name: str) -> tuple[bool, str]:
    if not name or not name.strip():
        return False, "cannot be empty"
    if ".." in name:
        return False, "name cannot contain '..'"
    if name.startswith(("/", "\\")):
        return False, "name cannot be an absolute path"
    if "/" in name or "\\" in name:
        return False, "name cannot contain path separators"
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return False, "name can only contain letters, numbers, hyphens, and underscores"
    return True, ""


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
    return servers


def _default_tools(assistant_id: str, *, only_mcp_servers: set[str] | None = None) -> list[Any]:
    # Keep in sync with main.DEFAULT_TOOLS without importing main.py (avoid cycles)
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
    if only_mcp_servers is None:
        tools.extend(load_mcp_tools(assistant_id))
    elif len(only_mcp_servers) > 0:
        tools.extend(load_mcp_tools(assistant_id, only_servers=only_mcp_servers))
    return tools


def _list(*, project: bool = False) -> None:
    user_dir = get_user_subagents_dir()
    project_dir = get_project_subagents_dir()

    if project:
        if not project_dir:
            console.print("[yellow]Not in a project directory.[/yellow]")
            console.print(
                "[dim]Project subagents require a .git directory in the project root.[/dim]",
                style=COLORS["dim"],
            )
            return
        items = list_subagents(user_subagents_dir=None, project_subagents_dir=project_dir)
    else:
        items = list_subagents(user_subagents_dir=user_dir, project_subagents_dir=project_dir)

    if not items:
        console.print("[yellow]No subagents found.[/yellow]")
        console.print(
            f"[dim]Create user subagents in {user_dir}/ or project subagents in {project_dir}/[/dim]",
            style=COLORS["dim"],
        )
        console.print(
            "\n[dim]Create a subagent:\n  deepdiver subagents create my-subagent\n  deepdiver subagents create my-subagent --project[/dim]",
            style=COLORS["dim"],
        )
        return

    user_items = [s for s in items if s["source"] == "user"]
    project_items = [s for s in items if s["source"] == "project"]

    console.print("\n[bold]Available Subagents:[/bold]\n", style=COLORS["primary"])
    if user_items and not project:
        console.print("[bold cyan]User Subagents:[/bold cyan]", style=COLORS["primary"])
        for s in user_items:
            console.print(f"  • [bold]{s['name']}[/bold]", style=COLORS["primary"])
            console.print(f"    {s['description']}", style=COLORS["dim"])
            console.print(f"    {s['path']}", style=COLORS["dim"])
            console.print()

    if project_items:
        if user_items and not project:
            console.print()
        console.print("[bold green]Project Subagents:[/bold green]", style=COLORS["primary"])
        for s in project_items:
            console.print(f"  • [bold]{s['name']}[/bold]", style=COLORS["primary"])
            console.print(f"    {s['description']}", style=COLORS["dim"])
            console.print(f"    {s['path']}", style=COLORS["dim"])
            console.print()


def _create(name: str, *, project: bool = False) -> None:
    ok, err = _validate_name(name)
    if not ok:
        console.print(f"[bold red]Error:[/bold red] Invalid subagent name: {err}")
        return

    if project:
        base = ensure_project_subagents_dir()
        if not base:
            console.print("[bold red]Error:[/bold red] Not in a project directory.")
            console.print(
                "[dim]Project subagents require a .git directory in the project root.[/dim]",
                style=COLORS["dim"],
            )
            return
    else:
        base = ensure_user_subagents_dir()

    path = base / f"{name}.md"
    if path.exists():
        console.print(f"[bold red]Error:[/bold red] Subagent already exists: {path}")
        return

    template = f"""---\nname: {name}\ndescription: [Describe when to use this subagent]\n# tools: file_read,file_write\n# enable_skills: true\n---\n\n# {name}\n\n## Purpose\n\n[What this subagent does]\n\n## When to Use\n\n- [Scenario 1]\n- [Scenario 2]\n\n## Instructions\n\n[Step-by-step guidance, constraints, examples]\n"""
    path.write_text(template, encoding="utf-8")

    console.print(f"✓ Subagent '{name}' created successfully!", style=COLORS["primary"])
    console.print(f"Location: {path}\n", style=COLORS["dim"])
    console.print(f"[dim]Edit the file:\n  nano {path}[/dim]", style=COLORS["dim"])


def _info(name: str, *, project: bool = False) -> None:
    item = get_subagent(name)
    if not item:
        console.print(f"[bold red]Error:[/bold red] Subagent '{name}' not found.")
        _list(project=project)
        return

    p = Path(item["path"])
    meta, body = read_subagent_definition(p)
    console.print(
        f"\n[bold]Subagent: {item['name']}[/bold] ({item['source']})\n",
        style=COLORS["primary"],
    )
    console.print(f"[bold]Description:[/bold] {item['description']}", style=COLORS["dim"])
    console.print(f"[bold]Location:[/bold] {p}\n", style=COLORS["dim"])
    console.print("[bold]Frontmatter:[/bold]\n", style=COLORS["primary"])
    console.print(str(meta), style=COLORS["dim"])
    console.print("\n[bold]Body:[/bold]\n", style=COLORS["primary"])
    console.print(body or "(empty)", style=COLORS["dim"])
    console.print()


def _run(name: str, task: str, *, assistant_id: str, resume_from: str | None = None) -> None:
    sub = get_subagent(name)
    if not sub:
        console.print(f"[bold red]Error:[/bold red] Subagent '{name}' not found.")
        _list()
        return

    model = create_model()
    tools = _default_tools(assistant_id, only_mcp_servers=_infer_mcp_servers_from_allowed_tools(sub.get("tools")))

    async def _go():
        run, output = await run_subagent(
            subagent=sub,
            task=task,
            assistant_id=assistant_id,
            model=model,
            tools=tools,
            resume_from=resume_from,
        )
        console.print()
        console.print(f"[bold]Run ID:[/bold] {run.run_id}", style=COLORS["primary"])
        console.print(f"[dim]Transcript: {run.transcript_path}[/dim]", style=COLORS["dim"])
        console.print()
        console.print(output, style=COLORS["agent"])
        console.print()

    asyncio.run(_go())


def setup_subagents_parser(subparsers: Any) -> argparse.ArgumentParser:
    subagents_parser = subparsers.add_parser(
        "subagents",
        help="Manage subagents",
        description="Manage subagents - create, list, view info, and run",
    )
    sp = subagents_parser.add_subparsers(dest="subagents_command", help="Subagents command")

    list_p = sp.add_parser("list", help="List subagents")
    list_p.add_argument("--project", action="store_true", help="Show only project-level subagents")

    create_p = sp.add_parser("create", help="Create a subagent")
    create_p.add_argument("name", help="Name of the subagent to create (e.g., code-reviewer)")
    create_p.add_argument("--project", action="store_true", help="Create in project directory")

    info_p = sp.add_parser("info", help="Show subagent details")
    info_p.add_argument("name", help="Name of the subagent")
    info_p.add_argument("--project", action="store_true", help="Search only project directory (best-effort)")

    run_p = sp.add_parser("run", help="Run a subagent")
    run_p.add_argument("name", help="Name of the subagent")
    run_p.add_argument("--agent", default="agent", help="Main agent profile id (for skills/mcp scope)")
    run_p.add_argument("task", nargs=argparse.REMAINDER, help="Task to run (use -- before task)")

    resume_p = sp.add_parser("resume", help="Resume a subagent run")
    resume_p.add_argument("run_id", help="Previous run id to resume from")
    resume_p.add_argument("name", help="Name of the subagent")
    resume_p.add_argument("--agent", default="agent", help="Main agent profile id (for skills/mcp scope)")
    resume_p.add_argument("task", nargs=argparse.REMAINDER, help="Task to run (use -- before task)")

    return subagents_parser


def execute_subagents_command(args: argparse.Namespace) -> None:
    cmd = args.subagents_command
    if cmd == "list":
        _list(project=args.project)
        return
    if cmd == "create":
        _create(args.name, project=args.project)
        return
    if cmd == "info":
        _info(args.name, project=args.project)
        return
    if cmd == "run":
        task = " ".join(args.task).strip()
        if not task:
            console.print("[bold red]Error:[/bold red] Missing task. Use `--` before the task text.")
            return
        _run(args.name, task, assistant_id=args.agent)
        return
    if cmd == "resume":
        task = " ".join(args.task).strip()
        if not task:
            console.print("[bold red]Error:[/bold red] Missing task. Use `--` before the task text.")
            return
        _run(args.name, task, assistant_id=args.agent, resume_from=args.run_id)
        return

    console.print("[yellow]Please specify a subagents subcommand: list, create, info, run, resume[/yellow]")
    console.print("[dim]Try: deepdiver subagents --help[/dim]", style=COLORS["dim"])


__all__ = ["execute_subagents_command", "setup_subagents_parser"]

