"""Main entry point and CLI loop for the Deepdiver CLI."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from strands_tools import editor, environment, file_read, file_write, http_request, shell,calculator,current_time

from .agent import create_agent_with_config, list_agents, reset_agent
from .commands import execute_bash_command, handle_command
from .config import COLORS, DEEPDIVER_ASCII, SessionState, console, create_model
from .csv_tool import filter_csv_data
from .execution import execute_task
from .input import create_prompt_session
from .mcp_tools import load_mcp_tools
from .skills import execute_skills_command, setup_skills_parser
from .subagents.commands import execute_subagents_command, setup_subagents_parser
from .subagents.tools import delegate_to_subagent, delegate_to_subagents_parallel
from .ui import show_help

DEFAULT_TOOLS = [
    file_read,
    file_write,
    editor,
    shell,
    http_request,
    environment,
    calculator,
    current_time,
    filter_csv_data,
    delegate_to_subagent,
    delegate_to_subagents_parallel,
]


def check_cli_dependencies():
    """Check if CLI optional dependencies are installed."""
    missing = []

    try:
        import rich
    except ImportError:
        missing.append("rich")

    try:
        import requests
    except ImportError:
        missing.append("requests")

    try:
        import dotenv
    except ImportError:
        missing.append("python-dotenv")

    try:
        import prompt_toolkit
    except ImportError:
        missing.append("prompt-toolkit")

    if missing:
        print("\n❌ Missing required CLI dependencies!")
        print("\nThe following packages are required to use the CLI:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nInstall the development dependencies with:")
        print("  uv sync")
        print("\n(If a published package becomes available later, install it via `pip install deepdiver-cli`.)")
        sys.exit(1)


def _env_auto_approve() -> bool:
    value = os.environ.get("DEEPDIVER_AUTO_APPROVE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Deepdiver - AI Innovation Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    subparsers.add_parser("list", help="List all available agents")

    # Help command
    subparsers.add_parser("help", help="Show help information")

    # Reset command
    reset_parser = subparsers.add_parser("reset", help="Reset an agent")
    reset_parser.add_argument("--agent", required=True, help="Name of agent to reset")
    reset_parser.add_argument(
        "--target", dest="source_agent", help="Copy prompt from another agent"
    )

    # Skills command
    setup_skills_parser(subparsers)

    # Subagents command
    setup_subagents_parser(subparsers)

    # Default interactive mode
    parser.add_argument(
        "--agent",
        default="agent",
        help="Agent identifier for separate memory stores (default: agent).",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve tool usage without prompting (disables human-in-the-loop)",
    )

    return parser.parse_args()


async def simple_cli(agent, assistant_id: str | None, session_state):
    """Main CLI loop."""
    console.clear()
    console.print(DEEPDIVER_ASCII, style=f"bold {COLORS['primary']}")
    console.print()

    console.print("... Ready to Innovation! What would you like to create?", style=COLORS["agent"])
    console.print(f"  [dim]Working directory: {Path.cwd()}[/dim]")
    console.print()

    if session_state.auto_approve:
        console.print(
            "  [yellow]⚡ Auto-approve: ON[/yellow] [dim](tools run without confirmation)[/dim]"
        )
        console.print()

    console.print(
        "  Tips: Enter to submit, Alt+Enter for newline, Ctrl+E for editor, Ctrl+T to toggle auto-approve, Ctrl+C to interrupt",
        style=f"dim {COLORS['dim']}",
    )
    console.print()

    # Create prompt session
    session = create_prompt_session(assistant_id, session_state)

    while True:
        try:
            user_input = await session.prompt_async()
            user_input = user_input.strip()
        except EOFError:
            break
        except KeyboardInterrupt:
            # Ctrl+C at prompt - exit the program
            console.print("\nGoodbye!", style=COLORS["primary"])
            # Return to allow cleanup
            os._exit(0)

        if not user_input:
            continue

        # Check for slash commands first
        if user_input.startswith("/"):
            result = await handle_command(user_input, assistant_id)
            if result == "exit":
                console.print("\nGoodbye!", style=COLORS["primary"])
                # Return to allow cleanup
                os._exit(0)
            if result:
                # Command was handled, continue to next input
                continue

        # Check for bash commands (!)
        if user_input.startswith("!"):
            execute_bash_command(user_input)
            continue

        # Handle regular quit keywords
        if user_input.lower() in ["quit", "exit", "q"]:
            console.print("\nGoodbye!", style=COLORS["primary"])
            # Return to allow cleanup
            os._exit(0)

        await execute_task(user_input, agent, assistant_id, session_state)


async def main(assistant_id: str, session_state):
    """Main entry point."""
    # Create the model (checks API keys)
    model = create_model()

    # Create agent with default tool set
    tools = list(DEFAULT_TOOLS)
    # Add todo tools (class-based tools with @tool decorator)
    #tools.extend(create_todo_write_tools())

    # Load MCP tools from mcp.json if available
    mcp_clients = load_mcp_tools(assistant_id)
    if mcp_clients:
        # MCPClient implements ToolProvider interface, can be added directly
        # Strands Agent will handle initialization automatically
        tools.extend(mcp_clients)

    # Create agent - MCP clients will initialize during agent creation
    # If some MCP servers fail to initialize, they will be skipped automatically
    agent = None
    try:
        agent = create_agent_with_config(model, assistant_id, tools)
    except (ValueError, Exception) as e:
        # If agent creation fails due to tool loading errors, try to continue with available tools
        error_msg = str(e)
        if "Failed to load tool" in error_msg or "MCP" in error_msg:
            console.print(
                "[yellow]Warning: Some MCP servers failed to initialize. "
                "Continuing with available tools...[/yellow]"
            )
            # Try to create agent with just the default tools
            # This is a fallback - ideally Strands should handle this gracefully
            try:
                agent = create_agent_with_config(model, assistant_id, DEFAULT_TOOLS)
            except Exception:
                # If that also fails, raise the original error
                raise e
        else:
            raise

    try:
        await simple_cli(agent, assistant_id, session_state)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}\n")
    finally:
        # Cleanup resources
        # Close the main model if it has a client
        if model and hasattr(model, "client") and hasattr(model.client, "aclose"):
            await model.client.aclose()


def cli_main():
    """Entry point for console script."""
    # Check dependencies first
    check_cli_dependencies()

    try:
        args = parse_args()

        if args.command == "help":
            show_help()
        elif args.command == "list":
            list_agents()
        elif args.command == "reset":
            reset_agent(args.agent, args.source_agent)
        elif args.command == "skills":
            execute_skills_command(args)
        elif args.command == "subagents":
            execute_subagents_command(args)
        else:
            # Create session state from args or env
            session_state = SessionState(
                auto_approve=args.auto_approve or _env_auto_approve()
            )

            # API key validation happens in create_model()
            asyncio.run(main(args.agent, session_state))
    except KeyboardInterrupt:
        # Clean exit on Ctrl+C - suppress ugly traceback
        console.print("\n\n[yellow]Interrupted[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    cli_main()
