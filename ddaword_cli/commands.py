"""Command handlers for slash commands and bash execution."""

import subprocess
from pathlib import Path

from .config import COLORS, DDAWORD_ASCII, console, get_current_model_info
from .ui import show_interactive_help


def handle_command(command: str) -> str | bool:
    """Handle slash commands. Returns 'exit' to exit, True if handled, False to pass to agent."""
    cmd = command.lower().strip().lstrip("/")

    if cmd in ["quit", "exit", "q"]:
        return "exit"

    if cmd == "clear":
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

    if cmd == "help":
        show_interactive_help()
        return True

    if cmd == "model":
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
            console.print("[yellow]No model provider configured.[/yellow]")
            console.print("[dim]Set STRANDS_MODEL_PROVIDER environment variable to configure a model.[/dim]")
        console.print()
        return True

    console.print()
    console.print(f"[yellow]Unknown command: /{cmd}[/yellow]")
    console.print("[dim]Type /help for available commands.[/dim]")
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
        console.print("[red]Command timed out after 30 seconds[/red]")
        console.print()
        return True
    except Exception as e:
        console.print(f"[red]Error executing command: {e}[/red]")
        console.print()
        return True
