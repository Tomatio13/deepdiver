"""Configuration, constants, and model creation for the CLI."""

import json
import os
from pathlib import Path
from typing import Any

import dotenv
from rich.console import Console

dotenv.load_dotenv()

# Color scheme
COLORS = {
    "primary": "#e8383b",
    "dim": "#6b7280",
    "user": "#ffffff",
    "agent": "#e8383b",
    "thinking": "#34d399",
    "tool": "#fbbf24",
}

# ASCII art banner
# DDAWORD_ASCII = """
#  ██████╗  ███████╗ ███████╗ ██████╗
#  ██╔══██╗ ██╔════╝ ██╔════╝ ██╔══██╗
#  ██║  ██║ █████╗   █████╗   ██████╔╝
#  ██║  ██║ ██╔══╝   ██╔══╝   ██╔═══╝
#  ██████╔╝ ███████╗ ███████╗ ██║
#  ╚═════╝  ╚══════╝ ╚══════╝ ╚═╝

#   █████╗   ██████╗  ███████╗ ███╗   ██╗ ████████╗ ███████╗
#  ██╔══██╗ ██╔════╝  ██╔════╝ ████╗  ██║ ╚══██╔══╝ ██╔════╝
#  ███████║ ██║  ███╗ █████╗   ██╔██╗ ██║    ██║    ███████╗
#  ██╔══██║ ██║   ██║ ██╔══╝   ██║╚██╗██║    ██║    ╚════██║
#  ██║  ██║ ╚██████╔╝ ███████╗ ██║ ╚████║    ██║    ███████║
#  ╚═╝  ╚═╝  ╚═════╝  ╚══════╝ ╚═╝  ╚═══╝    ╚═╝    ╚══════╝
# """

DDAWORD_ASCII = """

 ███████╗ ██╗   ██╗      ██╗ ██╗ ████████╗ ███████╗ ██╗   ██╗
 ██╔════╝ ██║   ██║      ██║ ██║ ╚══██╔══╝ ██╔════╝ ██║   ██║
 █████╗   ██║   ██║      ██║ ██║    ██║    ███████╗ ██║   ██║
 ██╔══╝   ██║   ██║ ██   ██║ ██║    ██║    ╚════██║ ██║   ██║
 ██║      ╚██████╔╝ ╚█████╔╝ ██║    ██║    ███████║ ╚██████╔╝
 ╚═╝       ╚═════╝   ╚════╝  ╚═╝    ╚═╝    ╚══════╝  ╚═════╝ 

 ██████╗  ██████╗   █████╗  ██╗    ██╗  ██████╗  ██████╗  ██████╗ 
 ██╔══██╗ ██╔══██╗ ██╔══██╗ ██║    ██║ ██╔═══██╗ ██╔══██╗ ██╔══██╗
 ██║  ██║ ██║  ██║ ███████║ ██║ █╗ ██║ ██║   ██║ ██████╔╝ ██║  ██║
 ██║  ██║ ██║  ██║ ██╔══██║ ██║███╗██║ ██║   ██║ ██╔══██╗ ██║  ██║
 ██████╔╝ ██████╔╝ ██║  ██║ ╚███╔███╔╝ ╚██████╔╝ ██║  ██║ ██████╔╝
 ╚═════╝  ╚═════╝  ╚═╝  ╚═╝  ╚══╝╚══╝   ╚═════╝  ╚═╝  ╚═╝ ╚═════╝ 
 """

# Interactive commands
COMMANDS = {
    "clear": "Clear screen",
    "help": "Show help information",
    "tokens": "Show token usage for current session",
    "quit": "Exit the CLI",
    "exit": "Exit the CLI",
}


# Maximum argument length for display
MAX_ARG_LENGTH = 150

# Rich console instance
console = Console(highlight=False)


class SessionState:
    """Holds mutable session state (auto-approve mode, etc)."""

    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve

    def toggle_auto_approve(self) -> bool:
        """Toggle auto-approve and return new state."""
        self.auto_approve = not self.auto_approve
        return self.auto_approve


def get_default_coding_instructions() -> str:
    """Get the default coding agent instructions.

    These are the immutable base instructions that cannot be modified by the agent.
    Long-term memory (agent.md) is handled separately by the middleware.
    """
    default_prompt_path = Path(__file__).parent / "default_agent_prompt.md"
    return default_prompt_path.read_text()


MODEL_CLASS_BY_PROVIDER = {
    "bedrock": "BedrockModel",
    "openai": "OpenAIModel",
    "anthropic": "AnthropicModel",
    "ollama": "OllamaModel",
}

SENSITIVE_KEYS = {"api_key", "secret", "token", "access_key"}


def _load_model_config(raw_value: str | None, provider: str) -> dict[str, Any]:
    config: dict[str, Any] = {}

    if provider == "bedrock":
        model_id = os.environ.get("BEDROCK_MODEL_ID") or os.environ.get("STRANDS_MODEL_ID")
        region = os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION")
        if model_id:
            config["model_id"] = model_id
        if region:
            config["region_name"] = region
    elif provider == "openai":
        if os.environ.get("OPENAI_MODEL"):
            config["model"] = os.environ["OPENAI_MODEL"]
        if os.environ.get("OPENAI_API_KEY"):
            config["api_key"] = os.environ["OPENAI_API_KEY"]
    elif provider == "anthropic":
        if os.environ.get("ANTHROPIC_MODEL"):
            config["model"] = os.environ["ANTHROPIC_MODEL"]
        if os.environ.get("ANTHROPIC_API_KEY"):
            config["api_key"] = os.environ["ANTHROPIC_API_KEY"]

    if not raw_value:
        return config

    candidate_path = Path(raw_value)
    try:
        if candidate_path.exists():
            loaded = json.loads(candidate_path.read_text())
        else:
            loaded = json.loads(raw_value)
        if isinstance(loaded, dict):
            config.update(loaded)
    except json.JSONDecodeError as exc:
        console.print(f"[yellow]Warning: Could not parse STRANDS_MODEL_CONFIG: {exc}[/yellow]")

    return config


def _sanitize_config_for_display(config: dict[str, Any]) -> dict[str, Any]:
    sanitised: dict[str, Any] = {}
    for key, value in config.items():
        if any(token in key.lower() for token in SENSITIVE_KEYS):
            sanitised[key] = "***"
        else:
            sanitised[key] = value
    return sanitised


def create_model():
    """Create a Strands model instance based on environment configuration."""

    provider = os.environ.get("STRANDS_MODEL_PROVIDER")
    if not provider:
        console.print(
            "[dim]STRANDS_MODEL_PROVIDER not set. Relying on Agent defaults for model selection.[/dim]"
        )
        return None

    provider = provider.lower()
    class_name = MODEL_CLASS_BY_PROVIDER.get(provider)
    if not class_name:
        console.print(f"[yellow]Unknown STRANDS_MODEL_PROVIDER '{provider}'.[/yellow]")
        return None

    config_value = os.environ.get("STRANDS_MODEL_CONFIG")
    model_config = _load_model_config(config_value, provider)

    try:
        module = __import__("strands", fromlist=[class_name])
        model_cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        console.print(f"[red]Failed to load {class_name}: {exc}[/red]")
        return None

    try:
        model = model_cls(**model_config)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error creating model: {exc}[/red]")
        return None

    sanitised = _sanitize_config_for_display(model_config)
    console.print(
        f"[dim]Using provider '{provider}' with config: {sanitised}[/dim]"
    )
    return model
