# Deepdiver CLI

Deepdiver CLI は、AWS Strands Agents SDK を用いた対話型コマンドラインインターフェースです。AI エージェントと協働してタスクを実行できます。

**バージョン**: 0.0.8

## セットアップ

### インストール

```bash
pip install --upgrade pip
pip install -e .
```

もしくは `uv` を利用している場合:

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

Strands Agents では AWS 資格情報 (例: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`) や各モデルプロバイダの API キーが必要になることがあります。`.env` を利用する場合は `python-dotenv` により自動で読み込まれます。

## 実行

### 基本的な起動方法

インストール後、以下のいずれかの方法で CLI を起動できます:

```bash
# モジュールとして実行
python -m deepdiver

# または、uv を使用する場合
uv run python -m deepdiver

# インストール後はコマンドとしても実行可能
deepdiver
# または
deepdiver-cli
```

### CLI オプション

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

CLI 実行中に使用できるショートカット:

- `Enter` - 入力を送信
- `Alt+Enter` - 改行を挿入
- `Ctrl+E` - エディタを開く
- `Ctrl+T` - 自動承認モードの切り替え
- `Ctrl+C` - 実行を中断

## モデル設定

### 概要

`deepdiver_cli/config.py` では `STRANDS_MODEL_PROVIDER` をもとに Strands の各モデルクラス（`BedrockModel` / `OpenAIModel` / `AnthropicModel` / `OllamaModel` / `GeminiModel`）を動的に生成します。

### 基本的な設定方法

モデル設定は環境変数で行います。例:

```bash
export STRANDS_MODEL_PROVIDER=bedrock
export STRANDS_MODEL_CONFIG='{"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "region_name": "us-east-1"}'
```

`STRANDS_MODEL_PROVIDER` を指定しない場合は、Strands Agent 側のデフォルト設定が利用されます。

### 詳細設定

主な環境変数は次の通りです。

- `STRANDS_MODEL_PROVIDER`: 利用するプロバイダ名（`bedrock` / `openai` / `anthropic` / `ollama` / `gemini`）。未指定の場合は CLI がエージェントのデフォルトモデルにフォールバックします。
- `STRANDS_MODEL_CONFIG`: JSON文字列または JSON ファイルへのパス。`model_id` や `region_name` など各モデルクラスの初期化パラメータを定義できます。ファイルパスを渡した場合は CLI が内容を読み取ってマージします。

プロバイダごとの補助的な環境変数:

- Bedrock: `BEDROCK_MODEL_ID` もしくは `STRANDS_MODEL_ID`、`BEDROCK_REGION` もしくは `AWS_REGION`。これらが設定されていれば `STRANDS_MODEL_CONFIG` とマージされます。
- OpenAI: `OPENAI_MODEL` または `OPENAI_MODEL_ID`（モデルID）、`OPENAI_API_KEY`（APIキー）、`OPENAI_BASE_URL`（OpenAI互換サーバーのベースURL、オプション）。LiteLLMなどのOpenAI互換プロバイダに接続する場合は `OPENAI_BASE_URL` を設定してください。
- Anthropic: `ANTHROPIC_MODEL`, `ANTHROPIC_API_KEY`
- Ollama: `OLLAMA_MODEL` または `OLLAMA_MODEL_ID`（モデルID）、`OLLAMA_HOST`（OllamaサーバーURL）
- Gemini: `GEMINI_MODEL` または `GEMINI_MODEL_ID`（モデルID）、`GOOGLE_API_KEY` または `GEMINI_API_KEY`（APIキー）。Google AI StudioからAPIキーを取得できます。

`.env` を利用する場合は `python-dotenv` により自動で読み込まれます。値に API キーなど機密情報を含めたくない場合はファイルパスを `STRANDS_MODEL_CONFIG` に渡し、JSON 内の該当キーだけを管理する運用も可能です。

### `.env` ファイルの作成

プロジェクトルートに `.env` ファイルを作成し、以下のように設定できます。

#### 標準のOpenAI APIを使用する場合

```env
STRANDS_MODEL_PROVIDER=openai

# OpenAI SDK と Strands モデル双方で参照される値
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-your-openai-key

# JSON 文字列でモデルパラメータを注入（必要に応じて温度なども指定）
STRANDS_MODEL_CONFIG='{"model_id": "gpt-4o-mini", "params": {"temperature": 0.2}}'
```

#### LiteLLMなどのOpenAI互換プロバイダを使用する場合

```env
STRANDS_MODEL_PROVIDER=openai

# モデルIDとAPIキー
OPENAI_MODEL_ID=gpt-4o-mini
OPENAI_API_KEY=your-api-key

# OpenAI互換サーバーのベースURL（LiteLLMなど）
OPENAI_BASE_URL=http://localhost:4000/v1

# または、STRANDS_MODEL_CONFIGで設定することも可能
# STRANDS_MODEL_CONFIG='{"client_args": {"api_key": "your-api-key", "base_url": "http://localhost:4000/v1"}, "model_id": "gpt-4o-mini"}'
```

#### Gemini 向け `.env` サンプル

```env
STRANDS_MODEL_PROVIDER=gemini

# モデルIDとAPIキー
GEMINI_MODEL_ID=gemini-2.5-flash
GOOGLE_API_KEY=your-google-api-key

# または、STRANDS_MODEL_CONFIGで設定することも可能
# STRANDS_MODEL_CONFIG='{"client_args": {"api_key": "your-google-api-key"}, "model_id": "gemini-2.5-flash", "params": {"temperature": 0.7, "max_output_tokens": 2048}}'
```

#### Ollama 向け `.env` サンプル

```env
STRANDS_MODEL_PROVIDER=ollama

# モデルIDとホスト
OLLAMA_MODEL_ID=llama3.1
OLLAMA_HOST=http://localhost:11434

# または、STRANDS_MODEL_CONFIGで設定することも可能
# STRANDS_MODEL_CONFIG='{"model_id": "llama3.1", "host": "http://localhost:11434"}'
```

`STRANDS_MODEL_CONFIG` はファイルパス（例: `./model-config.json`）を指すように設定することもできます。Strands CLI 起動時に `python-dotenv` が `.env` を読み込むため、追加の読み込み処理は不要です。

## エージェント管理

CLI は複数のエージェントプロファイルを管理できます。各エージェントは `~/.deepdiver/<agent-name>/` に保存され、独立したメモリとプロンプト設定を持ちます。

### エージェントの一覧表示

```bash
deepdiver list
```

### エージェントのリセット

エージェントのメモリとプロンプトをリセットします:

```bash
# エージェントを完全にリセット
deepdiver reset --agent my-agent

# 別のエージェントからプロンプトをコピーしてリセット
deepdiver reset --agent my-agent --target source-agent
```

## デフォルトツール

CLI には以下のデフォルトツールが組み込まれています:

- `file_read` - ファイルの読み込み
- `file_write` - ファイルの書き込み
- `editor` - エディタでの編集
- `shell` - シェルコマンドの実行
- `http_request` - HTTP リクエストの送信
- `environment` - 環境変数の取得
- `calculator` - 計算の実行
- `current_time` - 現在時刻の取得
- `filter_csv_data` - CSV データのフィルタリング

MCP (Model Context Protocol) サーバーが設定されている場合、追加のツールも利用可能です。

## SubAgents

Deepdiver は **SubAgents（サブエージェント）** の仕組みを使って、専門的なタスクを独立したエージェントに委譲できます。SubAgents は Markdown ファイル（YAML frontmatter 付き）として定義され、**progressive disclosure** 方式で管理されます。

### ディレクトリ構成

- ユーザー SubAgents: `~/.deepdiver/subagents/`
- プロジェクト SubAgents: `.deepdiver/subagents/`（git ルート配下、同名があればこちらが優先）

### SubAgent の作成

```bash
# ユーザー SubAgent を作成
deepdiver subagents create my-subagent

# プロジェクト SubAgent を作成
deepdiver subagents create my-subagent --project
```

### SubAgent 定義ファイルの形式

SubAgent は Markdown ファイルとして定義します:

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

### SubAgent の管理コマンド

```bash
# SubAgent 一覧を表示
deepdiver subagents list

# プロジェクト SubAgent のみ表示
deepdiver subagents list --project

# SubAgent の詳細情報を表示
deepdiver subagents info my-subagent

# SubAgent を直接実行
deepdiver subagents run my-subagent --agent agent -- "タスクの説明"

# 以前の実行を再開
deepdiver subagents resume <run_id> my-subagent --agent agent -- "続きのタスク"
```

### メインエージェントからの使用

メインエージェントは、以下のツールを使って SubAgent にタスクを委譲できます:

- `delegate_to_subagent(name=..., task=...)` - 単一の SubAgent にタスクを委譲
- `delegate_to_subagents_parallel(requests=[...])` - 複数の SubAgent に並列でタスクを委譲

SubAgent は独立したコンテキストで実行され、必要に応じてツールアクセスを制限できます。また、メインエージェントの Skills や MCP ツールも利用可能です（設定により制限可能）。

### CLI 内での使用

CLI 実行中に `/subagents` コマンドで SubAgent を直接実行することもできます:

```
/subagents my-subagent タスクの説明
```

## MCP (Model Context Protocol)

Deepdiver は **MCP (Model Context Protocol)** をサポートしており、外部ツールやサービスをエージェントに統合できます。MCP サーバーはエージェントごとに設定され、stdio、SSE (Server-Sent Events)、Streamable HTTP の各トランスポートをサポートします。

### 設定方法

各エージェントのディレクトリに `mcp.json` ファイルを作成して MCP サーバーを設定します:

**設定ファイルの場所**: `~/.deepdiver/<agent-name>/mcp.json`

### mcp.json の形式

```json
{
  "mcpServers": {
    "taivily": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-taivily"],
      "env": {
        "TAIVILY_API_KEY": "your-api-key"
      }
    },
    "weather": {
      "url": "http://localhost:3000/sse",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    },
    "filesystem": {
      "command": "uvx",
      "args": ["mcp-server-filesystem", "/path/to/allowed/directory"],
      "env": {}
    }
  }
}
```

### トランスポートタイプ

#### stdio（標準入出力）

```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["-m", "mcp_server_module"],
      "env": {
        "API_KEY": "value"
      }
    }
  }
}
```

#### SSE (Server-Sent Events)

```json
{
  "mcpServers": {
    "server-name": {
      "url": "http://localhost:3000/sse"
    }
  }
}
```

#### Streamable HTTP

```json
{
  "mcpServers": {
    "server-name": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  }
}
```

### MCP サーバーの無効化

特定の MCP サーバーを一時的に無効化するには、`disabled` フラグを設定します:

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

CLI 実行中に `/mcp` コマンドで設定済みの MCP サーバー情報を確認できます:

```
/mcp
```

### SubAgent での MCP 利用

SubAgent 定義の `tools` フィールドで MCP ツールを指定すると、その SubAgent は必要な MCP サーバーのみを読み込みます。これにより、不要な MCP サーバーの起動を避け、パフォーマンスを向上させることができます。

例:

```md
---
name: weather-checker
description: 天気予報を取得するサブエージェント
tools: weather_get_forecast,current_time
---
```

この場合、`weather` プレフィックスを持つ MCP サーバーのみが読み込まれます。

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

### SKILL.md の例

```md
---
name: plan
description: Generate a plan for how an agent should accomplish a complex coding task.
---

# Plan
...
```
