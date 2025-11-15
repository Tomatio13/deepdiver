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
    "primary": "#00bfff",
    "dim": "#6b7280",
    "user": "#ffffff",
    "agent": "#00bfff",
    "thinking": "#34d399",
    "tool": "#fbbf24",
}

# ASCII art banner
# DDAWORD_ASCII= """
#  ███████╗ ██╗   ██╗      ██╗ ██╗ ████████╗ ███████╗ ██╗   ██╗
#  ██╔════╝ ██║   ██║      ██║ ██║ ╚══██╔══╝ ██╔════╝ ██║   ██║
#  █████╗   ██║   ██║      ██║ ██║    ██║    ███████╗ ██║   ██║
#  ██╔══╝   ██║   ██║ ██   ██║ ██║    ██║    ╚════██║ ██║   ██║
#  ██║      ╚██████╔╝ ╚█████╔╝ ██║    ██║    ███████║ ╚██████╔╝
#  ╚═╝       ╚═════╝   ╚════╝  ╚═╝    ╚═╝    ╚══════╝  ╚═════╝ 

#  ██╗ ███╗   ██╗ ███╗   ██╗  ██████╗  ██╗   ██╗  █████╗  ████████╗ ███████╗      █████╗  ██╗
#  ██║ ████╗  ██║ ████╗  ██║ ██╔═══██╗ ██║   ██║ ██╔══██╗ ╚══██╔══╝ ██╔════╝     ██╔══██╗ ██║
#  ██║ ██╔██╗ ██║ ██╔██╗ ██║ ██║   ██║ ██║   ██║ ███████║    ██║    █████╗       ███████║ ██║
#  ██║ ██║╚██╗██║ ██║╚██╗██║ ██║   ██║ ╚██╗ ██╔╝ ██╔══██║    ██║    ██╔══╝       ██╔══██║ ██║
#  ██║ ██║ ╚████║ ██║ ╚████║ ╚██████╔╝  ╚████╔╝  ██║  ██║    ██║    ███████╗ ██╗ ██║  ██║ ██║
#  ╚═╝ ╚═╝  ╚═══╝ ╚═╝  ╚═══╝  ╚═════╝    ╚═══╝   ╚═╝  ╚═╝    ╚═╝    ╚══════╝ ╚═╝ ╚═╝  ╚═╝ ╚═╝
# """
DDAWORD_ASCII= """

 ██████╗   █████╗  ████████╗  █████╗ 
 ██╔══██╗ ██╔══██╗ ╚══██╔══╝ ██╔══██╗
 ██║  ██║ ███████║    ██║    ███████║
 ██║  ██║ ██╔══██║    ██║    ██╔══██║
 ██████╔╝ ██║  ██║    ██║    ██║  ██║
 ╚═════╝  ╚═╝  ╚═╝    ╚═╝    ╚═╝  ╚═╝

 ██████╗  ███████╗ ███████╗ ██████╗      ██████╗  ██╗ ██╗   ██╗ ███████╗
 ██╔══██╗ ██╔════╝ ██╔════╝ ██╔══██╗     ██╔══██╗ ██║ ██║   ██║ ██╔════╝
 ██║  ██║ █████╗   █████╗   ██████╔╝     ██║  ██║ ██║ ██║   ██║ █████╗  
 ██║  ██║ ██╔══╝   ██╔══╝   ██╔═══╝      ██║  ██║ ██║ ╚██╗ ██╔╝ ██╔══╝  
 ██████╔╝ ███████╗ ███████╗ ██║          ██████╔╝ ██║  ╚████╔╝  ███████╗
 ╚═════╝  ╚══════╝ ╚══════╝ ╚═╝          ╚═════╝  ╚═╝   ╚═══╝   ╚══════╝
"""

# Interactive commands
COMMANDS = {
    "clear": "Clear screen",
    "help": "Show help information",
    "model": "Show current model provider and name",
    "mcp": "Show configured MCP servers",
    "quit": "Exit the CLI",
    "exit": "Exit the CLI",
}

