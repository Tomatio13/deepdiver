# DDAWord CLI (WIP)

このリポジトリは、既存の DDAWord ベースのCLIを AWS Strands Agents SDK を用いた実装へ移行中です。

## セットアップ

```bash
pip install --upgrade pip
pip install -e .
```

もしくは `uv` を利用している場合:

```bash
uv pip install -e .
```

## 主要依存パッケージ

- `strands-agents`
- `strands-agents-tools`
- `boto3` (Amazon Bedrock など AWS 連携向け)

Strands Agents では AWS 資格情報 (例: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`) や各モデルプロバイダの API キーが必要になることがあります。`.env` を利用する場合は `python-dotenv` により自動で読み込まれます。

## 実行

開発中は次のコマンドで CLI を起動できます。

```bash
uv run python -m ddaword_cli
```

モデル設定は環境変数で行います。例:

```bash
export STRANDS_MODEL_PROVIDER=bedrock
export STRANDS_MODEL_CONFIG='{"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "region_name": "us-east-1"}'
```

`STRANDS_MODEL_PROVIDER` を指定しない場合は、Strands Agent 側のデフォルト設定が利用されます。

## モデル設定の詳細

`ddaword_cli/config.py` では `STRANDS_MODEL_PROVIDER` をもとに Strands の各モデルクラス（`BedrockModel` / `OpenAIModel` / `AnthropicModel` / `OllamaModel` / `GeminiModel`）を動的に生成します。主な環境変数は次の通りです。

- `STRANDS_MODEL_PROVIDER`: 利用するプロバイダ名（`bedrock` / `openai` / `anthropic` / `ollama` / `gemini`）。未指定の場合は CLI がエージェントのデフォルトモデルにフォールバックします。
- `STRANDS_MODEL_CONFIG`: JSON文字列または JSON ファイルへのパス。`model_id` や `region_name` など各モデルクラスの初期化パラメータを定義できます。ファイルパスを渡した場合は CLI が内容を読み取ってマージします。

プロバイダごとの補助的な環境変数:

- Bedrock: `BEDROCK_MODEL_ID` もしくは `STRANDS_MODEL_ID`、`BEDROCK_REGION` もしくは `AWS_REGION`。これらが設定されていれば `STRANDS_MODEL_CONFIG` とマージされます。
- OpenAI: `OPENAI_MODEL` または `OPENAI_MODEL_ID`（モデルID）、`OPENAI_API_KEY`（APIキー）、`OPENAI_BASE_URL`（OpenAI互換サーバーのベースURL、オプション）。LiteLLMなどのOpenAI互換プロバイダに接続する場合は `OPENAI_BASE_URL` を設定してください。
- Anthropic: `ANTHROPIC_MODEL`, `ANTHROPIC_API_KEY`
- Gemini: `GEMINI_MODEL` または `GEMINI_MODEL_ID`（モデルID）、`GOOGLE_API_KEY` または `GEMINI_API_KEY`（APIキー）。Google AI StudioからAPIキーを取得できます。

`.env` を利用する場合は `python-dotenv` により自動で読み込まれます。値に API キーなど機密情報を含めたくない場合はファイルパスを `STRANDS_MODEL_CONFIG` に渡し、JSON 内の該当キーだけを管理する運用も可能です。

### OpenAI 向け `.env` サンプル

`.env.example` をコピーして `.env` を作成し、以下のように設定できます。

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
