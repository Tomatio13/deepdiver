"""Command handlers for slash commands and bash execution."""

import subprocess
from pathlib import Path

from .agent import AGENT_ROOT
from .config import (
    COLORS,
    DEEPDIVER_ASCII,
    apply_theme,
    console,
    get_current_model_info,
    get_theme_name,
    get_theme_names,
)
from .input import apply_theme_to_prompt_session
from .mcp_tools import get_mcp_server_info
from .subagents.load import get_subagent, list_subagents
from .subagents.paths import get_project_subagents_dir, get_user_subagents_dir
from .subagents.runtime import run_subagent
from .skills.load import list_skills
from .skills.paths import get_project_skills_dir, get_user_skills_dir
from .ui import show_interactive_help, toast


def _print_skills_list(skills: list[dict]) -> None:
    if not skills:
        console.print("[yellow]No skills found.[/yellow]")
        console.print(
            "[dim]Create skills in ~/.deepdiver/<agent>/skills/ or .deepdiver/skills/[/dim]",
            style=COLORS["dim"],
        )
        return

    console.print("\n[bold]Available Skills:[/bold]\n", style=COLORS["primary"])
    for idx, skill in enumerate(skills, 1):
        source = "project" if skill["source"] == "project" else "user"
        console.print(f"  {idx}. [bold]${skill['name']}[/bold] [{source}]", style=COLORS["primary"])
        console.print(f"     {skill['description']}", style=COLORS["dim"])
        console.print(f"     {skill['path']}", style=COLORS["dim"])
    console.print()
    console.print(
        "[dim]Type /skills then Tab to insert $skill, or use /skills <name> for details.[/dim]",
        style=COLORS["dim"],
    )
    console.print()


def _print_skill_detail(skill: dict) -> None:
    skill_path = Path(skill["path"])
    if not skill_path.exists():
        toast(f"Skill file not found: {skill_path}", kind="warning")
        console.print()
        return

    skill_content = skill_path.read_text()
    console.print(
        f"\n[bold]Skill: {skill['name']}[/bold] ({skill['source']})\n",
        style=COLORS["primary"],
    )
    console.print(f"[bold]Description:[/bold] {skill['description']}\n", style=COLORS["dim"])
    console.print(f"[bold]Location:[/bold] {skill_path}\n", style=COLORS["dim"])
    console.print("[bold]Full SKILL.md Content:[/bold]\n", style=COLORS["primary"])
    console.print(skill_content, style=COLORS["dim"])
    console.print()


