<h1 align="center">Deepdiver CLI（パッケージ）</h1>
<p align="center">Strands Agents SDK ベースの対話型CLI実装</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
  <a href="README_EN.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Strands-Agents-2B6CB0" alt="Strands Agents">
  <img src="https://img.shields.io/badge/MCP-Supported-0B5D7A" alt="MCP Supported">
  <img src="https://img.shields.io/badge/Skills-Supported-0B5D7A" alt="Skills Supported">
  <img src="https://img.shields.io/badge/SubAgents-Supported-0B5D7A" alt="SubAgents Supported">
</p>

<p align="center">
  <img src="./assets/screen.png" alt="Deepdiver CLI screen" width="760">
</p>
<p align="center">Reference: [Image #1]</p>

このパッケージは、Strands Agents SDK 上に Deepdiver の対話型 CLI を実装したものです。ファイルシステム、シェル、HTTP などの共通ツールをラップし、エージェントプロファイル、Skills、SubAgents、MCP連携、JSONLトランスクリプトを提供します。

## 🧱 アーキテクチャ概要

```text
deepdiver/
├── __init__.py            # パッケージ公開API
├── __main__.py            # `python -m deepdiver` のエントリーポイント
├── agent.py               # エージェントライフサイクル（保存、プロンプト、リセット）
├── commands.py            # スラッシュコマンドとシェル連携
├── config.py              # 色設定、コンソール、モデル選択ヘルパー
├── csv_tool.py            # CSVフィルタリングヘルパー
├── default_agent_prompt.md
├── execution.py           # タスク実行とストリーミング補助
├── input.py               # prompt_toolkit設定と補完
├── main.py                # CLI全体制御 / 引数解析
├── mcp_tools.py           # MCPツール読み込み / エラーフィルタ
├── paths.py               # 共通パス（AGENT_ROOT, プロジェクトルート）
├── transcripts.py         # JSONLトランスクリプト + Codexロールアウトログ
├── ui.py                  # ヘルプ表示レンダラー
├── skills/                # Skillsシステム
├── subagents/             # SubAgentsシステム
└── examples/              # サンプル
```

## 🔑 主要モジュール

- **`agent.py`**: `~/.deepdiver/<agent>/` をバックエンドとして Strands `Agent` を生成。プロファイル一覧、リセット、システムプロンプト構築（`AGENT.md` を含む）を扱います。
- **`config.py`**: 環境変数読み込み、共通コンソール/色設定、`STRANDS_MODEL_PROVIDER` / `STRANDS_MODEL_CONFIG` によるモデル解決を提供します。
- **`execution.py`**: リクエスト正規化、参照ファイル文脈の注入、ストリーミング実行、非ストリーミングへのフォールバックを扱います。
- **`main.py`**: CLIフラグ解析、依存チェック、デフォルトツール登録、MCPツール読み込み、対話ループ実行を担います。
- **`mcp_tools.py`**: MCPツールを読み込み、ノイズの多いトランスポートエラーを抑制します。
- **`transcripts.py`**: JSONLトランスクリプトと Codex 互換ロールアウトログを書き込みます。
- **`skills/`**: Progressive disclosure 型の Skills システムと `/skills` コマンド。
- **`subagents/`**: SubAgents 定義、実行ランタイム、`/subagents` コマンド。

## 📦 エージェント保存先とプロンプト

- エージェントは `~/.deepdiver/<agent-name>/` 配下に保存されます。
- `AGENT.md` に長期指示を保存し、補助コンテキスト用に `memories/` サブディレクトリが作成されます。
- エージェントをリセットするとディレクトリを削除し、デフォルトプロンプトへ復元（または別エージェントの指示をコピー）します。

## 🧰 デフォルトツール

`main.py` は既定で以下の Strands ツールを登録します。

- `file_read`, `file_write`, `editor` - ファイルシステム操作
- `shell` - ターミナルコマンド実行（承認フローあり）
- `http_request` - 軽量HTTPリクエスト
- `environment` - 環境変数アクセス
- `calculator`, `current_time` - ユーティリティ
- `filter_csv_data` - CSVフィルタリング
- `delegate_to_subagent`, `delegate_to_subagents_parallel` - SubAgents委譲

`create_agent_with_config` を呼ぶ前に `DEFAULT_TOOLS` を拡張すれば、追加ツールを登録できます。

## 📝 JSONLトランスクリプト

トランスクリプトが有効な場合、CLI は `~/.deepdiver/` 配下にログを書き込みます。

- メインエージェント実行: `~/.deepdiver/<agent>/runs/agent-<run_id>.jsonl`
- ロールアウトセッション: `~/.deepdiver/sessions/YYYY/MM/DD/rollout-<timestamp>-<session_id>.jsonl`

無効化する場合:

```bash
export DEEPDIVER_TRANSCRIPT=0
```

## ⌨️ 対話コマンド

- `/help` - ショートカットとツールの概要表示
- `/skills` - Skills の管理と探索
- `/subagents` - SubAgents の管理
- `/mcp` - MCP サーバーステータス表示
- `/clear` - ターミナルクリア
- `/quit` または `/exit` - セッション終了
- `!<command>` - シェルコマンド実行（例: `!git status`）

## 🔌 MCP連携（設定方法）

Deepdiver はエージェント単位で MCP 設定を読み込みます。

- 設定ファイル: `~/.deepdiver/<agent-name>/mcp.json`
- 確認コマンド: `/mcp`
- 形式: ルートに `mcpServers` を置き、各サーバーに `url` か `command` のどちらかを指定

最小例（HTTP/SSE）:

```json
{
  "mcpServers": {
    "docs": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

最小例（stdio）:

```json
{
  "mcpServers": {
    "local": {
      "command": "node",
      "args": ["./server.js"],
      "env": {
        "API_KEY": "your_key"
      }
    }
  }
}
```

補足:

- `url` が `/sse` なら SSE として扱われます。
- それ以外の `url` は Streamable HTTP として扱われます。
- 接続に失敗した MCP サーバーは警告表示のうえスキップされ、CLI 全体は継続します。

## 🧩 Agent Skills（設定方法）

Skills は `SKILL.md` を持つディレクトリ単位で読み込まれます。

- ユーザーSkills: `~/.deepdiver/<agent-name>/skills/`
- プロジェクトSkills: `<git-root>/.deepdiver/skills/`
- 優先順位: 同名の場合は **プロジェクトSkillsが優先**
- 確認コマンド: `/skills`

ディレクトリ例:

```text
~/.deepdiver/agent/skills/
└── my-skill/
    └── SKILL.md
```

`SKILL.md` 最小例:

```markdown
---
name: my-skill
description: Explain how and when to use this skill.
---

# My Skill
Use this workflow when the user asks for ...
```

使い方:

- `/skills` で一覧表示
- `/skills <name>` で詳細表示
- 入力先頭で `$my-skill` を付けて実行（例: `$my-skill この課題を整理して`）

## 🚀 開発時の実行

```bash
# プロジェクトルートから
uv run python -m deepdiver

# または editable install
uv pip install -e .
deepdiver
```

## ⚙️ モデル設定

環境変数でモデル設定を行います。例:

```bash
export STRANDS_MODEL_PROVIDER=bedrock
export STRANDS_MODEL_CONFIG='{"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "region_name": "us-east-1"}'
```

OpenAI / Anthropic 系プロバイダでは既存のAPIキー変数（`OPENAI_API_KEY`, `ANTHROPIC_API_KEY` など）をそのまま使えます。`STRANDS_MODEL_PROVIDER` を省略すると、Strands Agent 側のデフォルト解決が使われます。

## 🛡️ Prompt Injection Defender

CLI はユーザー入力 / SubAgents入力に対する軽量な prompt-injection 防御機能を備えています。

```bash
export DEFENDER_ENABLED=true
export DEFENDER_DEFAULT_MODE=warn
export DEFENDER_WARN_THRESHOLD=0.35
export DEFENDER_BLOCK_THRESHOLD=0.95
export DEFENDER_SANITIZE_MODE=full-redact
```

- `DEFENDER_DEFAULT_MODE`: `warn`, `sanitize`, `block`
- `DEFENDER_SANITIZE_MODE`: 現在は `full-redact` のみサポート

## 📚 用語統一

このREADMEでは、複数形を含む機能名は **`SubAgents`** に統一して表記します。
