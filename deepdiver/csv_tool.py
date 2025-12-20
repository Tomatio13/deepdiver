"""CSV経営情報データの読み込みと絞り込みツール."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd
from strands import Agent, tool

from .config import create_model


# モデルインスタンスをキャッシュ（ツール呼び出しごとに作成しないように）
_cached_model: Any = None


def _get_model():
    """モデルインスタンスを取得（キャッシュを使用）。"""
    global _cached_model
    if _cached_model is None:
        _cached_model = create_model()
    return _cached_model


def _create_temp_agent(model: Any) -> Agent:
    """一時的なAgentインスタンスを作成（LLM呼び出し用）。
    
    Args:
        model: LLMモデルインスタンス
        
    Returns:
        一時的なAgentインスタンス
    """
    return Agent(
        model=model,
        system_prompt="あなたはCSVデータのフィルタリング専門家です。ユーザーの指示に基づいて、データを絞り込むための条件をJSON形式で生成してください。",
        tools=[],
    )


def _read_csv_with_encoding(csv_path: Path) -> pd.DataFrame:
    """エンコーディングを自動検出してCSVファイルを読み込む.
    
    Args:
        csv_path: CSVファイルのパス
        
    Returns:
        読み込んだDataFrame
        
    Raises:
        FileNotFoundError: ファイルが存在しない場合
        ValueError: CSVファイルの読み込みに失敗した場合
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
    
    # エンコーディングを順番に試す
    encodings = ["utf-8", "shift-jis", "cp932", "euc-jp", "latin-1"]
    
    for encoding in encodings:
        try:
            df = pd.read_csv(csv_path, encoding=encoding)
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            if encoding == encodings[-1]:
                # 最後のエンコーディングでも失敗した場合
                raise ValueError(f"CSVファイルの読み込みに失敗しました: {e}") from e
    
    # すべてのエンコーディングで失敗した場合
    raise ValueError("CSVファイルのエンコーディングを検出できませんでした")


def _build_column_info(df: pd.DataFrame, sample_rows: int = 3) -> str:
    """DataFrameのカラム情報を文字列として構築.
    
    Args:
        df: DataFrame
        sample_rows: サンプルデータの行数
        
    Returns:
        カラム情報を含む文字列
    """
    info_parts = ["## CSVファイルのカラム情報\n"]
    
    # カラム名とデータ型
    info_parts.append("### カラム一覧:\n")
    for col in df.columns:
        dtype = str(df[col].dtype)
        info_parts.append(f"- `{col}` (型: {dtype})")
    
    info_parts.append("\n### サンプルデータ（最初の数行）:\n")
    sample_df = df.head(sample_rows)
    info_parts.append(sample_df.to_string())
    
    info_parts.append(f"\n### データ概要:\n")
    info_parts.append(f"- 総行数: {len(df)}")
    info_parts.append(f"- 総列数: {len(df.columns)}")
    
    return "\n".join(info_parts)


async def _interpret_query_with_llm(
    query: str, column_info: str, model: Any
) -> dict[str, Any]:
    """LLMを使って自然言語指示を解釈し、フィルタ条件を生成.
    
    Args:
        query: 自然言語による絞り込み指示
        column_info: カラム情報の文字列
        model: LLMモデルインスタンス
        
    Returns:
        フィルタ条件を含む辞書
    """
    prompt = f"""以下のカラム情報とユーザーの指示に基づいて、データを絞り込むための条件を生成してください。

{column_info}

## ユーザーの指示:
{query}

## 出力形式:
以下のJSON形式で、フィルタ条件を返してください:
{{
    "filters": [
        {{
            "column": "カラム名",
            "operator": "演算子 (==, !=, >, <, >=, <=, contains, startswith, endswith)",
            "value": "値"
        }}
    ],
    "sort": {{
        "column": "ソートするカラム名（オプション）",
        "ascending": true
    }},
    "limit": 最大行数（オプション、指定がない場合はnull）
}}

複数の条件がある場合は、AND条件として扱います。
日付の比較の場合は、カラムの型に応じて適切な形式で値を指定してください。
文字列の部分一致には "contains" 演算子を使用してください。

JSONのみを返してください。説明文は不要です。"""

    response_text = ""
    try:
        # 一時的なAgentインスタンスを作成してLLMを呼び出す
        temp_agent = _create_temp_agent(model)
        
        # Agentのinvoke_asyncメソッドを使用
        if hasattr(temp_agent, "invoke_async"):
            response = await temp_agent.invoke_async(prompt)
        else:
            # フォールバック: 同期的に呼び出す
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: temp_agent.invoke(prompt))
        
        # レスポンスからテキストを抽出
        if hasattr(response, "output_text"):
            response_text = str(response.output_text)
        elif hasattr(response, "content"):
            response_text = str(response.content)
        elif isinstance(response, dict):
            response_text = str(response.get("output_text", response.get("content", response)))
        else:
            response_text = str(response)
        
        # JSON部分を抽出（```json や ``` で囲まれている場合がある）
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end != -1:
                response_text = response_text[start:end].strip()
            else:
                response_text = response_text[start:].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            if end != -1:
                response_text = response_text[start:end].strip()
            else:
                response_text = response_text[start:].strip()
        
        # JSONをパース
        conditions = json.loads(response_text)
        return conditions
    except json.JSONDecodeError as e:
        error_msg = f"LLMの応答をJSONとして解析できませんでした: {e}"
        if response_text:
            error_msg += f"\n応答内容: {response_text[:500]}"
        raise ValueError(error_msg) from e
    except Exception as e:
        raise ValueError(f"LLMによる指示の解釈に失敗しました: {e}") from e


