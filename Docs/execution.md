# ddaword_cli/execution.py 詳細設計

## 役割
- ユーザー入力からファイル参照を組み込んだ最終プロンプトを生成し、Strands エージェントに対する同期/非同期実行・ストリーミング描画を統合管理。
- ツールイベントやモデルデルタを Rich Panel/テキストで即時表示し、最終応答は Markdown として整形出力する。

## 処理フロー
1. `execute_task` が呼ばれると `_assemble_prompt` により `@path` 記法の補足情報を収集し、最大 50,000 文字に切り詰めたファイル内容をコンテキストとして付与。
2. エージェント実装が `stream_async` を持つ場合は `_stream_agent` を使用。イベントストリームから:
   - `tool_stream_event` → `_render_tool_event`
   - `model_stream_event` → `_render_model_delta`
   - `assistant_response` → `_extract_final_response`
   を通じて UI 更新。
3. ストリーミングが未実装/エラーの際は `_invoke_agent` にフォールバックし、同期的に応答を取得。
4. 取得した応答テキストを `Markdown` でレンダリングし、セクション間に空行を挿入して読みやすさを保持。

## 主要ユーティリティ
- `_stringify_response`: dict/list/Iterable を再帰的に文字列へ正規化し、Rich 表示に適した形へ整える。
- `_render_tool_event`: ツールからの途中結果を `Panel` で強調表示し、色は `COLORS["tool"]` を使用。
- `_render_model_delta`: LLM のストリーミングトークンをリアルタイム描画し、バッファへ蓄積して最終結果が欠落した場合にも対応。

## エラーハンドリング
- ファイル読み込み失敗時は例外メッセージをコンテキストに埋め込み、解析不能のまま沈黙しない。
- ストリーミング中の例外は捕捉して警告を表示した後、同期実行へ自動フェイルオーバー。
- エージェント呼び出し時の例外は上位へ送出せず `_invoke_agent` 内で吸収し、`simple_cli` が継続できるよう配慮。

## 拡張ポイント
- ストリーミングイベントの種類が増えた場合は `_render_tool_event` / `_render_model_delta` の分岐を拡張し、`agent.stream_async` の契約に合わせる。
- Markdown 出力前にプレーンテキストフィルタを挟むことで、不正な Markdown による Rich 側の例外発生を抑制できる。