# Consulting subcommands
CONSULTING_COMMANDS = {
    "init": "分析を初期化し、作業ディレクトリを作成",
    "hypothesis": "仮説を生成 <project_name>",
    "process-data": "データを整理・加工 <project_name>",
    "validate": "仮説を検証 <project_name>",
    "strategy": "戦略を立案 <project_name>",
    "report": "レポートを生成 <project_name>",
    "status": "現在の状態を表示 [project_name]",
    "approve": "現在のステップを承認 <project_name>",
    "reject": "現在のステップを否決 <project_name>",
}


# Maximum argument length for display
MAX_ARG_LENGTH = 150

# Rich console instance
console = Console(highlight=False, force_terminal=True)


class SessionState:
    """Holds mutable session state (auto-approve mode, etc)."""

    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve
        self.thinking_status: str | None = None  # "AI Thinking..." など
        self.tool_status: str | None = None  # "Tool executing: {name}..." など
        self._status_obj = None  # rich.status.Status オブジェクト

    def toggle_auto_approve(self) -> bool:
        """Toggle auto-approve and return new state."""
        self.auto_approve = not self.auto_approve
        return self.auto_approve
    
    def set_thinking_status(self, message: str | None) -> None:
        """Set thinking status message."""
        self.thinking_status = message
        self._update_status_display()
    
    def set_tool_status(self, message: str | None) -> None:
        """Set tool execution status message."""
        self.tool_status = message
        self._update_status_display()
    
    def _update_status_display(self) -> None:
        """Update the status display using rich.status.Status."""
        from rich.status import Status
        
        # 既存のステータスを停止
        if self._status_obj:
            self._status_obj.stop()
            self._status_obj = None
        
        # 新しいステータスを開始
        if self.tool_status:
            self._status_obj = console.status(
                f"[{COLORS['tool']}]🔧 {self.tool_status}[/]",
                spinner="aesthetic"
            )
            self._status_obj.start()
        elif self.thinking_status:
            self._status_obj = console.status(
                f"[{COLORS['thinking']}]📡 {self.thinking_status}[/]",
                spinner="aesthetic"
            )
            self._status_obj.start()
    
    def clear_status(self) -> None:
        """Clear all status messages."""
        self.thinking_status = None
        self.tool_status = None
        if self._status_obj:
            self._status_obj.stop()
            self._status_obj = None


def get_default_coding_instructions() -> str:
    """Get the default coding agent instructions.

    These are the immutable base instructions that cannot be modified by the agent.
    Long-term memory (agent.md) is handled separately by the middleware.
    """
    default_prompt_path = Path(__file__).parent / "default_agent_prompt.md"
    return default_prompt_path.read_text()


