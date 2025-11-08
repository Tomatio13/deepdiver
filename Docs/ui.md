# ddaword_cli/ui.py 詳細設計

## 役割
- CLI のヘルプ画面とインタラクティブヘルプ (`/help`) のレンダリングを担当し、利用者に提供する操作ガイドを集中管理する。
- Rich を通じてブランドカラー `COLORS` と ASCII バナー `DDAWORD_ASCII` を統一表示。

## 提供関数
### `show_interactive_help()`
- `/help` コマンド時に呼ばれ、コマンド一覧／編集ショートカット／特別機能をそれぞれセクション化して表示。
- `COMMANDS` ディクショナリを列挙して動的に説明を生成するため、新コマンド追加時も更新漏れが発生しない。

### `show_help()`
- `ddaword help` サブコマンドに対応する静的ヘルプ出力。
- 使い方、エージェント保存場所、インタラクティブ機能、コマンド一覧を順に説明し、CLI 未起動状態でも参照可能な情報を網羅。

## 依存
- `.config` から `COLORS`, `COMMANDS`, `DDAWORD_ASCII`, `console` を参照し、他モジュールとの整合性を確保。

## 拡張ガイド
- ヘルプ内容を増やす際はセクションごとに `console.print()` を追加し、ユーザーがスクロールなしで読める分量（上限 1 screen）を意識する。
- 国際化が必要になった場合は、このモジュールで文言を抽出し、翻訳辞書を噛ませることで CLI の他部分への影響を最小化できる。

### ヘルプ表示内容（`ui.show_interactive_help` 相当）
- **Interactive Commands**: `/help`, `/clear`, `/quit`, `/exit` など `COMMANDS` に登録されたパターンを自動列挙して説明。
- **Editing Features**: `Enter` の送信、`Alt+Enter/Ctrl+J` の改行挿入、`Ctrl+E` の外部エディタ起動、`Ctrl+T` の auto-approve トグルなど、主要ショートカットを表形式で提示。
- **Special Features**: `@filename` によるファイル挿入、`/command` のコマンド補完、`!command` のシェル実行といった入力モードの切り替えを案内し、ユーザが CLI 内の拡張操作を理解できるようにする。
