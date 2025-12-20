"""Command handlers for slash commands and bash execution."""

import subprocess
from pathlib import Path

from .agent import AGENT_ROOT
from .config import COLORS, DEEPDIVER_ASCII, console, get_current_model_info
from .mcp_tools import get_mcp_server_info
from .ui import show_interactive_help, toast


async def handle_command(command: str, assistant_id: str = "agent") -> str | bool:
    """Handle slash commands. Returns 'exit' to exit, True if handled, False to pass to agent."""
    stripped_command = command.strip().lstrip("/")
    cmd_lower = stripped_command.lower()

    if cmd_lower in ["quit", "exit", "q"]:
        return "exit"

    if cmd_lower == "clear":
        # Clear screen and show fresh UI
        console.clear()
        console.print(DDAWORD_ASCII, style=f"bold {COLORS['primary']}")
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
