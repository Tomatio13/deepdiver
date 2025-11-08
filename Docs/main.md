# ddaword_cli/main.py 詳細設計

## 役割と責務
- CLI のエントリーポイント群 (`cli_main` / `main`) を提供し、サブコマンド・引数処理からエージェント起動、対話ループまでを一貫して制御する。
- 依存パッケージの存在チェックや `SessionState` の初期化など、対話セッションの前提条件を満たすためのゲートキーピングを行う。
- prompt_toolkit を用いた `simple_cli` ループ内で、スラッシュコマンド・シェルコマンド・通常プロンプトの優先順位を保証しつつ `execution.execute_task` に処理を委譲する。

## 主な機能
### `check_cli_dependencies()`
- `rich`, `requests`, `python-dotenv`, `prompt_toolkit` のインポート可否を検査し、欠損時はインストール手順を案内して即時終了。
- エラー終了時は `sys.exit(1)` でプロセスを停止し、依存欠如による不整合を防ぐ。

### `parse_args()`
- `argparse` を用いて `list` / `help` / `reset` サブコマンドと `--agent`, `--auto-approve` を受理。
- `reset` コマンドには `--agent` (必須) と `--target`(コピー元) を提供し、他のサブコマンドはオプションなしのシンプル構成を維持。

### `simple_cli(agent, assistant_id, session_state)`
- `console` によるバナー表示と Tips を整えた後、`create_prompt_session` で prompt_toolkit セッションを生成。
- 入力ループ内で以下の分岐を順守：
  1. `/` で始まる場合は `commands.handle_command`
  2. `!` で始まる場合は `commands.execute_bash_command`
  3. `quit/exit/q` は即終了
  4. それ以外は `execute_task`
- `SessionState.auto_approve` のオン／オフを UI に表示し、Ctrl+T 連動を利用者に伝える。

### `main(assistant_id, session_state)`
- `.config.create_model()` でモデル実体を（存在すれば）生成し、`DEFAULT_TOOLS` を `create_agent_with_config` に渡してエージェントを構築。
- `simple_cli` を `await` し、例外が発生した際は Rich で整形したエラーメッセージを表示。

### `cli_main()`
- 依存確認→引数解析→サブコマンド分岐→セッション開始という高レベルフローを司る。
- `list` / `help` / `reset` は対応するエージェント操作関数へ移譲し、それ以外はインタラクティブモードに遷移する。
- Ctrl+C で中断された場合は整形済みのメッセージを出し、トレースバックを抑制。

## データフローと依存
- `.commands`, `.config`, `.agent`, `.execution`, `.input`, `.ui` へ相互依存し、CLI 全体のオーケストレーターとして機能。
- `DEFAULT_TOOLS` として `strands_tools` 由来のツールを束ね、`create_agent_with_config` に渡す唯一の呼び出し元となる。
- `SessionState` は `simple_cli` と prompt_toolkit のトグルキー／ツールバーが共有する唯一の可変状態。

## エラーハンドリング指針
- 依存欠如時は説明付きで終了し、曖昧な状態で CLI を開始しない。
- 入力ループでは `EOFError`(Ctrl+D) と `KeyboardInterrupt` を個別扱いし、ユーザーにとって自然な終了導線を確保。
- `execute_task` 呼び出しでの例外は `main` 側で捕捉してメッセージ化し、Rich Markdown の表示崩れを防ぐ。

## 拡張ポイント / 注意事項
- 新サブコマンドを追加する場合は `parse_args` と `cli_main` の両方に最小限の分岐を追加し、ロジックを他モジュールへ委譲する。
- `DEFAULT_TOOLS` の拡張は `main()` のみで実施し、他モジュールが直接リストを編集しない。
- prompt_toolkit の設定は `input.create_prompt_session` 側に集約されているため、UI 変更時はそちらを修正し `simple_cli` を肥大化させない。