MODEL_CLASS_BY_PROVIDER = {
    "bedrock": ("strands.models.bedrock", "BedrockModel"),
    "openai": ("strands.models.openai", "OpenAIModel"),
    "anthropic": ("strands.models.anthropic", "AnthropicModel"),
    "ollama": ("strands.models.ollama", "OllamaModel"),
    "gemini": ("strands.models.gemini", "GeminiModel"),
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
        # OpenAI互換プロバイダ（LiteLLMなど）に対応
        # client_argsにapi_keyとbase_urlを設定
        client_args: dict[str, Any] = {}
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            client_args["api_key"] = api_key
        
        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url:
            client_args["base_url"] = base_url
        
        if client_args:
            config["client_args"] = client_args
        
        # model_idを設定（OPENAI_MODELまたはOPENAI_MODEL_IDから取得）
        model_id = os.environ.get("OPENAI_MODEL_ID") or os.environ.get("OPENAI_MODEL")
        if model_id:
            config["model_id"] = model_id
    elif provider == "anthropic":
        if os.environ.get("ANTHROPIC_MODEL"):
            config["model"] = os.environ["ANTHROPIC_MODEL"]
        if os.environ.get("ANTHROPIC_API_KEY"):
            config["api_key"] = os.environ["ANTHROPIC_API_KEY"]
    elif provider == "gemini":
        # Geminiプロバイダの設定
        # client_argsにapi_keyを設定
        client_args: dict[str, Any] = {}
        
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            client_args["api_key"] = api_key
        
        if client_args:
            config["client_args"] = client_args
        
        # model_idを設定（GEMINI_MODEL_IDまたはGEMINI_MODELから取得）
        model_id = os.environ.get("GEMINI_MODEL_ID") or os.environ.get("GEMINI_MODEL")
        if model_id:
            config["model_id"] = model_id

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
        elif key == "client_args" and isinstance(value, dict):
            # client_args内の機密情報もサニタイズ
            sanitised_client_args: dict[str, Any] = {}
            for client_key, client_value in value.items():
                if any(token in client_key.lower() for token in SENSITIVE_KEYS):
                    sanitised_client_args[client_key] = "***"
                else:
                    sanitised_client_args[client_key] = client_value
            sanitised[key] = sanitised_client_args
        else:
            sanitised[key] = value
    return sanitised


def get_current_model_info() -> dict[str, str | None]:
    """Get current model provider and model name from environment configuration.
    
    Returns:
        Dictionary with 'provider' and 'model_name' keys.
    """
    provider = os.environ.get("STRANDS_MODEL_PROVIDER")
    if not provider:
        return {"provider": None, "model_name": None}
    
    provider = provider.lower()
    model_name = None
    
    if provider == "bedrock":
        model_name = os.environ.get("BEDROCK_MODEL_ID") or os.environ.get("STRANDS_MODEL_ID")
    elif provider == "openai":
        model_name = os.environ.get("OPENAI_MODEL_ID") or os.environ.get("OPENAI_MODEL")
    elif provider == "anthropic":
        model_name = os.environ.get("ANTHROPIC_MODEL")
    elif provider == "ollama":
        # Ollama typically uses OLLAMA_MODEL or model config
        model_name = os.environ.get("OLLAMA_MODEL")
    elif provider == "gemini":
        model_name = os.environ.get("GEMINI_MODEL_ID") or os.environ.get("GEMINI_MODEL")
    
    # Check STRANDS_MODEL_CONFIG for model name if not found above
    if not model_name:
        config_value = os.environ.get("STRANDS_MODEL_CONFIG")
        if config_value:
            try:
                candidate_path = Path(config_value)
                if candidate_path.exists():
                    loaded = json.loads(candidate_path.read_text())
                else:
                    loaded = json.loads(config_value)
                if isinstance(loaded, dict):
                    # Check common model name keys
                    model_name = loaded.get("model") or loaded.get("model_id") or loaded.get("model_name")
            except (json.JSONDecodeError, Exception):
                pass
    
    return {"provider": provider, "model_name": model_name}


def create_model():
    """Create a Strands model instance based on environment configuration."""

    provider = os.environ.get("STRANDS_MODEL_PROVIDER")
    if not provider:
        console.print(
            "[dim]STRANDS_MODEL_PROVIDER not set. Relying on Agent defaults for model selection.[/dim]"
        )
        return None

    provider = provider.lower()
    model_info = MODEL_CLASS_BY_PROVIDER.get(provider)
    if not model_info:
        console.print(f"[yellow]Unknown STRANDS_MODEL_PROVIDER '{provider}'.[/yellow]")
        return None

    module_path, class_name = model_info
    config_value = os.environ.get("STRANDS_MODEL_CONFIG")
    model_config = _load_model_config(config_value, provider)

    try:
        module = __import__(module_path, fromlist=[class_name])
        model_cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        console.print(f"[red]Failed to load {class_name} from {module_path}: {exc}[/red]")
        return None

    try:
        model = model_cls(**model_config)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Error creating model: {exc}[/red]")
        return None

    sanitised = _sanitize_config_for_display(model_config)
    # console.print(
    #     f"[dim]Using provider '{provider}' with config: {sanitised}[/dim]"
    # )
    return model
