<h1 align="center">Deepdiver CLI</h1>
<p align="center">AWS Strands Agents SDK を用いた対話型コマンドラインインターフェース</p>
<p align="center"><strong>Version 0.0.8</strong></p>

## 概要

Deepdiver CLI は、AI エージェントと協働してタスクを実行するための対話型 CLI です。複数エージェントの管理、SubAgents、MCP、Skills を使った拡張に対応します。

## クイックスタート

```bash
pip install -e .

deepdiver
```

- モデル設定は `STRANDS_MODEL_PROVIDER` / `STRANDS_MODEL_CONFIG` で行います。
- `.env` を用意すれば `python-dotenv` が自動読み込みします。

## 機能概要

- エージェントと対話しながらタスクを実行
- 複数エージェントのプロファイル管理
- SubAgents による専門タスクの委譲
- MCP (Model Context Protocol) による外部ツール連携
- Skills による手順の再利用

## 必要要件

- Python 3.9+
- ネットワーク接続（各モデルプロバイダを使う場合）
- 必要に応じて API キー（Bedrock / OpenAI / Anthropic / Gemini など）

## セットアップ

### インストール

```bash
pip install --upgrade pip
pip install -e .
```

`uv` を利用する場合:

```bash
uv pip install -e .
```

### 主要依存パッケージ

- `strands-agents>=0.2.0` - Strands Agents SDK
- `strands-agents-tools>=0.2.0` - Strands ツールセット
- `boto3>=1.34.0` - Amazon Bedrock など AWS 連携向け
- `openai` - OpenAI API クライアント
- `pandas>=2.0.0` - データ分析
- `rich>=13.0.0` - リッチなターミナル出力
- `prompt-toolkit>=3.0.52` - 対話型入力
- `python-dotenv` - 環境変数管理
- `mcp` - Model Context Protocol サポート
- `requests` - HTTP リクエスト
- `tabulate>=0.9.0` - テーブル表示

## 環境変数（モデル設定）

### 基本

```bash
export STRANDS_MODEL_PROVIDER=bedrock
export STRANDS_MODEL_CONFIG='{"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "region_name": "us-east-1"}'
```

- `STRANDS_MODEL_PROVIDER` 未指定の場合は、Strands Agent 側のデフォルト設定が利用されます。
- `STRANDS_MODEL_CONFIG` は JSON 文字列または JSON ファイルパスを指定できます。
- `.env` を利用する場合は `python-dotenv` により自動で読み込まれます。

### プロバイダ別の補助環境変数

- Bedrock: `BEDROCK_MODEL_ID` / `STRANDS_MODEL_ID`, `BEDROCK_REGION` / `AWS_REGION`
- OpenAI: `OPENAI_MODEL` / `OPENAI_MODEL_ID`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- Anthropic: `ANTHROPIC_MODEL`, `ANTHROPIC_API_KEY`
- Ollama: `OLLAMA_MODEL` / `OLLAMA_MODEL_ID`, `OLLAMA_HOST`
- Gemini: `GEMINI_MODEL` / `GEMINI_MODEL_ID`, `GOOGLE_API_KEY` / `GEMINI_API_KEY`

<details>
<summary>設定例（.env）</summary>

#### OpenAI API

```env
STRANDS_MODEL_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-your-openai-key
STRANDS_MODEL_CONFIG='{"model_id": "gpt-4o-mini", "params": {"temperature": 0.2}}'
```

#### OpenAI互換（LiteLLMなど）

```env
STRANDS_MODEL_PROVIDER=openai
OPENAI_MODEL_ID=gpt-4o-mini
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=http://localhost:4000/v1
# STRANDS_MODEL_CONFIG='{"client_args": {"api_key": "your-api-key", "base_url": "http://localhost:4000/v1"}, "model_id": "gpt-4o-mini"}'
```

#### Gemini

```env
STRANDS_MODEL_PROVIDER=gemini
GEMINI_MODEL_ID=gemini-2.5-flash
GOOGLE_API_KEY=your-google-api-key
# STRANDS_MODEL_CONFIG='{"client_args": {"api_key": "your-google-api-key"}, "model_id": "gemini-2.5-flash", "params": {"temperature": 0.7, "max_output_tokens": 2048}}'
```

#### Ollama

```env
STRANDS_MODEL_PROVIDER=ollama
OLLAMA_MODEL_ID=llama3.1
OLLAMA_HOST=http://localhost:11434
# STRANDS_MODEL_CONFIG='{"model_id": "llama3.1", "host": "http://localhost:11434"}'
```

</details>

## 使い方

### 起動

```bash
# モジュールとして実行
python -m deepdiver

# uv を使用する場合
uv run python -m deepdiver

# インストール後はコマンドとして実行可能
deepdiver
# または
deepdiver-cli
```

