"""Configuration, constants, and model creation for the CLI."""

import json
import os
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Optional

import dotenv

from rich.console import Console
from rich.live import Live

dotenv.load_dotenv()

THEMES = {
    "dark": {
        "primary": "#38bdf8",
        "dim": "#64748b",
        "user": "#e2e8f0",
        "agent": "#e2e8f0",
        "thinking": "#38bdf8",
        "tool": "#fbbf24",
        "success": "#22c55e",
        "warning": "#f59e0b",
        "error": "#ef4444",
        "info": "#38bdf8",
        "panel_border": "#334155",
        "panel_title": "#94a3b8",
        "prompt": "#e2e8f0",
        "prompt_cont": "#94a3b8",
        "toolbar_ok_bg": "#10b981",
        "toolbar_ok_fg": "#0b0f14",
        "toolbar_warn_bg": "#f59e0b",
        "toolbar_warn_fg": "#0b0f14",
        "toolbar_bash_bg": "#ec4899",
        "toolbar_bash_fg": "#0b0f14",
        "toolbar_dim_fg": "#94a3b8",
    },
    "white": {
        "primary": "#1d4ed8",
        "dim": "#6b7280",
        "user": "#111827",
        "agent": "#111827",
        "thinking": "#1d4ed8",
        "tool": "#d97706",
        "success": "#16a34a",
        "warning": "#d97706",
        "error": "#dc2626",
        "info": "#2563eb",
        "panel_border": "#d1d5db",
        "panel_title": "#374151",
        "prompt": "#111827",
        "prompt_cont": "#6b7280",
        "toolbar_ok_bg": "#22c55e",
        "toolbar_ok_fg": "#0b0f14",
        "toolbar_warn_bg": "#f59e0b",
        "toolbar_warn_fg": "#0b0f14",
        "toolbar_bash_bg": "#ec4899",
        "toolbar_bash_fg": "#0b0f14",
        "toolbar_dim_fg": "#6b7280",
    },
    "gray": {
        "primary": "#9ca3af",
        "dim": "#6b7280",
        "user": "#e5e7eb",
        "agent": "#e5e7eb",
        "thinking": "#cbd5f5",
        "tool": "#fbbf24",
        "success": "#86efac",
        "warning": "#fbbf24",
        "error": "#f87171",
        "info": "#9ca3af",
        "panel_border": "#4b5563",
        "panel_title": "#9ca3af",
        "prompt": "#e5e7eb",
        "prompt_cont": "#9ca3af",
        "toolbar_ok_bg": "#22c55e",
        "toolbar_ok_fg": "#0b0f14",
        "toolbar_warn_bg": "#f59e0b",
        "toolbar_warn_fg": "#0b0f14",
        "toolbar_bash_bg": "#ec4899",
        "toolbar_bash_fg": "#0b0f14",
        "toolbar_dim_fg": "#9ca3af",
    },
    "mono": {
        "primary": "#e5e7eb",
        "dim": "#9ca3af",
        "user": "#f3f4f6",
        "agent": "#f3f4f6",
        "thinking": "#d4d4d4",
        "tool": "#d4d4d4",
        "success": "#d4d4d4",
        "warning": "#d4d4d4",
        "error": "#f87171",
        "info": "#e5e7eb",
        "panel_border": "#6b7280",
        "panel_title": "#d4d4d4",
        "prompt": "#f3f4f6",
        "prompt_cont": "#9ca3af",
        "toolbar_ok_bg": "#9ca3af",
        "toolbar_ok_fg": "#0b0f14",
        "toolbar_warn_bg": "#9ca3af",
        "toolbar_warn_fg": "#0b0f14",
        "toolbar_bash_bg": "#9ca3af",
        "toolbar_bash_fg": "#0b0f14",
        "toolbar_dim_fg": "#9ca3af",
    },
    "monokai": {
        "primary": "#66d9ef",
        "dim": "#75715e",
        "user": "#f8f8f2",
        "agent": "#f8f8f2",
        "thinking": "#a6e22e",
        "tool": "#fd971f",
        "success": "#a6e22e",
        "warning": "#fd971f",
        "error": "#f92672",
        "info": "#66d9ef",
        "panel_border": "#3b3a32",
        "panel_title": "#a6e22e",
        "prompt": "#f8f8f2",
        "prompt_cont": "#75715e",
        "toolbar_ok_bg": "#a6e22e",
        "toolbar_ok_fg": "#272822",
        "toolbar_warn_bg": "#fd971f",
        "toolbar_warn_fg": "#272822",
        "toolbar_bash_bg": "#f92672",
        "toolbar_bash_fg": "#272822",
        "toolbar_dim_fg": "#75715e",
    },
}

