"""UI utilities for the Strands CLI."""

from __future__ import annotations

from .config import COLORS, COMMANDS, DDAWORD_ASCII, console


def show_interactive_help() -> None:
    """Show available commands during interactive session."""

    console.print()
    console.print("[bold]Interactive Commands:[/bold]", style=COLORS["primary"])
    console.print()

    for cmd, desc in COMMANDS.items():
        console.print(f"  /{cmd:<12} {desc}", style=COLORS["dim"])

    console.print()
    console.print("[bold]Editing Features:[/bold]", style=COLORS["primary"])
    console.print("  Enter           Submit your message", style=COLORS["dim"])
    console.print(
        "  Alt+Enter/Ctrl+J Insert newline (Option+Enter on Mac, or ESC then Enter)",
        style=COLORS["dim"],
    )
    console.print(
        "  Ctrl+E          Open in external editor (nano by default)", style=COLORS["dim"]
    )
    console.print("  Ctrl+T          Toggle auto-approve mode", style=COLORS["dim"])
    console.print("  Ctrl+C          Cancel input or interrupt agent mid-work", style=COLORS["dim"])
    console.print()
    console.print("[bold]Special Features:[/bold]", style=COLORS["primary"])
    console.print("  @filename       Type @ to inject file contents", style=COLORS["dim"])
    console.print("  /command        Type / to see available commands", style=COLORS["dim"])
    console.print("  !command        Type ! to run shell commands", style=COLORS["dim"])
    console.print()


def show_help() -> None:
    """Show help information."""

    console.print()
    console.print(DDAWORD_ASCII, style=f"bold {COLORS['primary']}")
    console.print()

    console.print("[bold]Usage:[/bold]", style=COLORS["primary"])
    console.print("  ddaword [--agent NAME] [--auto-approve]        Start interactive session")
    console.print("  ddaword list                                   List available agents")
    console.print("  ddaword reset --agent AGENT                    Reset agent prompt")
    console.print("  ddaword help                                   Show help message")
    console.print()

    console.print("[bold]Agent Storage:[/bold]", style=COLORS["primary"])
    console.print(
        "  Agents are stored in: ~/.strands-agents-cli/AGENT_NAME/", style=COLORS["dim"]
    )
    console.print(
        "  Each agent has an agent.md file and an optional memories/ directory",
        style=COLORS["dim"],
    )
    console.print()

    console.print("[bold]Interactive Features:[/bold]", style=COLORS["primary"])
    console.print("  Enter           Submit your message", style=COLORS["dim"])
    console.print(
        "  Alt+Enter/Ctrl+J Insert newline (Option+Enter or ESC then Enter)",
        style=COLORS["dim"],
    )
    console.print("  Ctrl+E          Open in external editor", style=COLORS["dim"])
    console.print("  Ctrl+T          Toggle auto-approve mode", style=COLORS["dim"])
    console.print("  @filename       Auto-complete file paths to inject context", style=COLORS["dim"])
    console.print()

    console.print("[bold]Interactive Commands:[/bold]", style=COLORS["primary"])
    console.print("  /help           Show this summary", style=COLORS["dim"])
    console.print("  /clear          Clear screen", style=COLORS["dim"])
    console.print("  /quit, /exit    Exit the session", style=COLORS["dim"])
    console.print()
