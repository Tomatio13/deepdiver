# ddaword_cli/mcp_tools.py 詳細設計

## 役割
- `~/.strands-agents-cli/<agent名>/mcp.json`からMCP（Model Context Protocol）サーバー設定を読み込み、Strands AgentのToolとして統合する機能を提供。
- Strands Agentの`MCPClient`を使用して、stdio、SSE、Streamable HTTPの3つのトランスポート方式に対応。
- MCPクライアントの初期化エラーやタイムアウトエラーを適切に処理し、一部のサーバーが失敗しても他のサーバーは動作し続けるようにする。

## 機能別設計

### エラーハンドリングとログ抑制

#### `RuntimeWarning`の抑制
- MCPクライアントのクリーンアップ時に発生する`coroutine was never awaited`警告を抑制。
- `warnings.filterwarnings()`を使用して、以下のパターンを抑制：
  - `.*coroutine.*was never awaited.*`
  - `.*MCPClient.*`
  - `asyncio`モジュールからのMCP関連警告

#### ログレベルの調整
- MCP、httpx、httpcoreのロガーを`ERROR`レベルに設定し、ハンドラーを削除してノイズを抑制。
- `MCPErrorFilter`クラスで、以下のエラーパターンをフィルター：
  - `receive loop`
  - `error in sse_reader`
  - `readtimeout`
  - `httpx.readtimeout`
  - `httpcore.readtimeout`
  - `unhandled exception`
  - `sse_reader`

#### stderrフィルター
- `FilteredStderr`クラスで`sys.stderr`をラップし、直接出力されるエラーメッセージをフィルター。
- 複数行のエラーメッセージ（Traceback含む）をバッファリングして処理。
- MCP関連のエラーパターンを含むメッセージを抑制。

### 設定ファイルの読み込み

#### `load_mcp_config(agent_dir: Path) -> dict[str, Any] | None`
- `mcp.json`ファイルを読み込み、`mcpServers`セクションを返す。
- JSONパースエラーやファイル読み込みエラーをキャッチし、警告を表示して`None`を返す。
- ファイルが存在しない場合は`None`を返す。

### MCPクライアントの作成

#### `create_mcp_client(server_name: str, server_config: dict[str, Any]) -> MCPClient | None`
- サーバー設定に基づいて`MCPClient`インスタンスを作成。

**URLベースのトランスポート（SSE/Streamable HTTP）:**
- URLに`/sse`が含まれる場合：`sse_client`を使用してSSEトランスポートを作成。
- それ以外：`streamablehttp_client`を使用してStreamable HTTPトランスポートを作成。
- `headers`が指定されている場合は、Streamable HTTPクライアントに渡す。

**コマンドベースのトランスポート（stdio）:**
- `command`と`args`を指定して`StdioServerParameters`を作成。
- 環境変数は`os.environ`とマージして渡す。
- `stdio_client`を使用してstdioトランスポートを作成。

**エラーハンドリング:**
- 各トランスポートタイプの作成時にエラーが発生した場合、警告を表示して`None`を返す。
- 無効な設定（`url`も`command`もない）の場合は警告を表示して`None`を返す。

### MCPサーバー情報の取得

#### `get_mcp_server_info(assistant_id: str) -> list[dict[str, Any]]`
- 設定されたMCPサーバーの情報を取得して返す。
- 各サーバーについて以下の情報を含む辞書を返す：
  - `name`: サーバー名
  - `disabled`: 無効化されているかどうか
  - `type`: トランスポートタイプ（`stdio`/`SSE`/`Streamable HTTP`）
  - `connection`: 接続情報（URLまたはコマンド+引数）

### MCPツールの読み込み

#### `load_mcp_tools(assistant_id: str) -> list[MCPClient]`
- `mcp.json`からMCPサーバー設定を読み込み、各サーバーに対して`MCPClient`インスタンスを作成。
- `disabled: true`が設定されているサーバーはスキップ。
- 作成に成功したクライアントのリストを返す。
- 各サーバーの読み込み時に`[dim]Loaded MCP server: {server_name}[/dim]`メッセージを表示。

## 設定ファイル形式

### `mcp.json`の構造

```json
{
  "mcpServers": {
    "server-name": {
      "url": "http://localhost:5001/mcp",
      "disabled": false,
      "headers": {
        "Authorization": "Bearer token"
      }
    },
    "another-server": {
      "command": "/path/to/command",
      "args": ["arg1", "arg2"],
      "env": {
        "ENV_VAR": "value"
      },
      "disabled": false
    }
  }
}
```

