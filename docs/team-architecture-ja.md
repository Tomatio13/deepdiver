# Deepdiver Team 実装ドキュメント

本ドキュメントは、今回実装した tmux ベースの Team 機能について、構成・通信方式・運用方法・制約を整理したものです。

## 概要

Deepdiver Team は、1つの tmux セッション内で複数ロール（`team-lead`, `coder`, `reviewer` など）を独立プロセスとして起動し、ファイルベースのメッセージバスで協調動作させる仕組みです。

- `team-lead`: 対話型オーケストレータ
- `coder` / `reviewer` など: ワーカーロール
- 通信: `~/.deepdiver/teams/<session_id>/bus/*.jsonl`

## 画面レイアウト（tmux）

`deepdiver team start` で以下のレイアウトを作成します。

- 左側メインペイン: `team-lead`（常に固定）
- 右側: その他ロール（縦積み）

`--lead-width` で左ペイン幅を変更できます（40-85%）。

## 主要コマンド

```bash
# チーム起動
python -m deepdiver team start --roles team-lead,coder,reviewer --lead-width 55

# tmuxに入る
tmux attach -t deepdiver-<session_id>

# 外部送信
python -m deepdiver team send --session <session_id> --from team-lead --to coder -- "調査して"

# 受信確認
python -m deepdiver team inbox --session <session_id> --role team-lead --tail 20

# 状態確認
python -m deepdiver team status --session <session_id>

# 停止
python -m deepdiver team stop --session <session_id>
```

## team-lead の対話モード

team-lead ペインは通常チャット + ルーティングのハイブリッドです。

- 明示送信: `@coder 実装して`
- 自動ルーティング:
  - `coderで このバグ直して`
  - `reviewerに この変更レビューして`
  - `coder: ユニットテスト追加して`
- ロール確認: `/roles`
- 終了: `/quit`

ロール指定がない入力は、team-lead 自身の通常エージェント対話として処理します。

## メンバー間コミュニケーション

### 通信モデル

- 各ロールに専用チャンネル（`<role>.jsonl`）を持つ
- 送信時に受信側チャンネルへ1行JSONを追記
- ワーカーはオフセット管理で新着のみ購読
- 処理完了後、送信元へ `response` を返送

### メッセージ形式（概略）

```json
{
  "id": "abc123",
  "ts": 1738870000.0,
  "type": "task",
  "from": "team-lead",
  "to": "coder",
  "content": "実装してください",
  "parent_id": "..."
}
```

`type` は主に `task` / `instruction` / `response` を利用します。

## ワーカー実行仕様

- `coder` / `reviewer` などは受信後にタスクを実行
- 実行中は進捗ログを定期表示
  - `タスク開始`
  - `作業中...`
  - `タスク完了`
- ロール名と同名の Subagent 定義が存在する場合はそれを優先使用
- 定義がなければ通常Agentとして処理

## 実装ファイル

- `deepdiver/team_commands.py`: team CLI、tmux制御
- `deepdiver/team_worker.py`: workerループ、team-lead対話、進捗表示
- `deepdiver/team_bus.py`: JSONLメッセージバス
- `deepdiver/team_paths.py`: Teams関連パス管理
- `deepdiver/main.py`: `team` コマンド統合

## データ保存先

- セッション: `~/.deepdiver/teams/<session_id>/session.json`
- メッセージバス: `~/.deepdiver/teams/<session_id>/bus/`
- ワーカー状態（オフセット）: `~/.deepdiver/teams/<session_id>/state/`

## 制約・既知事項

- ファイルベース通信のため、分散環境向けではない（ローカル前提）
- 失敗時の自動再送・ACK保証は未実装
- 意図推定ルーティングはキーワードベースで誤判定余地あり
- team-leadの対話モードは通常CLIを完全再現するものではなく、Team運用向け簡易UI

## トラブルシュート

- `zsh: command not found: deepdiver`
  - `python -m deepdiver ...` で実行する（team startは内部でこの形式を使用）
- メッセージが見えない
  - `team-lead` の受信は `response` をリアルタイム表示
  - 併せて `team inbox` で確認
- レイアウトが意図と違う
  - `--lead-width` を調整して再起動

