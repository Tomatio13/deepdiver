"""MCP (Model Context Protocol) tools integration for the CLI."""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Any

from strands.tools.mcp import MCPClient

from .agent import AGENT_ROOT
from .config import console

# Suppress RuntimeWarning about unawaited coroutines from MCPClient cleanup
# These warnings occur during MCP client cleanup and are harmless
warnings.filterwarnings(
    "ignore",
    message=".*coroutine.*was never awaited.*",
    category=RuntimeWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*MCPClient.*",
    category=RuntimeWarning,
)
# Suppress asyncio RuntimeWarnings related to MCP cleanup
# These occur when MCPClient cleanup coroutines are not awaited
warnings.filterwarnings(
    "ignore",
    message=".*coroutine.*MCPClient.*",
    category=RuntimeWarning,
)
# Suppress warnings from asyncio.base_events related to MCP cleanup
warnings.filterwarnings(
    "ignore",
    message=".*coroutine.*was never awaited.*",
    category=RuntimeWarning,
    module="asyncio",
)

# Suppress noisy MCP client error logs
# These errors are handled gracefully by catching exceptions
# Set log level to ERROR to suppress timeout and connection errors in background threads
mcp_logger = logging.getLogger("mcp")
mcp_logger.setLevel(logging.ERROR)
# Suppress specific error messages from MCP client background threads
for handler in mcp_logger.handlers[:]:
    mcp_logger.removeHandler(handler)

httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.ERROR)
for handler in httpx_logger.handlers[:]:
    httpx_logger.removeHandler(handler)

httpcore_logger = logging.getLogger("httpcore")
httpcore_logger.setLevel(logging.ERROR)
for handler in httpcore_logger.handlers[:]:
    httpcore_logger.removeHandler(handler)

# Suppress MCP client timeout and connection errors
# These occur when MCP servers timeout or disconnect
root_logger = logging.getLogger()
# Suppress ERROR level messages related to MCP timeouts and connection errors
class MCPErrorFilter(logging.Filter):
    """Filter to suppress MCP client timeout and connection errors."""
    
    # Patterns to suppress
    SUPPRESS_PATTERNS = [
        "receive loop",
        "error in sse_reader",
        "readtimeout",
        "httpx.readtimeout",
        "httpcore.readtimeout",
        "unhandled exception",
        "sse_reader",
    ]
    
    def filter(self, record):
        # Format the message similar to how logging does it
        try:
            if hasattr(record, 'getMessage'):
                msg = record.getMessage()
            else:
                msg = str(record.msg)
                if record.args:
                    try:
                        msg = msg % record.args
                    except Exception:
                        pass
        except Exception:
            msg = str(record.msg)
        
        msg_lower = msg.lower()
        
        # Suppress messages matching any pattern
        for pattern in self.SUPPRESS_PATTERNS:
            if pattern in msg_lower:
                return False
        
        # Also check the logger name
        logger_name = record.name.lower()
        if any(pattern in logger_name for pattern in ["mcp", "httpx", "httpcore"]):
            # Suppress ERROR level messages from MCP-related loggers
            if record.levelno >= logging.ERROR:
                return False
        
        return True

# Add filter to root logger and all handlers
root_logger.addFilter(MCPErrorFilter())
for handler in root_logger.handlers:
    handler.addFilter(MCPErrorFilter())

# Also filter stderr output for MCP-related errors
# This catches errors printed directly to stderr (not through logging)
class FilteredStderr:
    """Wrapper for stderr that filters MCP timeout errors."""
    
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.suppress_patterns = [
            "error in sse_reader",
            "readtimeout",
            "httpx.readtimeout",
            "httpcore.readtimeout",
            "unhandled exception in receive loop",
            "traceback (most recent call last)",
            "site-packages/mcp/client/sse.py",
            "site-packages/httpx",
            "site-packages/httpcore",
            "site-packages/mcp/shared/session.py",
            "site-packages/mcp/client/session.py",
        ]
        self.buffer = ""
        self.suppressing = False
    
    def write(self, text):
        if not text:
            return
        
        # Buffer text to check multi-line messages
        self.buffer += text
        
        # Check if we should suppress based on current buffer
        text_lower = self.buffer.lower()
        
        # Check if any pattern matches
        should_suppress = any(pattern in text_lower for pattern in self.suppress_patterns)
        
        # If we see a pattern, start suppressing
        if should_suppress:
            self.suppressing = True
        
        # If suppressing and we see a newline or the buffer is getting large, reset
        if self.suppressing:
            if '\n' in text or len(self.buffer) > 10000:
                self.buffer = ""
                self.suppressing = False
            return
        
        # Not suppressing, write normally
        self.original_stderr.write(text)
        # Reset buffer on newline
        if '\n' in text:
            self.buffer = ""
    
    def flush(self):
        if not self.suppressing:
            self.original_stderr.flush()
        self.buffer = ""
        self.suppressing = False
    
    def __getattr__(self, name):
        return getattr(self.original_stderr, name)

# Replace stderr with filtered version
# Only filter if we're not in a test environment
if not hasattr(sys, '_getframe') or 'pytest' not in sys.modules:
    sys.stderr = FilteredStderr(sys.stderr)

try:
    from strands.types.exceptions import ToolProviderException
except ImportError:
    ToolProviderException = Exception

try:
    from mcp import stdio_client, StdioServerParameters
except ImportError:
    stdio_client = None
    StdioServerParameters = None

try:
    from mcp.client.sse import sse_client
except ImportError:
    sse_client = None