### 設定フィールド

- **`url`**: HTTPベースのトランスポート（SSEまたはStreamable HTTP）を使用する場合のURL。
  - URLに`/sse`が含まれる場合、SSEトランスポートが使用される。
  - それ以外はStreamable HTTPトランスポートが使用される。
- **`command`**: stdioトランスポートを使用する場合のコマンド。
- **`args`**: コマンドの引数（オプション、デフォルト: `[]`）。
- **`env`**: 環境変数（オプション、デフォルト: `{}`）。
- **`headers`**: HTTPリクエストヘッダー（Streamable HTTPのみ、オプション）。
- **`disabled`**: サーバーを無効化するかどうか（オプション、デフォルト: `false`）。

## 依存要素

- **Strands Agent**: `strands.tools.mcp.MCPClient`を使用。
- **MCP Python SDK**: `mcp`パッケージから以下のクライアントをインポート：
  - `stdio_client`, `StdioServerParameters`（stdioトランスポート）
  - `sse_client`（SSEトランスポート）
  - `streamablehttp_client`（Streamable HTTPトランスポート）
- **`.agent`**: `AGENT_ROOT`を参照してエージェントディレクトリのパスを取得。
- **`.config`**: `console`を参照してメッセージを表示。

## エラー/セキュリティ配慮

### エラーハンドリング
- 設定ファイルの読み込みエラー、JSONパースエラー、クライアント作成エラーを適切にキャッチ。
- 一部のサーバーが失敗しても、他のサーバーは正常に動作し続ける。
- エラーメッセージは警告として表示され、CLIの動作は継続される。

### ログと警告の抑制
- MCPクライアントのバックグラウンドスレッドで発生するタイムアウトエラーや接続エラーを抑制。
- ログフィルターとstderrフィルターの2層でエラーメッセージを抑制。
- テスト環境ではstderrフィルターを適用しない（`pytest`モジュールが存在する場合はスキップ）。

### セキュリティ
- 環境変数は`os.environ`とマージして渡すため、既存の環境変数が保持される。
- HTTPヘッダーに認証情報を含めることができるが、設定ファイルに平文で保存される点に注意。

## 統合方法

### `main.py`での使用

```python
from .mcp_tools import load_mcp_tools

# エージェント作成時にMCPツールを読み込む
mcp_clients = load_mcp_tools(assistant_id)
if mcp_clients:
    tools.extend(mcp_clients)

agent = create_agent_with_config(model, assistant_id, tools)
```

### `/mcp`コマンドでの使用

`commands.py`の`handle_command()`関数で`/mcp`コマンドを処理：

```python
from .mcp_tools import get_mcp_server_info

if cmd == "mcp":
    server_info_list = get_mcp_server_info(assistant_id)
    # サーバー情報を表示
```

## 動作フロー

1. **初期化時**: モジュール読み込み時にログフィルターとstderrフィルターを設定。
2. **エージェント作成時**: `load_mcp_tools()`が呼ばれ、`mcp.json`から設定を読み込む。
3. **クライアント作成**: 各サーバー設定に対して`create_mcp_client()`が呼ばれ、`MCPClient`インスタンスが作成される。
4. **ツール登録**: 作成された`MCPClient`インスタンスが`Agent`の`tools`リストに追加される。
5. **初期化**: Strands Agentが`ToolProvider`インターフェースを通じて各MCPクライアントを初期化。
6. **エラー処理**: 初期化に失敗したサーバーは自動的にスキップされ、他のサーバーは正常に動作する。

## トラブルシューティング

### MCPサーバーが読み込まれない
- `mcp.json`が`~/.strands-agents-cli/<agent名>/mcp.json`に存在するか確認。
- JSONの構文エラーがないか確認。
- `disabled: true`が設定されていないか確認。

### タイムアウトエラーが発生する
- サーバーが起動しているか確認。
- URLが正しいか確認。
- ネットワーク接続を確認。
- エラーメッセージは抑制されるが、サーバーはスキップされる。

### ツールが認識されない
- `MCPClient`は`ToolProvider`インターフェースを実装しているため、`Agent`の`tools`リストに直接追加できる。
- Strands Agentが自動的にツールを検出して登録する。

## 拡張案

- MCPサーバーのヘルスチェック機能を追加。
- 設定ファイルのバリデーション機能を追加。
- MCPサーバーの接続状態を監視する機能を追加。
- 設定ファイルのホットリロード機能を追加。