### CLIオプション（例）

```bash
# エージェントを指定して起動（デフォルト: agent）
deepdiver --agent my-agent

# ツール使用時の承認を自動化（人間の確認なしで実行）
deepdiver --auto-approve

# 利用可能なエージェント一覧を表示
deepdiver list

# エージェントをリセット
deepdiver reset --agent my-agent

# 別のエージェントからプロンプトをコピーしてリセット
deepdiver reset --agent my-agent --target source-agent

# ヘルプを表示
deepdiver help
```

### キーボードショートカット

- `Enter` - 入力を送信
- `Alt+Enter` - 改行を挿入
- `Ctrl+E` - エディタを開く
- `Ctrl+T` - 自動承認モードの切り替え
- `Ctrl+C` - 実行を中断

## エージェント管理

CLI は複数のエージェントプロファイルを管理できます。各エージェントは `~/.deepdiver/<agent-name>/` に保存され、独立したメモリとプロンプト設定を持ちます。

```bash
deepdiver list

deepdiver reset --agent my-agent

deepdiver reset --agent my-agent --target source-agent
```

## SubAgents

Deepdiver は **SubAgents（サブエージェント）** の仕組みで、専門的なタスクを独立したエージェントに委譲できます。SubAgents は Markdown ファイル（YAML frontmatter 付き）として定義され、**progressive disclosure** 方式で管理されます。

### ディレクトリ構成

- ユーザー SubAgents: `~/.deepdiver/subagents/`
- プロジェクト SubAgents: `.deepdiver/subagents/`（git ルート配下、同名があればこちらが優先）

### 作成と実行

```bash
# ユーザー SubAgent を作成
deepdiver subagents create my-subagent

# プロジェクト SubAgent を作成
deepdiver subagents create my-subagent --project

# SubAgent を直接実行
deepdiver subagents run my-subagent --agent agent -- "タスクの説明"

# 以前の実行を再開
deepdiver subagents resume <run_id> my-subagent --agent agent -- "続きのタスク"
```

### 定義ファイルの形式

```md
---
name: code-reviewer
description: コードレビューを専門に行うサブエージェント
tools: file_read,editor
enable_skills: true
---

# Code Reviewer

## Purpose

コードレビューを専門に行い、バグや改善点を指摘します。

## When to Use

- コードの品質チェックが必要な場合
- セキュリティ問題の検出が必要な場合

## Instructions

1. コードを読み込み、構造を理解する
2. バグ、セキュリティ問題、パフォーマンス問題を検出
3. 改善提案を具体的に提示する
```

## MCP (Model Context Protocol)

Deepdiver は **MCP (Model Context Protocol)** をサポートしており、外部ツールやサービスをエージェントに統合できます。MCP サーバーはエージェントごとに設定され、stdio、SSE (Server-Sent Events)、Streamable HTTP の各トランスポートをサポートします。

### 設定方法

**設定ファイルの場所**: `~/.deepdiver/<agent-name>/mcp.json`

```json
{
  "mcpServers": {
    "taivily": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-taivily"],
      "env": {
        "TAIVILY_API_KEY": "your-api-key"
      }
    }
  }
}
```

### トランスポートタイプ

- stdio（標準入出力）
- SSE (Server-Sent Events)
- Streamable HTTP

### MCP サーバーの無効化

```json
{
  "mcpServers": {
    "server-name": {
      "command": "...",
      "disabled": true
    }
  }
}
```

### CLI 内での確認

```
/mcp
```

## Skills

Deepdiver は Agent Skills の仕組みを使って、専門的な手順やワークフローを追加できます。Skills は `SKILL.md` を含むフォルダとして管理され、必要なときにだけ読み込まれる **progressive disclosure** 方式です。

### ディレクトリ構成

- ユーザー技能: `~/.deepdiver/<agent>/skills/`
- プロジェクト技能: `.deepdiver/skills/`（git ルート配下）

### 使い方

- `/skills` でスキル一覧を表示
- `/skills` → Tab で `$skill ` を挿入して続けて入力
- `$plan 移行計画を立案してください。` のように指定すると、該当スキルの `SKILL.md` を読み込みます
- `$` を付けない場合は、LLM が文脈から自動選択します（該当時に SKILL.md を読む前提）

## デフォルトツール

CLI には以下のデフォルトツールが組み込まれています。

- `file_read` - ファイルの読み込み
- `file_write` - ファイルの書き込み
- `editor` - エディタでの編集
- `shell` - シェルコマンドの実行
- `http_request` - HTTP リクエストの送信
- `environment` - 環境変数の取得
- `calculator` - 計算の実行
- `current_time` - 現在時刻の取得
- `filter_csv_data` - CSV データのフィルタリング

MCP サーバーが設定されている場合、追加のツールも利用可能です。
