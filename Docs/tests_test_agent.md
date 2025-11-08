# tests/test_agent.py 詳細設計

## テスト目的
- `ddaword_cli.agent` の永続ディレクトリ操作が副作用なく動作すること、および `reset_agent` がプロンプト内容を所望通りに差し替えることを保証する。

## テストケース
### `test_get_system_prompt_creates_agent_files`
- `monkeypatch` で `agent.AGENT_ROOT` を一時ディレクトリへ上書きし、`get_system_prompt("demo-agent")` の呼び出しを通じてファイル群が生成されることを確認。
- アサーション: 生成されたプロンプトに `<agent_memory>` が含まれること、`agent.md` と `memories/` が存在すること。

### `test_reset_agent_replaces_prompt`
- `AGENT_ROOT` を一時パスに差し替えた上で:
  1. `primary` を初期化し既定プロンプトを保存。
  2. `primary` の `agent.md` をカスタム文字列に書き換え。
  3. `reset_agent("secondary", source_agent="primary")` を実行し、コピーが正しく行われるか検証。
  4. `primary` を再リセットして既定プロンプトへ戻ることを確認。
- Strands 環境へアクセスせずにローカルファイル操作のみで完結するため、CI でも決 deterministically 実行可能。

## テスト戦略メモ
- 追加のエージェント管理機能を実装した際は、このファイルを拡張して副作用（削除・複製）を確実に検証する。
- 長期的には `pytest` フィクスチャで共通の `AGENT_ROOT` 差し替え処理を提供するとスケールしやすい。
