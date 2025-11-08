# ddaword_cli/__main__.py 詳細設計

## 目的
- `python -m ddaword_cli` 実行時のエントリーポイントを提供し、`ddaword_cli.main.cli_main` を呼び出す薄いラッパーとして機能する。

## 振る舞い
- import 時に副作用を持たず、`if __name__ == "__main__":` ブロックから `cli_main()` を起動するのみ。
- `setup.cfg` 等で `python -m` 実行を許可するために必要な慣習的モジュール。

## メンテナンス注意
- CLI の初期化ロジックはすべて `main.py` へ集約されているため、本ファイルにロジックを追加しない。
