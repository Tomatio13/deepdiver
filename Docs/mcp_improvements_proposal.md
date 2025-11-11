# MCP実装改善提案

## 1. エラーハンドリングの改善

### 現在の問題点
- 過度に広い例外キャッチ（`Exception`）
- エラーメッセージの文字列マッチング
- 部分的に失敗した場合の処理が不明確

### 改善案

```python
# mcp_tools.py の改善版

from strands.types.exceptions import ToolProviderException

def load_mcp_tools(assistant_id: str) -> list[MCPClient]:
    """Load MCP tools from mcp.json configuration file.
    
    Returns:
        List of successfully initialized MCPClient instances.
    """
    agent_dir = AGENT_ROOT / assistant_id
    if not agent_dir.exists():
        return []

    mcp_servers = load_mcp_config(agent_dir)
    if not mcp_servers:
        return []

    mcp_clients = []
    failed_servers = []
    
    for server_name, server_config in mcp_servers.items():
        # Check if server is disabled
        if server_config.get("disabled", False):
            console.print(
                f"[dim]Skipping disabled MCP server: {server_name}[/dim]"
            )
            continue

        try:
            client = create_mcp_client(server_name, server_config)
            if client:
                mcp_clients.append(client)
                console.print(
                    f"[dim]Loaded MCP server: {server_name}[/dim]"
                )
            else:
                failed_servers.append((server_name, "Client creation returned None"))
        except ToolProviderException as e:
            # 具体的な例外型をキャッチ
            failed_servers.append((server_name, str(e)))
            console.print(
                f"[yellow]Warning: Failed to initialize MCP server '{server_name}': {e}[/yellow]"
            )
        except Exception as e:
            # 予期しないエラーは警告を出して続行
            failed_servers.append((server_name, str(e)))
            console.print(
                f"[yellow]Warning: Unexpected error initializing MCP server '{server_name}': {e}[/yellow]"
            )
    
    # 失敗したサーバーがある場合、サマリーを表示
    if failed_servers:
        console.print(
            f"[dim]Note: {len(failed_servers)} MCP server(s) failed to initialize. "
            f"Continuing with {len(mcp_clients)} available server(s).[/dim]"
        )
    
    return mcp_clients
```

```python
# main.py の改善版

async def main(assistant_id: str, session_state):
    """Main entry point."""
    model = create_model()

    # Create agent with default tool set
    tools = list(DEFAULT_TOOLS)

    # Load MCP tools from mcp.json if available
    mcp_clients = load_mcp_tools(assistant_id)
    if mcp_clients:
        tools.extend(mcp_clients)
        console.print(
            f"[dim]Loaded {len(mcp_clients)} MCP server(s)[/dim]"
        )

    # Create agent - MCP clients will initialize during agent creation
    # load_mcp_tools()で既にエラーハンドリングされているため、
    # ここでは単純にエージェントを作成する
    try:
        agent = create_agent_with_config(model, assistant_id, tools)
    except Exception as e:
        # エージェント作成自体が失敗した場合のみエラーを表示
        console.print(
            f"[bold red]Error: Failed to create agent: {e}[/bold red]"
        )
        raise

    try:
        await simple_cli(agent, assistant_id, session_state)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error:[/bold red] {e}\n")
```

## 2. ツールフィルタリングの実装

### 改善案