def _apply_filters(df: pd.DataFrame, conditions: dict[str, Any]) -> pd.DataFrame:
    """フィルタ条件をDataFrameに適用.
    
    Args:
        df: 元のDataFrame
        conditions: フィルタ条件を含む辞書
        
    Returns:
        フィルタリングされたDataFrame
    """
    filtered_df = df.copy()
    
    # フィルタ条件を適用
    filters = conditions.get("filters", [])
    for filter_cond in filters:
        column = filter_cond.get("column")
        operator = filter_cond.get("operator", "==")
        value = filter_cond.get("value")
        
        if column not in df.columns:
            raise ValueError(f"カラム '{column}' が存在しません")
        
        # 演算子に応じてフィルタリング
        if operator == "==":
            filtered_df = filtered_df[filtered_df[column] == value]
        elif operator == "!=":
            filtered_df = filtered_df[filtered_df[column] != value]
        elif operator == ">":
            filtered_df = filtered_df[filtered_df[column] > value]
        elif operator == "<":
            filtered_df = filtered_df[filtered_df[column] < value]
        elif operator == ">=":
            filtered_df = filtered_df[filtered_df[column] >= value]
        elif operator == "<=":
            filtered_df = filtered_df[filtered_df[column] <= value]
        elif operator == "contains":
            filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(str(value), na=False)]
        elif operator == "startswith":
            filtered_df = filtered_df[filtered_df[column].astype(str).str.startswith(str(value), na=False)]
        elif operator == "endswith":
            filtered_df = filtered_df[filtered_df[column].astype(str).str.endswith(str(value), na=False)]
        else:
            raise ValueError(f"サポートされていない演算子: {operator}")
    
    # ソート
    sort_config = conditions.get("sort")
    if sort_config:
        sort_column = sort_config.get("column")
        ascending = sort_config.get("ascending", True)
        if sort_column and sort_column in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=sort_column, ascending=ascending)
    
    # 行数制限
    limit = conditions.get("limit")
    if limit is not None and isinstance(limit, int) and limit > 0:
        filtered_df = filtered_df.head(limit)
    
    return filtered_df


def _format_output(df: pd.DataFrame, output_format: str) -> str:
    """DataFrameを指定された形式で文字列に変換.
    
    Args:
        df: DataFrame
        output_format: 出力形式 ("csv", "json", "markdown")
        
    Returns:
        フォーマットされた文字列
    """
    if output_format == "csv":
        return df.to_csv(index=False)
    elif output_format == "json":
        return df.to_json(orient="records", force_ascii=False, indent=2)
    elif output_format == "markdown":
        # Markdownテーブル形式
        return df.to_markdown(index=False)
    else:
        raise ValueError(f"サポートされていない出力形式: {output_format}")


@tool
async def filter_csv_data(
    csv_path: str,
    query: str,
    output_format: str = "markdown",
) -> str:
    """CSVファイルを読み込み、自然言語指示に従ってデータを絞り込み、指定された形式で返却する.

    このツールは経営情報が記載されたCSVファイルを読み込み、親エージェントからの自然言語指示に従って
    データを絞り込みます。カラム情報は自動的に取得され、LLMが自然言語指示を解釈してフィルタ条件を
    生成します。

    Args:
        csv_path: CSVファイルのパス（相対パスまたは絶対パス）
        query: 自然言語による絞り込み指示（例: 「2024年の売上高が1000万円以上の行を抽出」）
        output_format: 出力形式。以下のいずれか: "csv", "json", "markdown"（デフォルト: "markdown"）

    Returns:
        絞り込まれたデータを指定された形式で文字列として返却

    Raises:
        FileNotFoundError: CSVファイルが存在しない場合
        ValueError: CSVファイルの読み込み、LLMによる指示解釈、またはフィルタ適用に失敗した場合

    Example:
        >>> result = await filter_csv_data(
        ...     csv_path="data/financial.csv",
        ...     query="2024年の売上高が1000万円以上の行を抽出",
        ...     output_format="markdown"
        ... )
    """
    try:
        # パスを解決（相対パスの場合は現在の作業ディレクトリ基準）
        csv_file = Path(csv_path)
        if not csv_file.is_absolute():
            csv_file = Path.cwd() / csv_file
        
        # CSVファイルを読み込む
        df = _read_csv_with_encoding(csv_file)
        
        # カラム情報を構築
        column_info = _build_column_info(df)
        
        # LLMモデルを取得
        model = _get_model()
        if model is None:
            raise ValueError(
                "LLMモデルが設定されていません。"
                "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
            )
        
        # LLMを使って自然言語指示を解釈
        conditions = await _interpret_query_with_llm(query, column_info, model)
        
        # フィルタ条件を適用
        filtered_df = _apply_filters(df, conditions)
        
        # 結果が空の場合のメッセージ
        if len(filtered_df) == 0:
            return f"絞り込み条件に一致するデータが見つかりませんでした。\n\n{column_info}"
        
        # 指定された形式で出力
        result = _format_output(filtered_df, output_format)
        
        return result
        
    except FileNotFoundError as e:
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}") from e
    except ValueError as e:
        raise ValueError(f"データ処理エラー: {e}") from e
    except Exception as e:
        raise ValueError(f"予期しないエラーが発生しました: {e}") from e

