# MCP実装レビュー - Strand Agentsとの比較

## 実行日
2025年1月27日

## 概要
現在のMCP（Model Context Protocol）実装をStrand Agentsの公式ドキュメントと比較し、最適性を評価しました。

## 現在の実装状況

### 1. Managed Integration (Experimental) の使用 ✅

**現在の実装:**
```python
# main.py:167-171
mcp_clients = load_mcp_tools(assistant_id)
if mcp_clients:
    # MCPClient implements ToolProvider interface, can be added directly
    # Strands Agent will handle initialization automatically
    tools.extend(mcp_clients)
```

**評価:** ✅ **適切**
- Strand Agentsのドキュメントによると、`MCPClient`は`ToolProvider`インターフェースを実装しており、`Agent`の`tools`リストに直接追加できる
- Managed Integrationを使用することで、明示的な`with`文によるコンテキスト管理が不要
- エージェントが自動的にMCP接続の開始、ツール発見、クリーンアップを管理

**ドキュメント参照:**
> "The `MCPClient` now implements the experimental `ToolProvider` interface, enabling direct usage in Agent constructors. The agent handles MCP connection startup, tool discovery, and cleanup without requiring explicit with statements or manual resource management."

### 2. トランスポート方式のサポート ✅

**現在の実装:**
```python
# mcp_tools.py:241-326
def create_mcp_client(server_name: str, server_config: dict[str, Any]) -> MCPClient | None:
    # SSE transport
    if "/sse" in url or url.endswith("/sse"):
        return MCPClient(lambda: sse_client(url), prefix=server_name)
    
    # Streamable HTTP transport
    else:
        headers = server_config.get("headers", {})
        return MCPClient(lambda: streamablehttp_client(url, headers=headers if headers else None), prefix=server_name)
    
    # stdio transport
    if "command" in server_config:
        server_params = StdioServerParameters(...)
        return MCPClient(lambda: stdio_client(server_params), prefix=server_name)
```

**評価:** ✅ **適切**
- 3つの主要なトランスポート方式（stdio、SSE、Streamable HTTP）をすべてサポート
- ドキュメントに記載されているすべての方式に対応
- Streamable HTTPの`headers`パラメータも適切にサポート

### 3. ツール名プレフィックス ✅

**現在の実装:**
```python
# mcp_tools.py:263, 279, 312
return MCPClient(lambda: sse_client(url), prefix=server_name)
```

**評価:** ✅ **適切**
- 複数のMCPサーバーを使用する際の名前衝突を防ぐため、`prefix`パラメータを使用
- ドキュメントの推奨事項に従っている

### 4. エラーハンドリング ⚠️

**現在の実装:**
```python
# main.py:175-193
try:
    agent = create_agent_with_config(model, assistant_id, tools)
except (ValueError, Exception) as e:
    error_msg = str(e)
    if "Failed to load tool" in error_msg or "MCP" in error_msg:
        console.print("[yellow]Warning: Some MCP servers failed to initialize...[/yellow]")
        try:
            agent = create_agent_with_config(model, assistant_id, DEFAULT_TOOLS)
        except Exception:
            raise e
```

**評価:** ⚠️ **改善の余地あり**

**問題点:**
1. **過度に広い例外キャッチ**: `Exception`をキャッチしているため、予期しないエラーも隠蔽される可能性
2. **エラーメッセージの文字列マッチング**: エラーメッセージの文字列検索は脆弱で、メッセージが変更されると動作しなくなる
3. **フォールバック処理**: MCPツールがすべて失敗した場合、デフォルトツールのみでエージェントを作成するが、部分的に失敗した場合の処理が不明確

**推奨改善:**
- `ToolProviderException`などの具体的な例外型を使用
- 各MCPクライアントの初期化エラーを個別に処理し、成功したもののみをツールリストに追加

### 5. ツールフィルタリング ❌

**現在の実装:**
- ツールフィルタリング機能は未実装