```python
# mcp_tools.py に追加

import re
from typing import Callable

def create_mcp_client(
    server_name: str, 
    server_config: dict[str, Any]
) -> MCPClient | None:
    """Create an MCPClient instance from server configuration.
    
    Args:
        server_name: Name of the MCP server.
        server_config: Configuration dictionary for the server.
            May include:
            - url: URL for SSE or Streamable HTTP transport
            - command: Command for stdio transport
            - args: Arguments for stdio transport
            - env: Environment variables for stdio transport
            - headers: Headers for Streamable HTTP transport
            - tool_filters: Tool filtering configuration
                - allowed: List of tool names, regex patterns, or callables
                - rejected: List of tool names, regex patterns, or callables
    
    Returns:
        MCPClient instance, or None if creation fails.
    """
    # ツールフィルタを取得
    tool_filters_config = server_config.get("tool_filters", {})
    tool_filters = None
    
    if tool_filters_config:
        # tool_filtersをStrandsの形式に変換
        allowed = tool_filters_config.get("allowed", [])
        rejected = tool_filters_config.get("rejected", [])
        
        # 文字列を正規表現パターンに変換（必要に応じて）
        processed_allowed = []
        processed_rejected = []
        
        for item in allowed:
            if isinstance(item, str):
                # 文字列の場合はそのまま使用（完全一致）
                processed_allowed.append(item)
            elif isinstance(item, dict) and "pattern" in item:
                # 正規表現パターン
                processed_allowed.append(re.compile(item["pattern"]))
            else:
                processed_allowed.append(item)
        
        for item in rejected:
            if isinstance(item, str):
                processed_rejected.append(item)
            elif isinstance(item, dict) and "pattern" in item:
                processed_rejected.append(re.compile(item["pattern"]))
            else:
                processed_rejected.append(item)
        
        if processed_allowed or processed_rejected:
            tool_filters = {
                "allowed": processed_allowed if processed_allowed else None,
                "rejected": processed_rejected if processed_rejected else None
            }
    
    # Check for URL-based transport (SSE or Streamable HTTP)
    if "url" in server_config:
        url = server_config["url"]
        headers = server_config.get("headers", {})
        
        if "/sse" in url or url.endswith("/sse"):
            # Server-Sent Events transport
            if sse_client is None:
                console.print(
                    f"[yellow]Warning: SSE client not available. Skipping server '{server_name}'.[/yellow]"
                )
                return None
            try:
                return MCPClient(
                    lambda: sse_client(url), 
                    prefix=server_name,
                    tool_filters=tool_filters
                )
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
                return MCPClient(
                    lambda: streamablehttp_client(url, headers=headers if headers else None),
                    prefix=server_name,
                    tool_filters=tool_filters
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
            merged_env = os.environ.copy()
            merged_env.update(env)

            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=merged_env
            )
            return MCPClient(
                lambda: stdio_client(server_params),
                prefix=server_name,
                tool_filters=tool_filters
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
```

### mcp.json の例

```json
{
  "mcpServers": {
    "aws_docs": {
      "command": "uvx",
      "args": ["awslabs.aws-documentation-mcp-server@latest"],
      "tool_filters": {
        "allowed": ["search_documentation", "read_documentation"],
        "rejected": ["get_available_services"]
      }
    },
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${MCP_PAT}"
      },
      "tool_filters": {
        "allowed": [
          {
            "pattern": "^search.*"
          }
        ]
      }
    }
  }
}
```

## 3. エラーログ抑制の見直し

### 改善案

```python
# mcp_tools.py の改善版

import logging
import sys
from typing import Optional

# デバッグモードの設定（環境変数から読み込み）
DEBUG_MCP = os.getenv("DEBUG_MCP", "false").lower() == "true"

# 基本的な警告抑制のみ（過剰な抑制を削減）
if not DEBUG_MCP:
    # MCPクライアントのクリーンアップ時の警告のみ抑制
    warnings.filterwarnings(
        "ignore",
        message=".*coroutine.*was never awaited.*",
        category=RuntimeWarning,
    )
    
    # MCP関連のロガーをWARNINGレベルに設定（ERRORではなく）
    mcp_logger = logging.getLogger("mcp")
    mcp_logger.setLevel(logging.WARNING)
    
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    
    httpcore_logger = logging.getLogger("httpcore")
    httpcore_logger.setLevel(logging.WARNING)
else:
    # デバッグモードではすべてのログを表示
    console.print("[dim]MCP debug mode enabled[/dim]")

# sys.stderrの置き換えは削除（危険で不要）
```

## 4. 接続状態の監視（オプション）

### 改善案

```python
# mcp_tools.py に追加

def check_mcp_server_health(client: MCPClient) -> bool:
    """Check if an MCP server is healthy.
    
    Args:
        client: MCPClient instance to check.
    
    Returns:
        True if server is healthy, False otherwise.
    """
    try:
        # list_tools_sync()を呼び出して接続を確認
        # 注意: これはManaged Integrationでは自動的に管理されるため、
        # 明示的なチェックは通常不要
        # この関数はデバッグ目的でのみ使用
        tools = client.list_tools_sync()
        return True
    except Exception:
        return False

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
            "status": "unknown",  # 追加: 接続状態
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
```

## 実装の優先順位

1. **エラーハンドリングの改善** - 最も重要
2. **ツールフィルタリングの実装** - 有用性が高い
3. **エラーログ抑制の見直し** - 保守性の向上
4. **接続状態の監視** - オプション機能

