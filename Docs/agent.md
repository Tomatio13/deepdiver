# ddaword_cli/agent.py 詳細設計

## 役割
- Strands エージェントの永続ディレクトリ管理（`~/.strands-agents-cli/<agent>/`）とエージェント生成ユーティリティを提供し、CLI からのライフサイクル操作（一覧・リセット・生成）を一括で扱う。

## ディレクトリ構造
- ルート: `AGENT_ROOT = ~/.strands-agents-cli`
- 各エージェント: `<AGENT_ROOT>/<assistant_id>/`
  - `agent.md`: プロンプト／長期記憶
  - `memories/`: 追加メモリ
- `_ensure_agent_files` が初回呼び出し時にフォルダと `agent.md`/`memories` を自動作成。

## 関数詳細
### `list_agents()`
- `AGENT_ROOT` 配下のディレクトリを列挙し、Rich でパスと状態（agent.md 有無）を表示。

### `reset_agent(agent_name, source_agent=None)`
- 既存ディレクトリを `shutil.rmtree` で削除後、デフォルトまたは別エージェントの `agent.md` をコピー。
- 実行結果／配置先を Rich で通知。

### `_base_cli_prompt()` / `_build_system_prompt()`
- 作業ディレクトリやメモリディレクトリを記述したランタイムコンテキストを生成し、`agent.md` の内容を `<agent_memory>` タグ内へ埋め込む。

### `get_agent_directory()` / `get_system_prompt()`
- CLI の他レイヤーが永続パスとプロンプトを取得するための API。`tests/test_agent.py` で振る舞いが保証されている。

### `create_agent_with_config(model, assistant_id, tools)`
- `_build_system_prompt` を適用した `strands.Agent` を生成し、`tools` と `model` を渡す。
- 生成したエージェントに `cli_context` 属性を追加し、他モジュールがパス情報へ容易にアクセスできるようにする。

## エラーハンドリング/注意
- `reset_agent` は `shutil.rmtree` を用いるため、操作対象の存在確認とユーザー通知を必ず行う。
- `_ensure_agent_files` は idempotent に設計されており、何度呼ばれても同じ状態が維持される。

## 拡張
- メモリディレクトリ配下にサブリソースを追加する際は、`cli_context` のディクショナリにパスを追記して全モジュールで再利用できるようにする。
- 将来的に複数ストレージ後端をサポートする場合は、`AGENT_ROOT` を Path 以外のアダプタに差し替えやすい抽象化（例: ストレージインターフェース）を検討。