**評価:** ❌ **未実装**

**ドキュメントの推奨事項:**
- `tool_filters`パラメータを使用して、特定のツールのみを読み込むことができる
- 文字列マッチング、正規表現、カスタム関数によるフィルタリングをサポート

**推奨改善:**
```python
# mcp.jsonにtool_filtersを追加できるようにする
{
  "mcpServers": {
    "server_name": {
      "url": "...",
      "tool_filters": {
        "allowed": ["tool1", "tool2"],
        "rejected": ["unwanted_tool"]
      }
    }
  }
}
```

### 6. エラーログの抑制 ⚠️

**現在の実装:**
```python
# mcp_tools.py:18-183
# 大量の警告抑制コード
warnings.filterwarnings(...)
logging.getLogger("mcp").setLevel(logging.ERROR)
class MCPErrorFilter(logging.Filter): ...
class FilteredStderr: ...
```

**評価:** ⚠️ **過剰な可能性**

**問題点:**
1. **過剰な抑制**: エラーログを完全に抑制することで、デバッグが困難になる可能性
2. **stderrの置き換え**: `sys.stderr`を置き換えるのは危険で、他のライブラリとの互換性問題を引き起こす可能性
3. **保守性**: 大量のフィルタリングコードは保守が困難

**推奨改善:**
- エラーログの抑制を最小限に
- デバッグモードや詳細ログモードを追加
- `sys.stderr`の置き換えを避け、ロガーレベルの調整のみに留める

### 7. 接続管理 ✅

**現在の実装:**
- Managed Integrationを使用しているため、明示的な`with`文は不要
- エージェントが自動的に接続を管理

**評価:** ✅ **適切**
- ドキュメントの推奨事項に従っている
- ただし、実験的な機能であることに注意が必要

### 8. 設定ファイルの構造 ✅

**現在の実装:**
```python
# mcp_tools.py:212-238
def load_mcp_config(agent_dir: Path) -> dict[str, Any] | None:
    mcp_config_path = agent_dir / "mcp.json"
    config = json.loads(config_content)
    return config.get("mcpServers", {})
```

**評価:** ✅ **適切**
- `mcp.json`から`mcpServers`セクションを読み込む
- エラーハンドリングも適切

## 改善推奨事項

### 優先度: 高

1. **エラーハンドリングの改善**
   - 具体的な例外型を使用
   - 各MCPクライアントの初期化エラーを個別に処理
   - 部分的に失敗した場合の処理を明確化

2. **ツールフィルタリングの実装**
   - `mcp.json`に`tool_filters`を追加できるようにする
   - 文字列マッチング、正規表現、カスタム関数をサポート

### 優先度: 中

3. **エラーログ抑制の見直し**
   - 過剰な抑制を削減
   - デバッグモードを追加
   - `sys.stderr`の置き換えを避ける

4. **接続状態の監視**
   - MCPサーバーのヘルスチェック機能を追加
   - 接続状態を監視する機能を追加

### 優先度: 低

5. **設定ファイルのバリデーション**
   - `mcp.json`の構造を検証
   - 不正な設定を早期に検出

6. **ホットリロード機能**
   - `mcp.json`の変更を検知して自動的に再読み込み

## 結論

現在の実装は、Strand Agentsのドキュメントに概ね準拠しており、基本的な機能は適切に実装されています。特に、Managed Integrationの使用、トランスポート方式のサポート、ツール名プレフィックスの使用は適切です。

ただし、以下の点で改善の余地があります：
- エラーハンドリングの改善（具体的な例外型の使用）
- ツールフィルタリング機能の追加
- エラーログ抑制の見直し

これらの改善により、より堅牢で保守しやすい実装になります。

## 参考資料

- [Strand Agents MCP Tools Documentation](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/mcp-tools/index.md)
- [MCP Calculator Example](https://strandsagents.com/latest/documentation/docs/examples/python/mcp_calculator/index.md)

