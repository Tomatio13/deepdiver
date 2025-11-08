# ddaword_cli/commands.py 詳細設計

## 役割
- 対話ループから `/` プレフィックスで呼び出されるインタラクティブ・コマンドのディスパッチと、`!` プレフィックスで実行される Bash コマンドの実行ラッパーを提供。
- Rich コンソールによる一貫したフィードバック表示と、タイムアウトやエラー時の標準化されたメッセージ出力を担う。

## 機能別設計
### `handle_command(command: str)`
- 受け取った文字列から先頭の `/` を除去し、小文字化したトークンでスイッチング。
- `quit/exit/q` は `'exit'` を呼び出し元へ返却し、`simple_cli` が即座にループを抜けられるようにする。
- `clear` は Rich の `console.clear()` と ASCII バナー再描画を行い、会話履歴は維持したまま UI をリフレッシュ。
- `help` は `.ui.show_interactive_help` へ委譲。
- 未知コマンドは警告を表示した上で `True` を返し、呼び出し側に「処理済み」と認識させる。

### `execute_bash_command(command: str)`
- 先頭の `!` を除去した文字列を `subprocess.run(..., shell=True, timeout=30)` に渡し、現在の作業ディレクトリで実行。
- stdout/stderr を個別に Rich へ出力。エラーコードが非 0 の場合は `Exit code` を補足表示。
- `TimeoutExpired` やその他例外は明示的なエラーメッセージで通知し、CLI を継続可能に保つ。

## 依存要素
- `.config` から `console`, `COLORS`, `DDAWORD_ASCII` を参照してビジュアルを統一。
- `.ui.show_interactive_help` に依存し、ヘルプ内容の一元管理を維持。

## エラー/セキュリティ配慮
- `shell=True` を使用しているため、ユーザー入力がそのままシェルに渡る点を周知し、不要な自動整形を行わない。
- タイムアウトは 30 秒固定で、長時間ハングアップによる CLI フリーズを予防。

## 拡張案
- 将来的に `/set key value` のような状態操作コマンドを追加する際は、本モジュール側で小さなコマンドテーブルを導入し、`main.simple_cli` の複雑化を避ける。
