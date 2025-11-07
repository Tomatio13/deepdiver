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
