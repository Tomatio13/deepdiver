# DDAWord CLI

DDAWord CLI は、AWS Strands Agents SDK を用いた対話型コマンドラインインターフェースです。AI エージェントと協働してタスクを実行できます。

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
- `pandas>=2.0.0` - データ分析（Consulting ワークフロー用）
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
python -m ddaword_cli

# または、uv を使用する場合
uv run python -m ddaword_cli

# インストール後はコマンドとしても実行可能
ddaword
# または
ddaword-cli
```

### CLI オプション

```bash
# エージェントを指定して起動（デフォルト: agent）
ddaword --agent my-agent

# ツール使用時の承認を自動化（人間の確認なしで実行）
ddaword --auto-approve

# 利用可能なエージェント一覧を表示
ddaword list

# エージェントをリセット
ddaword reset --agent my-agent

# 別のエージェントからプロンプトをコピーしてリセット
ddaword reset --agent my-agent --target source-agent

# ヘルプを表示
ddaword help
```

### キーボードショートカット

CLI 実行中に使用できるショートカット:

- `Enter` - 入力を送信
- `Alt+Enter` - 改行を挿入
- `Ctrl+E` - エディタを開く
- `Ctrl+T` - 自動承認モードの切り替え
- `Ctrl+C` - 実行を中断

## Consulting ワークフロー

本 CLI には、売上・人事など複数の CSV を読み込み経営課題を抽出するコンサルティング用エージェントが同梱されています。操作は `/consulting:*` スラッシュコマンドで行います。

### 1. 初期化

```bash
/consulting:init "<analysis_focus>" <csv_path1> [csv_path2] ...
```

- `analysis_focus` をもとに、**英小文字のみ / 数字なし / `単語_単語` 形式 (最大24文字)** の `project_name` が自動生成されます。
- ファイルだけでなくフォルダ指定も可能（再帰的に `.csv` を収集）。
- プロジェクトごとに `.consulting/<project_name>/` 以下へ状態 (`consulting.json`) と成果物 Markdown を保存します。

### 2. ワークフローの流れ

| ステップ | コマンド例 | 内容 |
| --- | --- | --- |
| 仮説立案 | `/consulting:hypothesis <project_name>` | CSV を横断し経営課題の仮説を生成 |
| データ加工 | `/consulting:process-data <project_name>` | 仮説検証に必要な指標を抽出・加工 |
| 仮説検証 | `/consulting:validate <project_name>` | 仮説をデータで検証し結論を出力 |
| 戦略立案 | `/consulting:strategy <project_name>` | 検証済み課題に対する施策を提案 |
| レポート生成 | `/consulting:report <project_name>` | 全成果を統合した最終レポートを作成 |

各ステップ完了後は `/consulting:approve <project_name>` で承認、もしくは `/consulting:reject <project_name>` で否決します。否決時には CLI が理由入力を求め、内容は `feedback` として保存され次回のプロンプトに反映されます。否決ステップに応じてワークフローが適切な位置まで巻き戻ります（例: レポート否決→戦略ステップに戻る）。

### 3. 状態確認

```bash
/consulting:status [project_name]
```

- 現在の状態・成果物・フィードバック履歴を表示します。
- 状況に応じて推奨される次のコマンド（例: `/consulting:hypothesis <project_name>`）が案内されます。
- `project_name` を省略すると最新のプロジェクトが対象です。

### 4. 成果物

プロジェクトディレクトリには下記 Markdown が生成されます。

- `hypotheses.md` – 仮説一覧
- `processed_data.md` – 検証用データの加工結果
- `validation_results.md` – 仮説検証レポート
- `strategies.md` – 戦略提案
- `report.md` – 最終レポート

必要に応じてエディタで内容を確認し、承認／否決を繰り返してブラッシュアップしてください。

### 5. メモリ構造

コンサルティング機能は、認知科学のメモリモデルに基づいて情報を管理しています。

#### 1. ワーキングメモリ（Working Memory）: 現在の会話・作業文脈

現在の分析プロジェクトの状態と進捗を保持します。

- **`.consulting/<project_name>/consulting.json`** - プロジェクトの現在状態
  - `current_step`: 現在実行中のステップ（`hypothesis`, `process_data`, `validate`, `strategy`, `report`）
  - `status`: 現在のフェーズと状態（例: `report_approved`, `validate_rejected`）
  - `steps.<step>.status`: 各ステップの状態（`pending`, `in_progress`, `completed`, `approved`, `rejected`）
  - `steps.<step>.approved`: 承認フラグ（`true`/`false`/`null`）
  - `analysis_focus`: 分析の焦点（初期化時に設定）
  - `csv_paths`: 読み込まれたCSVファイルのパス一覧

- **各ステップの成果物ファイル** - 現在のステップで生成された最新の内容
  - `hypotheses.md` - 仮説一覧（仮説立案ステップ）
  - `processed_data.md` - 加工済みデータ（データ加工ステップ）
  - `validation_results.md` - 検証結果（仮説検証ステップ）
  - `strategies.md` - 戦略提案（戦略立案ステップ）
  - `report.md` - 最終レポート（レポート生成ステップ）

#### 2. エピソード記憶（Episodic Memory）: 過去の出来事の履歴

プロジェクトの実行履歴と承認プロセスを記録します。

- **`consulting.json` のタイムスタンプ**
  - `created_at`: プロジェクト作成日時
  - `updated_at`: 最終更新日時
  - `steps.<step>.completed_at`: 各ステップの完了日時

- **承認・否決の履歴**
  - `steps.<step>.approved`: 承認フラグの推移（`null` → `true`/`false`）
  - `steps.<step>.feedback[]`: フィードバック履歴
    - `reason`: 否決理由や改善要望
    - `timestamp`: フィードバックの日時
  - 否決時のワークフロー巻き戻し履歴（例: レポート否決 → 戦略ステップに戻る）

- **Git 履歴**（オプション）
  - `.consulting/<project_name>/` ディレクトリをGitで管理することで、各成果物ファイルの版管理が可能

#### 3. 意味記憶（Semantic Memory）: 事実・知識のストック

分析で得られた知見と構造化された知識を保存します。

- **分析成果物（Markdownファイル）**
  - `hypotheses.md` - 抽出された経営課題の仮説と根拠
  - `processed_data.md` - 検証用に加工された指標とデータ
  - `validation_results.md` - 仮説検証の結果と結論
  - `strategies.md` - 検証済み課題に対する施策提案
  - `report.md` - 全成果を統合した最終レポート

- **プロジェクトメタデータ**
  - `analysis_focus`: 分析の焦点（初期化時に設定）
  - `csv_paths`: 使用したデータソースの記録

- **プロンプトテンプレート**（`ddaword_cli/consulting_prompts.py`）
  - 各ステップの標準的なプロンプトテンプレート
  - 可視化指針（matplotlib/seaborn）などの知識ベース

#### 4. 手続き記憶（Procedural Memory）: 行動規則・How to

ワークフローの実行手順と各ステップの処理方法を定義します。

- **スラッシュコマンドのワークフロー**
  ```
  /consulting:init → /consulting:hypothesis → /consulting:process-data 
  → /consulting:validate → /consulting:strategy → /consulting:report
  ```

- **各ステップの処理手順**（`ddaword_cli/consulting_agents.py`）
  - `generate_hypotheses()`: CSVを横断し経営課題の仮説を生成
  - `process_data_for_validation()`: 仮説検証に必要な指標を抽出・加工
  - `validate_hypotheses()`: 仮説をデータで検証し結論を出力
  - `plan_strategies()`: 検証済み課題に対する施策を提案
  - `generate_consulting_report()`: 全成果を統合した最終レポートを作成

- **Human-in-the-Loop プロセス**
  - 各ステップ完了後の承認フロー（`/consulting:approve` / `/consulting:reject`）
  - 否決時のフィードバック収集とワークフロー巻き戻しロジック
  - 状態に応じた次のコマンド推奨（`/consulting:status`）

- **状態管理ロジック**（`ddaword_cli/consulting_state.py`）
  - ステップ状態の更新（`update_step_status()`）
  - 承認・否決の処理（`approve_step()`, `reject_step()`）
  - フィードバックの追加（`add_feedback()`）

## モデル設定

### 概要

`ddaword_cli/config.py` では `STRANDS_MODEL_PROVIDER` をもとに Strands の各モデルクラス（`BedrockModel` / `OpenAIModel` / `AnthropicModel` / `OllamaModel` / `GeminiModel`）を動的に生成します。

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

`STRANDS_MODEL_CONFIG` はファイルパス（例: `./model-config.json`）を指すように設定することもできます。Strands CLI 起動時に `python-dotenv` が `.env` を読み込むため、追加の読み込み処理は不要です。

## サンプルデータ

経営コンサルエージェントの動作確認用に、`sample_data/` ディレクトリにサンプル CSV ファイルを用意しています。

- `sample_sales_data.csv` - 売上データ（2024年1月〜6月）
- `sample_hr_data.csv` - 人事情報データ（2024年1月〜6月）
- `sample_customer_data.csv` - 顧客データ（2024年1月〜6月）
- `sample_financial_data.csv` - 財務データ

詳細は `sample_data/README_CONSULTING_SAMPLES.md` を参照してください。

### サンプルデータを使用した分析例

```bash
# 単一ファイルでの分析
/consulting:init "売上向上と利益率改善" sample_data/sample_sales_data.csv

# 複数ファイルでの分析
/consulting:init "売上と人事の総合分析" sample_data/sample_sales_data.csv sample_data/sample_hr_data.csv

# フォルダ指定での分析（再帰的にCSVを収集）
/consulting:init "総合経営分析" sample_data/
```

## エージェント管理

CLI は複数のエージェントプロファイルを管理できます。各エージェントは `~/.strands-agents-cli/<agent-name>/` に保存され、独立したメモリとプロンプト設定を持ちます。

### エージェントの一覧表示

```bash
ddaword list
```

### エージェントのリセット

エージェントのメモリとプロンプトをリセットします:

```bash
# エージェントを完全にリセット
ddaword reset --agent my-agent

# 別のエージェントからプロンプトをコピーしてリセット
ddaword reset --agent my-agent --target source-agent
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
