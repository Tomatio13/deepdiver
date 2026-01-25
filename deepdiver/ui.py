"""UI utilities for the Strands CLI."""

from __future__ import annotations

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import COLORS, COMMANDS, DEEPDIVER_ASCII, console

# ToDo表示用のアイコンとスタイル
TODO_ICON = {"pending": "○", "in_progress": "◔", "done": "✓", "completed": "✓"}


def normalize_todos(todos: list[dict]) -> list[dict]:
    """Normalize todos list, handling blocking states.
    
    If a todo is not completed, subsequent todos are marked as pending
    (blocked by incomplete tasks).
    
    Args:
        todos: List of todo dictionaries with 'status' and 'content' keys
        
    Returns:
        Normalized list of todos with adjusted statuses
    """
    blocked = False
    output = []
    for todo in todos:
        status = todo.get("status", "pending")
        # Map "done" to "completed" for consistency
        if status == "done":
            status = "completed"
        
        # If we've encountered an incomplete task, mark subsequent as pending
        if blocked and status != "completed":
            status = "pending"
        
        # Track if we've seen an incomplete task
        if status != "completed":
            blocked = True
        
        output.append({**todo, "status": status})
    return output


def render_todos_panel(todos: list[dict] | None = None, max_completed: int = 5) -> Panel:
    """Render a todos list as a Rich Panel.
    
    Args:
        todos: List of todo dictionaries. Each dict should have:
            - 'content': Task description
            - 'status': "pending", "in_progress", "done", or "completed"
            - 'activeForm': (optional) Active form of the task
        max_completed: Maximum number of completed tasks to show (default: 5)
            
    Returns:
        Panel with formatted todos table
    """
    if not todos:
        todos = []
    
    todos = normalize_todos(todos)
    
    # Separate completed and active tasks
    completed_indices = []
    active_indices = []
    
    for idx, item in enumerate(todos):
        status = item.get("status", "pending")
        if status == "done": 
            status = "completed"
        
        if status == "completed":
            completed_indices.append(idx)
        else:
            active_indices.append(idx)
            
    # Determine which completed tasks to hide
    hidden_count = 0
    show_indices = set(active_indices)
    
    if len(completed_indices) > max_completed:
        hidden_count = len(completed_indices) - max_completed
        # Show only the last max_completed items
        show_indices.update(completed_indices[-max_completed:])
    else:
        show_indices.update(completed_indices)
        
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", width=3, no_wrap=True)
    table.add_column()
    
    # Add hidden tasks summary if needed
    if hidden_count > 0:
        table.add_row("", Text(f"... {hidden_count} completed tasks hidden ...", style="dim italic"))
    
    todo_style = {
        "pending": COLORS["dim"],
        "in_progress": COLORS["warning"],
        "done": COLORS["success"],
        "completed": COLORS["success"],
    }

    for idx, item in enumerate(todos, 1):
        if (idx - 1) not in show_indices:
            continue
            
        status = item.get("status", "pending")
        # Map "done" to "completed" for display
        if status == "done":
            status = "completed"
        
        content = item.get("content", item.get("activeForm", "(empty)"))
        text = Text(content, style=todo_style.get(status, COLORS["dim"]))
        
        # Strike through completed items
        if status == "completed":
            text.stylize("strike")
        
        icon = TODO_ICON.get(status, "○")
        icon_text = Text(icon + " ", style=todo_style.get(status, COLORS["dim"]))
        
        table.add_row(f"{idx}.", Text.assemble(icon_text, text))
    
    title = f"[{COLORS['panel_title']}]TODOs[/]"
    return Panel(
        table,
        title=title,
        border_style=COLORS["panel_border"],
        box=box.ROUNDED,
        padding=(1, 1),
    )


def diff_todos(before: list[dict], after: list[dict]) -> list[str]:
    """Calculate differences between two todo lists.
    
    Args:
        before: Previous todo list
        after: Current todo list
        
    Returns:
        List of change descriptions
    """
    changes = []
    before_normalized = normalize_todos(before)
    after_normalized = normalize_todos(after)
    
    # Compare todos by index
    max_len = max(len(before_normalized), len(after_normalized))
    for idx in range(max_len):
        prev = before_normalized[idx] if idx < len(before_normalized) else None
        curr = after_normalized[idx] if idx < len(after_normalized) else None
        
        if prev is None:
            # New todo added
            changes.append(f"[{idx + 1}] Added: {curr.get('content', '')}")
        elif curr is None:
            # Todo removed
            changes.append(f"[{idx + 1}] Removed: {prev.get('content', '')}")
        elif prev.get("status") != curr.get("status"):
            # Status changed
            prev_status = prev.get("status", "pending")
            curr_status = curr.get("status", "pending")
            changes.append(
                f"[{idx + 1}] {curr.get('content', '')} -> {prev_status} → {curr_status}"
            )
    
    return changes


def toast(message: str, kind: str = "info") -> None:
    """Display a toast notification panel.
    
    Args:
        message: Message to display
        kind: Type of notification - "success", "warning", "error", or "info" (default)
    """
    color = {
        "success": COLORS["success"],
        "warning": COLORS["warning"],
        "error": COLORS["error"],
    }.get(kind, COLORS["info"])
    console.print(Panel.fit(Text(message, style=color), border_style=COLORS["panel_border"]))


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
    console.print(DEEPDIVER_ASCII, style=f"{COLORS['primary']}")
    console.print()

    console.print("[bold]Usage:[/bold]", style=COLORS["primary"])
    console.print("  deepdiver [--agent NAME] [--auto-approve]      Start interactive session")
    console.print("  deepdiver list                                 List available agents")
    console.print("  deepdiver reset --agent AGENT                  Reset agent prompt")
    console.print("  deepdiver help                                 Show help message")
    console.print()

    console.print("[bold]Agent Storage:[/bold]", style=COLORS["primary"])
    console.print(
        "  Agents are stored in: ~/.deepdiver/AGENT_NAME/", style=COLORS["dim"]
    )
    console.print(
        "  Each agent has an AGENT.md file and an optional memories/ directory",
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
    console.print("  /skills         List or show skills", style=COLORS["dim"])
    console.print("  /voice          Record and transcribe audio into the next prompt", style=COLORS["dim"])
    console.print("  /quit, /exit    Exit the session", style=COLORS["dim"])
    console.print()