# Color scheme (active theme)
COLORS = dict(THEMES["dark"])
_CURRENT_THEME = "dark"


DEEPDIVER_ASCII = """

 ██████╗  ███████╗ ███████╗ ██████╗      ██████╗  ██╗ ██╗   ██╗ ███████╗ ██████╗ 
 ██╔══██╗ ██╔════╝ ██╔════╝ ██╔══██╗     ██╔══██╗ ██║ ██║   ██║ ██╔════╝ ██╔══██╗
 ██║  ██║ █████╗   █████╗   ██████╔╝     ██║  ██║ ██║ ██║   ██║ █████╗   ██████╔╝
 ██║  ██║ ██╔══╝   ██╔══╝   ██╔═══╝      ██║  ██║ ██║ ╚██╗ ██╔╝ ██╔══╝   ██╔══██╗
 ██████╔╝ ███████╗ ███████╗ ██║          ██████╔╝ ██║  ╚████╔╝  ███████╗ ██║  ██║
 ╚═════╝  ╚══════╝ ╚══════╝ ╚═╝          ╚═════╝  ╚═╝   ╚═══╝   ╚══════╝ ╚═╝  ╚═╝

"""

COMMANDS = {
    "clear": "Clear screen",
    "help": "Show help information",
    "model": "Show current model provider and name",
    "mcp": "Show configured MCP servers",
    "theme": "List or change UI theme",
    "skills": "List or show available skills",
    "subagents": "List or run available subagents",
    "agents": "Alias for subagents",
    "quit": "Exit the CLI",
    "exit": "Exit the CLI",
}

# Maximum argument length for display
MAX_ARG_LENGTH = 150

# Rich console instance
console = Console(highlight=False, force_terminal=True)

# Liveインスタンスを共有（Live表示と入力処理の競合回避用）
current_live: Optional[Live] = None


def get_theme_name() -> str:
    return _CURRENT_THEME


def get_theme_names() -> list[str]:
    return sorted(THEMES.keys())


def apply_theme(name: str) -> bool:
    """Apply a theme by name to the active color map."""
    global _CURRENT_THEME
    theme_key = (name or "").strip().lower()
    if theme_key not in THEMES:
        return False
    COLORS.clear()
    COLORS.update(THEMES[theme_key])
    _CURRENT_THEME = theme_key
    return True


_env_theme = os.environ.get("DEEPDIVER_THEME")
if _env_theme:
    apply_theme(_env_theme)


def set_live(live: Optional[Live]) -> None:
    """Set the current Live instance for shared state management."""
    global current_live
    current_live = live


class SessionState:
    """Holds mutable session state (auto-approve mode, etc)."""

    def __init__(self, auto_approve: bool = False, theme: str | None = None):
        self.auto_approve = auto_approve
        self.theme = theme or get_theme_name()
        self.thinking_status: str | None = None  # "AI Thinking..." など
        self.tool_status: str | None = None  # "Tool executing: {name}..." など
        self._status_obj = None  # rich.status.Status オブジェクト
        self.prompt_session = None

    def toggle_auto_approve(self) -> bool:
        """Toggle auto-approve and return new state."""
        self.auto_approve = not self.auto_approve
        return self.auto_approve

    def set_theme(self, name: str) -> bool:
        """Set theme for the session and update global colors."""
        if not apply_theme(name):
            return False
        self.theme = get_theme_name()
        return True
    
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
                spinner="dots"
            )
            self._status_obj.start()
        elif self.thinking_status:
            self._status_obj = console.status(
                f"[{COLORS['thinking']}] {self.thinking_status}[/]",
                spinner="dots"
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
    elif provider == "ollama":
        host = os.environ.get("OLLAMA_HOST")
        if host:
            config["host"] = host

        model_id = os.environ.get("OLLAMA_MODEL_ID") or os.environ.get("OLLAMA_MODEL")
        if model_id:
            config["model_id"] = model_id
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
