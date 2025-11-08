# ddaword_cli/input.py 詳細設計

## 役割
- prompt_toolkit を用いた CLI 入力 UX を統括し、補完・キーバインド・ツールバー表示・ファイル参照解析を提供。
- `/` コマンド補完・`@path` ファイル補完を状況依存で切り替え、ユーザー入力を `execute_task` が消費しやすい形へ整える。

## コンポーネント
### prompt_toolkit 概要
- 端末上で動作するリッチな行編集ライブラリ。Emacs モードをベースにしながらカスタムキーバインドやステータスバー、外部エディタ連携を提供できる。
- キーバインドは `KeyBindings` デコレータで宣言し、端末が認識できる組み合わせのみ捕捉可能（Shift+Enter など一部は端末側で区別できない点に留意）。
- スタイルや補完、マルチライン入力などを `PromptSession` 初期化時に渡せるため、本 CLI では入力体験の中心的コンポーネントとなっている。

### `FilePathCompleter`
- `@` 以降のトークンに対してのみ `PathCompleter` を起動し、スペースをバックスラッシュでエスケープするなど CLI 入力に適した整形を実施。
- `Path.is_dir()` 判定に基づき末尾 `/` を自動付加し、階層移動を滑らかにする。

### `CommandCompleter`
- 行頭 `/` の場合にのみ起動し、`config.COMMANDS` のキーから前方一致候補を提示。

### `parse_file_mentions(text)`
- `@path` 記法を正規表現で抽出し、`Path.cwd()` 基準で解決。存在しない場合は Rich 警告を即時表示し、無視されたままにしない。
- 戻り値は `(元テキスト, 実ファイル Path のリスト)` で `execution._assemble_prompt` へ渡される。

### `get_bottom_toolbar(session_state, session_ref)`
- `SessionState.auto_approve` と現在の入力内容（BASH モード判定）を基に、Rich 風のステータスバー情報を prompt_toolkit スタイルで提供。

### `create_prompt_session()`
- 主要なキーバインド:
  - `Ctrl+T`: auto-approve トグル
  - `Enter`: 補完中は候補決定／通常時は送信
  - `Alt+Enter` / `Ctrl+J`: 改行挿入
  - `Ctrl+E`: 外部エディタ起動
  - `Backspace`: 削除後に補完を再トリガ
- `merge_completers` によりコマンド補完とファイル補完を統合し、`reserve_space_for_menu=7` で候補欄を確保。
- `session_ref` ディクショナリを閉包内で共有し、ツールバー描画時に現在のバッファへアクセス可能にする。

## 依存と副作用
- `EDITOR` 未設定時に `nano` をデフォルト化しており、外部エディタ機能の一貫性を確保。
- `prompt_toolkit.styles.Style` をローカル import しているため、モジュール import 時のコストを抑えつつスタイル設定を保持。

## 拡張時の考慮
- 新しい補完種別（例: `#tag`）を追加する場合は `merge_completers` に別コンポーネントを差し込む。
- キーバインドを増やす場合は既存バインドとの衝突に注意し、prompt_toolkit のモーダル挙動（vi/Emacs）に合わせて記述する。
