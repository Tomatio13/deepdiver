# ddaword_cli/config.py 詳細設計

## 役割
- CLI 全体で共有する定数（色・ASCII バナー・コマンド一覧・表示上限等）と Rich の `Console` インスタンスを一元管理。
- `.env` 読み込みやモデル生成ユーティリティを提供し、環境変数ベースの設定パターンを統一。
- prompt_toolkit に渡す `SessionState` の実装を保持し、UI と実行層で共有できる状態管理を行う。

## 主な構成要素
### グローバル定数
- `COLORS`, `DDAWORD_ASCII`, `COMMANDS`, `MAX_ARG_LENGTH` など UI／入力補助で利用される値を定義し、他モジュールからの再定義を防ぐ。

### `console`
- `rich.console.Console` を `highlight=False` で初期化し、全モジュールが同一インスタンスを共有。出力スタイルの一貫性と Rich の自動ハイライト抑止を保証。

### `SessionState`
- `auto_approve` フラグのみを保持する軽量クラス。`toggle_auto_approve()` により状態遷移を行い、prompt_toolkit バインディングから直接呼べる。

### `get_default_coding_instructions()`
- `default_agent_prompt.md` を読み込み、エージェント初期化時のシステムメモリに利用される不変プロンプトを返す。

### モデル生成関連
- `MODEL_CLASS_BY_PROVIDER` でプロバイダ文字列と Strands モデル実装のマッピングを保持。
- `_load_model_config()` は `STRANDS_MODEL_CONFIG` の JSON／ファイル参照を解析し、プロバイダ固有の環境変数上書きを統合して辞書を返す。
- `_sanitize_config_for_display()` で `api_key` 等のセンシティブ値を `***` へマスクし、ログ出力時に漏洩を防止。
- `create_model()` は `STRANDS_MODEL_PROVIDER` を起点にモデルクラスを動的 import し、生成時エラーを Rich で通知。

## 依存関係
- `dotenv.load_dotenv()` をモジュール import 時に実行し、環境設定が CLI 全体に即時反映されるよう設計。
- `strands` への依存は `create_model()` 実行時に限定し、CLI 自体はモデル未設定でも起動できる。

## エラーハンドリング
- JSON decode 失敗やモジュール import 失敗時には Rich の警告／エラーメッセージを表示し、None を返してフォールバック。
- `create_model()` は例外を握りつぶさず捕捉した上で `None` を返し、上位層がモデル未設定状態で継続可能。

## 拡張指針
- プロバイダ追加時は `MODEL_CLASS_BY_PROVIDER` と `_load_model_config` に分離されたロジックを追加し、`create_model` の条件分岐を増やさない。
- `SessionState` にフィールドを増設する際は prompt_toolkit の UI 表示（`input.py`）と CLI ループ（`main.simple_cli`）の双方に波及する点へ注意。