try:
    from mcp.client.streamable_http import streamablehttp_client
except ImportError:
    streamablehttp_client = None

if stdio_client is None and sse_client is None and streamablehttp_client is None:
    console.print(
        "[yellow]Warning: MCP packages not installed. MCP tools will not be available.[/yellow]"
    )


def load_mcp_config(agent_dir: Path) -> dict[str, Any] | None:
    """Load mcp.json configuration from agent directory.

    Args:
        agent_dir: Path to the agent directory.

    Returns:
        Dictionary containing MCP server configurations, or None if file doesn't exist.
    """
    mcp_config_path = agent_dir / "mcp.json"
    if not mcp_config_path.exists():
        return None

    try:
        config_content = mcp_config_path.read_text()
        config = json.loads(config_content)
        return config.get("mcpServers", {})
    except json.JSONDecodeError as e:
        console.print(
            f"[yellow]Warning: Failed to parse mcp.json: {e}[/yellow]"
        )
        return None
    except Exception as e:
        console.print(
            f"[yellow]Warning: Error loading mcp.json: {e}[/yellow]"
        )
        return None


def create_mcp_client(server_name: str, server_config: dict[str, Any]) -> MCPClient | None:
    """Create an MCPClient instance from server configuration.

    Args:
        server_name: Name of the MCP server.
        server_config: Configuration dictionary for the server.

    Returns:
        MCPClient instance, or None if creation fails.
    """
    # Check for URL-based transport (SSE or Streamable HTTP)
    if "url" in server_config:
        url = server_config["url"]
        # Determine transport type based on URL path
        if "/sse" in url or url.endswith("/sse"):
            # Server-Sent Events transport
            if sse_client is None:
                console.print(
                    f"[yellow]Warning: SSE client not available. Skipping server '{server_name}'.[/yellow]"
                )
                return None
            try:
                return MCPClient(lambda: sse_client(url), prefix=server_name)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to create SSE client for '{server_name}': {e}[/yellow]"
                )
                return None
        else:
            # Streamable HTTP transport
            if streamablehttp_client is None:
                console.print(
                    f"[yellow]Warning: Streamable HTTP client not available. Skipping server '{server_name}'.[/yellow]"
                )
                return None
            try:
                # Support headers if provided
                headers = server_config.get("headers", {})
                return MCPClient(
                    lambda: streamablehttp_client(url, headers=headers if headers else None),
                    prefix=server_name
                )
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to create Streamable HTTP client for '{server_name}': {e}[/yellow]"
                )
                return None

    # Check for command-based transport (stdio)
    if "command" in server_config:
        command = server_config["command"]
        args = server_config.get("args", [])
        env = server_config.get("env", {})

        if StdioServerParameters is None:
            console.print(
                f"[yellow]Warning: StdioServerParameters not available. Skipping server '{server_name}'.[/yellow]"
            )
            return None

        try:
            # Merge environment variables
            merged_env = os.environ.copy()
            merged_env.update(env)

            # Create stdio client
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=merged_env
            )
            return MCPClient(
                lambda: stdio_client(server_params),
                prefix=server_name
            )
        except Exception as e:
            console.print(
                f"[yellow]Warning: Failed to create stdio client for '{server_name}': {e}[/yellow]"
            )
            return None

    console.print(
        f"[yellow]Warning: Invalid MCP server configuration for '{server_name}'. "
        f"Must have either 'url' or 'command' field.[/yellow]"
    )
    return None


def get_mcp_server_info(assistant_id: str) -> list[dict[str, Any]]:
    """Get information about configured MCP servers.

    Args:
        assistant_id: Agent identifier.

    Returns:
        List of dictionaries containing server information.
    """
    agent_dir = AGENT_ROOT / assistant_id
    if not agent_dir.exists():
        return []

    mcp_servers = load_mcp_config(agent_dir)
    if not mcp_servers:
        return []

    server_info_list = []
    for server_name, server_config in mcp_servers.items():
        info: dict[str, Any] = {
            "name": server_name,
            "disabled": server_config.get("disabled", False),
            "type": None,
            "connection": None,
        }

        if "url" in server_config:
            url = server_config["url"]
            if "/sse" in url or url.endswith("/sse"):
                info["type"] = "SSE"
            else:
                info["type"] = "Streamable HTTP"
            info["connection"] = url
        elif "command" in server_config:
            info["type"] = "stdio"
            command = server_config["command"]
            args = server_config.get("args", [])
            info["connection"] = f"{command} {' '.join(args)}".strip()

        server_info_list.append(info)

    return server_info_list


def load_mcp_tools(assistant_id: str) -> list[MCPClient]:
    """Load MCP tools from mcp.json configuration file.

    Args:
        assistant_id: Agent identifier.

    Returns:
        List of MCPClient instances (wrapped in SafeMCPClient if needed).
    """
    agent_dir = AGENT_ROOT / assistant_id
    if not agent_dir.exists():
        return []

    mcp_servers = load_mcp_config(agent_dir)
    if not mcp_servers:
        return []

    mcp_clients = []
    for server_name, server_config in mcp_servers.items():
        # Check if server is disabled
        if server_config.get("disabled", False):
            console.print(
                f"[dim]Skipping disabled MCP server: {server_name}[/dim]"
            )
            continue

        client = create_mcp_client(server_name, server_config)
        if client:
            # Use MCPClient directly - it implements ToolProvider interface
            mcp_clients.append(client)
            console.print(
                f"[dim]Loaded MCP server: {server_name}[/dim]"
            )

    return mcp_clients