async def handle_command(
    command: str, assistant_id: str = "agent", session_state=None
) -> str | bool:
    """Handle slash commands. Returns 'exit' to exit, True if handled, False to pass to agent."""
    stripped_command = command.strip().lstrip("/")
    cmd_lower = stripped_command.lower()

    if cmd_lower in ["quit", "exit", "q"]:
        return "exit"

    if cmd_lower == "clear":
        # Clear screen and show fresh UI
        console.clear()
        console.print(DEEPDIVER_ASCII, style=f"{COLORS['primary']}")
        console.print()
        console.print(
            "... Fresh start! Screen cleared. Conversation state will continue in the current session.",
            style=COLORS["agent"],
        )
        console.print()
        return True

    if cmd_lower == "help":
        show_interactive_help()
        return True

    if cmd_lower == "model":
        model_info = get_current_model_info()
        console.print()
        if model_info["provider"]:
            console.print("[bold]Current Model Configuration:[/bold]", style=COLORS["primary"])
            console.print(f"  Provider: [bold]{model_info['provider']}[/bold]", style=COLORS["agent"])
            if model_info["model_name"]:
                console.print(f"  Model: [bold]{model_info['model_name']}[/bold]", style=COLORS["agent"])
            else:
                console.print("  Model: [dim](not specified, using provider defaults)[/dim]", style=COLORS["dim"])
        else:
            toast("No model provider configured.\nSet STRANDS_MODEL_PROVIDER environment variable to configure a model.", kind="warning")
        console.print()
        return True

    if cmd_lower.startswith("theme"):
        parts = stripped_command.split(maxsplit=1)
        arg = parts[1].strip().lower() if len(parts) > 1 else ""

        console.print()
        theme_names = get_theme_names()
        current = get_theme_name()

        if not arg or arg in {"list", "ls"}:
            console.print("[bold]Available Themes:[/bold]", style=COLORS["primary"])
            for name in theme_names:
                marker = "*" if name == current else " "
                console.print(f"  {marker} {name}", style=COLORS["agent"])
            console.print()
            console.print(
                f"[dim]Current theme: {current} (use /theme <name> to switch)[/dim]",
                style=COLORS["dim"],
            )
            console.print()
            return True

        updated = False
        if session_state:
            updated = session_state.set_theme(arg)
        else:
            updated = apply_theme(arg)

        if updated:
            if session_state:
                apply_theme_to_prompt_session(session_state)
            console.print(
                f"[bold]Theme updated:[/bold] {get_theme_name()}",
                style=COLORS["primary"],
            )
        else:
            toast(
                f"Unknown theme: {arg}\nAvailable: {', '.join(theme_names)}",
                kind="warning",
            )
        console.print()
        return True


    if cmd_lower == "mcp":
        # Show MCP server information
        console.print()
        console.print("[bold]MCP Servers Configuration[/bold]", style=COLORS["primary"])
        console.print()

        agent_dir = AGENT_ROOT / assistant_id
        mcp_config_path = agent_dir / "mcp.json"

        if not mcp_config_path.exists():
            toast(f"No mcp.json found at: {mcp_config_path}\nCreate mcp.json in the agent directory to configure MCP servers.", kind="warning")
            console.print()
            return True

        server_info_list = get_mcp_server_info(assistant_id)
        if not server_info_list:
            toast("No MCP servers configured.", kind="warning")
            console.print()
            return True

        for info in server_info_list:
            status = "[dim](disabled)[/dim]" if info["disabled"] else "[green](enabled)[/green]"
            console.print(f"  [bold]{info['name']}[/bold] {status}", style=COLORS["agent"])
            if info["type"]:
                console.print(f"    Type: {info['type']}", style=COLORS["dim"])
            if info["connection"]:
                # Truncate long connection strings
                conn = info["connection"]
                if len(conn) > 80:
                    conn = conn[:77] + "..."
                console.print(f"    Connection: [dim]{conn}[/dim]", style=COLORS["dim"])
            console.print()

        console.print(f"[dim]Configuration file: {mcp_config_path}[/dim]")
        console.print()
        return True

    if cmd_lower.startswith("skills"):
        parts = stripped_command.split(maxsplit=1)
        arg = parts[1] if len(parts) > 1 else ""

        user_skills_dir = get_user_skills_dir(assistant_id)
        project_skills_dir = get_project_skills_dir()
        skills = list_skills(
            user_skills_dir=user_skills_dir,
            project_skills_dir=project_skills_dir,
        )

        if not arg or arg == "list":
            _print_skills_list(skills)
            return True

        if arg == "help":
            console.print("\n[bold]Skills Command Usage:[/bold]", style=COLORS["primary"])
            console.print("  /skills                List skills", style=COLORS["dim"])
            console.print("  /skills list           List skills", style=COLORS["dim"])
            console.print("  /skills <number>       Show skill details", style=COLORS["dim"])
            console.print("  /skills <name>         Show skill details", style=COLORS["dim"])
            console.print("  $<name> <request>      Run with a skill", style=COLORS["dim"])
            console.print()
            return True

        # Try numeric index selection
        selected: dict | None = None
        if arg.isdigit():
            index = int(arg) - 1
            if 0 <= index < len(skills):
                selected = skills[index]
        else:
            selected = next((s for s in skills if s["name"] == arg), None)

        if not selected:
            toast(f"Skill not found: {arg}", kind="warning")
            _print_skills_list(skills)
            return True

        _print_skill_detail(selected)
        return True

    if cmd_lower.startswith("subagents") or cmd_lower.startswith("agents"):
        # /agents is an alias for /subagents
        parts = stripped_command.split(maxsplit=1)
        argline = parts[1] if len(parts) > 1 else ""

        user_dir = get_user_subagents_dir()
        project_dir = get_project_subagents_dir()
        subs = list_subagents(user_subagents_dir=user_dir, project_subagents_dir=project_dir)

        def _print_subagents_list() -> None:
            if not subs:
                console.print("[yellow]No subagents found.[/yellow]")
                console.print(
                    f"[dim]Create subagents in {user_dir}/ or {project_dir}/[/dim]",
                    style=COLORS["dim"],
                )
                console.print()
                return
            console.print("\n[bold]Available Subagents:[/bold]\n", style=COLORS["primary"])
            for idx, s in enumerate(subs, 1):
                console.print(
                    f"  {idx}. [bold]{s['name']}[/bold] [{s['source']}]",
                    style=COLORS["primary"],
                )
                console.print(f"     {s['description']}", style=COLORS["dim"])
                console.print(f"     {s['path']}", style=COLORS["dim"])
            console.print()
            console.print(
                "[dim]Usage:\n"
                "  /subagents                 List subagents\n"
                "  /subagents <name> <task>    Run subagent\n"
                "  /subagents resume <run_id> <name> <task>  Resume\n"
                "[/dim]",
                style=COLORS["dim"],
            )
            console.print()

        if not argline or argline.strip() in ("list",):
            _print_subagents_list()
            return True

        if argline.strip() == "help":
            _print_subagents_list()
            return True

        # resume form: resume <run_id> <name> <task...>
        if argline.lower().startswith("resume "):
            tokens = argline.split(maxsplit=3)
            if len(tokens) < 4:
                toast("Usage: /subagents resume <run_id> <name> <task>", kind="warning")
                _print_subagents_list()
                return True
            _, run_id, name, task = tokens
            sub = get_subagent(name)
            if not sub:
                toast(f"Subagent not found: {name}", kind="warning")
                _print_subagents_list()
                return True

            from .config import create_model
            from strands_tools import (
                calculator,
                current_time,
                editor,
                environment,
                file_read,
                file_write,
                http_request,
                shell,
            )

            from .csv_tool import filter_csv_data
            from .mcp_tools import load_mcp_tools

            model = create_model()
            tools = [
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

            run, output = await run_subagent(
                subagent=sub,
                task=task,
                assistant_id=assistant_id,
                model=model,
                tools=tools,
                resume_from=run_id,
            )
            console.print()
            console.print(f"[bold]Run ID:[/bold] {run.run_id}", style=COLORS["primary"])
            console.print(f"[dim]Transcript: {run.transcript_path}[/dim]", style=COLORS["dim"])
            console.print()
            console.print(output, style=COLORS["agent"])
            console.print()
            return True

        # run form: <name> <task...>
        tokens = argline.split(maxsplit=1)
        if len(tokens) < 2:
            toast("Usage: /subagents <name> <task>", kind="warning")
            _print_subagents_list()
            return True
        name, task = tokens
        sub = get_subagent(name)
        if not sub:
            toast(f"Subagent not found: {name}", kind="warning")
            _print_subagents_list()
            return True

        from .config import create_model
        from strands_tools import (
            calculator,
            current_time,
            editor,
            environment,
            file_read,
            file_write,
            http_request,
            shell,
        )

        from .csv_tool import filter_csv_data
        from .mcp_tools import load_mcp_tools

        model = create_model()
        tools = [
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

        run, output = await run_subagent(
            subagent=sub,
            task=task,
            assistant_id=assistant_id,
            model=model,
            tools=tools,
        )
        console.print()
        console.print(f"[bold]Run ID:[/bold] {run.run_id}", style=COLORS["primary"])
        console.print(f"[dim]Transcript: {run.transcript_path}[/dim]", style=COLORS["dim"])
        console.print()
        console.print(output, style=COLORS["agent"])
        console.print()
        return True

    toast(f"Unknown command: /{cmd_lower}\nType /help for available commands.", kind="warning")
    console.print()
    return True

    return False


def execute_bash_command(command: str) -> bool:
    """Execute a bash command and display output. Returns True if handled."""
    cmd = command.strip().lstrip("!")

    if not cmd:
        return True

    try:
        console.print()
        console.print(f"[dim]$ {cmd}[/dim]")

        # Execute the command
        result = subprocess.run(
            cmd, check=False, shell=True, capture_output=True, text=True, timeout=30, cwd=Path.cwd()
        )

        # Display output
        if result.stdout:
            console.print(result.stdout, style=COLORS["dim"], markup=False)
        if result.stderr:
            console.print(result.stderr, style="red", markup=False)

        # Show return code if non-zero
        if result.returncode != 0:
            console.print(f"[dim]Exit code: {result.returncode}[/dim]")

        console.print()
        return True

    except subprocess.TimeoutExpired:
        toast("Command timed out after 30 seconds", kind="error")
        console.print()
        return True
    except Exception as e:
        toast(f"Error executing command: {e}", kind="error")
        console.print()
        return True
