## Deepdiver Subagents Examples

このディレクトリの `.md` は **サブエージェント定義**のサンプルです。

### 配置先

- **ユーザ共通**: `~/.deepdiver/subagents/`
- **プロジェクト**: `<project_root>/.deepdiver/subagents/`（同名があればこちらが優先）

### 作成済みサンプル

- `date-checker.md`: `current_time` を使って「明日」等を確定
- `event-searcher.md`: MCPのTaivily/Tavily系ツールでイベント検索
- `weather-forecast.md`: MCPのweather系ツールで天気予報取得

### MCPツールについて（重要）

DeepdiverのMCPツール名は **`~/.deepdiver/<agent>/mcp.json` の server名（prefix）** に依存します。

- `/mcp` で有効なMCPサーバを確認
- そのprefixに対応する検索/天気ツールをサブエージェントが使います

