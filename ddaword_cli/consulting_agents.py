"""経営コンサルエージェントのサブエージェント実装."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd
from strands import Agent

from .config import create_model
from .consulting_prompts import CONSULTING_PROMPTS
from .consulting_state import get_project_dir, load_state

# モデルキャッシュ
_cached_model: Any = None


def _get_model():
    """モデルインスタンスを取得（キャッシュを使用）。"""
    global _cached_model
    if _cached_model is None:
        _cached_model = create_model()
    return _cached_model


def _create_consulting_agent(agent_type: str, model: Any) -> Agent:
    """指定されたタイプのコンサルティングエージェントを作成。
    
    Args:
        agent_type: エージェントタイプ（"hypothesis_generator"など）
        model: LLMモデルインスタンス
        
    Returns:
        エージェントインスタンス
    """
    prompt = CONSULTING_PROMPTS.get(agent_type, "")
    return Agent(
        model=model,
        system_prompt=prompt,
        tools=[],
    )


async def _invoke_agent_async(agent: Agent, prompt: str) -> str:
    """エージェントを非同期で呼び出し、結果を文字列で返す。"""
    if hasattr(agent, "invoke_async"):
        response = await agent.invoke_async(prompt)
    else:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: agent.invoke(prompt))
    
    # レスポンスからテキストを抽出
    if hasattr(response, "output_text"):
        return str(response.output_text)
    elif hasattr(response, "content"):
        return str(response.content)
    elif isinstance(response, dict):
        return str(response.get("output_text", response.get("content", response)))
    return str(response)


async def generate_project_name(analysis_focus: str) -> str:
    """analysis_focusから英数字20文字程度のユニークなproject_nameを生成する。
    
    Args:
        analysis_focus: 分析の焦点
        
    Returns:
        プロジェクト名（英数字20文字程度）
    """
    model = _get_model()
    if model is None:
        raise ValueError(
            "LLMモデルが設定されていません。"
            "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
        )
    
    agent = Agent(
        model=model,
        system_prompt="あなたはプロジェクト名生成の専門家です。分析の焦点を表す、英数字のみで構成された20文字程度のユニークなプロジェクト名を生成してください。",
        tools=[],
    )
    
    prompt = f"""
以下の分析の焦点を表す、英数字のみで構成された20文字程度のユニークなプロジェクト名を生成してください。

分析の焦点: {analysis_focus}

要件:
- 英数字のみ（a-z, A-Z, 0-9, ハイフン、アンダースコアのみ）
- 20文字程度
- 分析の焦点を表す内容
- ユニークで識別しやすい

プロジェクト名のみを返してください。説明は不要です。
"""
    
    response_text = await _invoke_agent_async(agent, prompt)
    
    import re

    # 英字のみを抽出し、小文字化
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", response_text)]

    if not words:
        words = ["consulting", "analysis"]
    if len(words) == 1:
        words.append("analysis")

    # 各単語の長さを調整し、数字を含まないようにする
    normalized_words = [re.sub(r"[^a-z]", "", w)[:10] for w in words if re.sub(r"[^a-z]", "", w)]
    if not normalized_words:
        normalized_words = ["consulting", "analysis"]
    if len(normalized_words) == 1:
        normalized_words.append("analysis")

    # 先頭2語を使用し、「単語_単語」形式にする
    project_name = "_".join(normalized_words[:2])

    # 全体の長さを最大24文字に制限
    if len(project_name) > 24:
        first, second = project_name.split("_", 1)
        available = 24 - len(first) - 1
        second = second[:max(1, available)]
        project_name = f"{first}_{second}"

    project_name = project_name.strip("_")
    if "_" not in project_name:
        project_name = f"{project_name}_analysis"

    return project_name


def _read_csv_with_encoding(csv_path: Path) -> pd.DataFrame:
    """エンコーディングを自動検出してCSVファイルを読み込む。
    
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
                raise ValueError(f"CSVファイルの読み込みに失敗しました: {e}") from e
    
    raise ValueError("CSVファイルのエンコーディングを検出できませんでした")


async def generate_hypotheses(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """CSVデータから経営課題の仮説を生成し、統合データ構造を更新する。
    
    Args:
        state: 統合データ構造（consulting.jsonから読み込んだ状態）
        project_name: プロジェクト名
        
    Returns:
        更新された統合データ構造
    """
    try:
        csv_paths = state.get("csv_paths", [])
        if not csv_paths:
            # 後方互換性のため、csv_pathもチェック
            csv_path = state.get("csv_path", "")
            if csv_path:
                csv_paths = [csv_path]
            else:
                raise ValueError("CSVファイルが指定されていません。")
        
        # デバッグ: 読み込むCSVファイルのリストを確認
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"読み込むCSVファイル: {csv_paths}")
        
        # 複数のCSVファイルを読み込む
        dfs = []
        data_summaries = []
        
        for csv_path in csv_paths:
            csv_file = Path(csv_path)
            if not csv_file.is_absolute():
                csv_file = Path.cwd() / csv_file
            
            if not csv_file.exists():
                raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
            
            df = _read_csv_with_encoding(csv_file)
            dfs.append(df)
            
            # 各ファイルのデータ概要を生成
            file_summary = f"""
## ファイル: {csv_file.name}
- 総行数: {len(df)}
- カラム: {', '.join(df.columns.tolist())}
- サンプルデータ（最初の5行）:
{df.head(5).to_string()}

### データ型情報
"""
            for col in df.columns:
                dtype = str(df[col].dtype)
                file_summary += f"- `{col}`: {dtype}\n"
            
            data_summaries.append(file_summary)
        
        # データ概要を統合
        data_summary = "\n".join(data_summaries)
        
        # 複数ファイルの場合は統合情報も追加
        if len(dfs) > 1:
            total_rows = sum(len(df) for df in dfs)
            all_columns = set()
            for df in dfs:
                all_columns.update(df.columns.tolist())
            
            data_summary += f"""
## 統合データ概要
- ファイル数: {len(dfs)}
- 総行数: {total_rows}
- 全カラム数: {len(all_columns)}
- カラム一覧: {', '.join(sorted(all_columns))}
"""
        
        feedback_entries = state.get("steps", {}).get("hypothesis", {}).get("feedback", [])
        if feedback_entries:
            data_summary += "\n## レビューコメント\n"
            for entry in feedback_entries[-5:]:
                if isinstance(entry, dict):
                    timestamp = entry.get("timestamp", "")
                    reason = entry.get("reason", "")
                else:
                    timestamp = ""
                    reason = str(entry)
                prefix = f"- ({timestamp}) " if timestamp else "- "
                data_summary += f"{prefix}{reason}\n"

        if state.get("analysis_focus"):
            data_summary += f"\n## 分析の焦点\n{state['analysis_focus']}\n"
        
        # 前回の検証結果がある場合は追加
        if state.get("steps", {}).get("validate", {}).get("output_file"):
            project_dir = get_project_dir(project_name)
            validation_file = project_dir / state["steps"]["validate"]["output_file"]
            if validation_file.exists():
                validation_content = validation_file.read_text()
                data_summary += f"\n## 前回の検証結果（参考）\n{validation_content[:1000]}...\n"
        
        # エージェント作成
        model = _get_model()
        if model is None:
            raise ValueError(
                "LLMモデルが設定されていません。"
                "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
            )
        
        agent = _create_consulting_agent("hypothesis_generator", model)
        
        # プロンプト構築
        prompt = f"""
        {data_summary}

        上記のデータを分析し、経営課題の仮説を生成してください。
        Markdown形式で出力し、各仮説にはID、タイトル、説明、優先度を含めてください。
        """
        
        # エージェント呼び出し
        response_text = await _invoke_agent_async(agent, prompt)
        
        # Markdownを保存
        state["hypotheses_markdown"] = response_text
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"仮説生成に失敗しました: {e}")
        return state


async def process_data_for_validation(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """仮説検証用にデータを加工し、統合データ構造を更新する。
    
    Args:
        state: 統合データ構造
        project_name: プロジェクト名
        
    Returns:
        更新された統合データ構造
    """
    try:
        csv_paths = state.get("csv_paths", [])
        if not csv_paths:
            # 後方互換性のため、csv_pathもチェック
            csv_path = state.get("csv_path", "")
            if csv_path:
                csv_paths = [csv_path]
            else:
                raise ValueError("CSVファイルが指定されていません。")
        
        # 複数のCSVファイルを読み込む
        dfs = []
        csv_data_parts = []
        
        for csv_path in csv_paths:
            csv_file = Path(csv_path)
            if not csv_file.is_absolute():
                csv_file = Path.cwd() / csv_file
            
            if not csv_file.exists():
                raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")
            
            df = _read_csv_with_encoding(csv_file)
            dfs.append(df)
            csv_data_parts.append(f"## ファイル: {csv_file.name}\n{df.to_string()}")
        
        csv_data = "\n\n".join(csv_data_parts)
        
        # 仮説を取得
        project_dir = get_project_dir(project_name)
        hypotheses_file = project_dir / state["steps"]["hypothesis"]["output_file"]
        if not hypotheses_file.exists():
            raise ValueError("仮説ファイルが見つかりません。先に仮説を生成してください。")
        
        hypotheses_content = hypotheses_file.read_text()
        
        # エージェント作成
        model = _get_model()
        if model is None:
            raise ValueError(
                "LLMモデルが設定されていません。"
                "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
            )
        
        agent = _create_consulting_agent("data_processor", model)
        
        feedback_entries = state.get("steps", {}).get("process_data", {}).get("feedback", [])
        feedback_section = ""
        if feedback_entries:
            lines = []
            for entry in feedback_entries[-5:]:
                if isinstance(entry, dict):
                    timestamp = entry.get("timestamp", "")
                    reason = entry.get("reason", "")
                else:
                    timestamp = ""
                    reason = str(entry)
                prefix = f"- ({timestamp}) " if timestamp else "- "
                lines.append(f"{prefix}{reason}")
            feedback_section = "\n## レビューコメント\n" + "\n".join(lines) + "\n"

        # プロンプト構築
        prompt = f"""
        ## 仮説リスト
        {hypotheses_content}

        ## CSVデータ（複数ファイル）
        {csv_data}

        {feedback_section}

        上記の仮説を検証するために必要なデータを抽出・加工してください。
        複数のCSVファイルがある場合は、ファイル間の関連性も考慮してください。
        Markdown形式で出力し、抽出したデータの概要、集計結果、データの特徴を含めてください。
        """
        
        # エージェント呼び出し
        response_text = await _invoke_agent_async(agent, prompt)
        
        # Markdownを保存
        state["processed_data_markdown"] = response_text
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"データ加工に失敗しました: {e}")
        return state


async def validate_hypotheses(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """仮説を検証し、統合データ構造を更新する。
    
    Args:
        state: 統合データ構造
        project_name: プロジェクト名
        
    Returns:
        更新された統合データ構造
    """
    try:
        # 仮説と加工済みデータを取得
        project_dir = get_project_dir(project_name)
        hypotheses_file = project_dir / state["steps"]["hypothesis"]["output_file"]
        processed_data_file = project_dir / state["steps"]["process_data"]["output_file"]
        
        if not hypotheses_file.exists():
            raise ValueError("仮説ファイルが見つかりません。")
        if not processed_data_file.exists():
            raise ValueError("加工済みデータファイルが見つかりません。")
        
        hypotheses_content = hypotheses_file.read_text()
        processed_data_content = processed_data_file.read_text()
        
        # エージェント作成
        model = _get_model()
        if model is None:
            raise ValueError(
                "LLMモデルが設定されていません。"
                "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
            )
        
        agent = _create_consulting_agent("hypothesis_validator", model)
        
        feedback_entries = state.get("steps", {}).get("validate", {}).get("feedback", [])
        feedback_section = ""
        if feedback_entries:
            lines = []
            for entry in feedback_entries[-5:]:
                if isinstance(entry, dict):
                    timestamp = entry.get("timestamp", "")
                    reason = entry.get("reason", "")
                else:
                    timestamp = ""
                    reason = str(entry)
                prefix = f"- ({timestamp}) " if timestamp else "- "
                lines.append(f"{prefix}{reason}")
            feedback_section = "\n## レビューコメント\n" + "\n".join(lines) + "\n"

        # プロンプト構築
        prompt = f"""
        ## 仮説リスト
        {hypotheses_content}

        ## 加工済みデータ
        {processed_data_content}

        {feedback_section}

        上記のデータを用いて仮説を検証してください。
        Markdown形式で出力し、各仮説の検証結果、根拠となるデータ、主要指標を含めてください。
        """
        
        # エージェント呼び出し
        response_text = await _invoke_agent_async(agent, prompt)
        
        # Markdownを保存
        state["validation_results_markdown"] = response_text
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"仮説検証に失敗しました: {e}")
        return state


async def plan_strategies(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """検証済み課題に対する戦略を立案し、統合データ構造を更新する。
    
    Args:
        state: 統合データ構造
        project_name: プロジェクト名
        
    Returns:
        更新された統合データ構造
    """
    try:
        # 仮説と検証結果を取得
        project_dir = get_project_dir(project_name)
        hypotheses_file = project_dir / state["steps"]["hypothesis"]["output_file"]
        validation_file = project_dir / state["steps"]["validate"]["output_file"]
        
        if not hypotheses_file.exists():
            raise ValueError("仮説ファイルが見つかりません。")
        if not validation_file.exists():
            raise ValueError("検証結果ファイルが見つかりません。")
        
        hypotheses_content = hypotheses_file.read_text()
        validation_content = validation_file.read_text()
        
        # エージェント作成
        model = _get_model()
        if model is None:
            raise ValueError(
                "LLMモデルが設定されていません。"
                "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
            )
        
        agent = _create_consulting_agent("strategy_planner", model)
        
        feedback_entries = state.get("steps", {}).get("strategy", {}).get("feedback", [])
        feedback_section = ""
        if feedback_entries:
            lines = []
            for entry in feedback_entries[-5:]:
                if isinstance(entry, dict):
                    timestamp = entry.get("timestamp", "")
                    reason = entry.get("reason", "")
                else:
                    timestamp = ""
                    reason = str(entry)
                prefix = f"- ({timestamp}) " if timestamp else "- "
                lines.append(f"{prefix}{reason}")
            feedback_section = "\n## レビューコメント\n" + "\n".join(lines) + "\n"

        # プロンプト構築
        prompt = f"""
        ## 仮説リスト
        {hypotheses_content}

        ## 検証結果
        {validation_content}

        {feedback_section}

        検証済みの課題に対して具体的な対策・戦略を立案してください。
        Markdown形式で出力し、各戦略にID、タイトル、詳細、優先度、期待される影響度、実装難易度、タイムライン、主要アクションを含めてください。
        """
        
        # エージェント呼び出し
        response_text = await _invoke_agent_async(agent, prompt)
        
        # Markdownを保存
        state["strategies_markdown"] = response_text
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"戦略立案に失敗しました: {e}")
        return state


async def generate_consulting_report(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """最終レポートを生成し、統合データ構造を更新する。
    
    Args:
        state: 統合データ構造
        project_name: プロジェクト名
        
    Returns:
        更新された統合データ構造
    """
    try:
        # 全ての成果物を取得
        project_dir = get_project_dir(project_name)
        
        files_to_read = {
            "hypotheses": state["steps"]["hypothesis"]["output_file"],
            "processed_data": state["steps"]["process_data"]["output_file"],
            "validation_results": state["steps"]["validate"]["output_file"],
            "strategies": state["steps"]["strategy"]["output_file"],
        }
        
        content_parts = []
        for key, filename in files_to_read.items():
            if filename:
                file_path = project_dir / filename
                if file_path.exists():
                    content = file_path.read_text()
                    content_parts.append(f"## {key}\n{content}\n")
        
        if not content_parts:
            raise ValueError("必要なファイルが見つかりません。")
        
        all_content = "\n".join(content_parts)
        
        # エージェント作成
        model = _get_model()
        if model is None:
            raise ValueError(
                "LLMモデルが設定されていません。"
                "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
            )
        
        agent = _create_consulting_agent("report_generator", model)
        
        feedback_entries = state.get("steps", {}).get("report", {}).get("feedback", [])
        feedback_section = ""
        if feedback_entries:
            lines = []
            for entry in feedback_entries[-5:]:
                if isinstance(entry, dict):
                    timestamp = entry.get("timestamp", "")
                    reason = entry.get("reason", "")
                else:
                    timestamp = ""
                    reason = str(entry)
                prefix = f"- ({timestamp}) " if timestamp else "- "
                lines.append(f"{prefix}{reason}")
            feedback_section = "\n## レビューコメント\n" + "\n".join(lines) + "\n"

        # プロンプト構築
        prompt = f"""
        {all_content}

        {feedback_section}

        上記の情報を統合し、経営コンサルレポートを作成してください。
        Markdown形式で、エグゼクティブサマリー、分析概要、検証された課題、推奨対策、データ可視化の推奨、次のステップを含めてください。
        """
        
        # エージェント呼び出し
        response_text = await _invoke_agent_async(agent, prompt)
        
        # Markdownを保存
        state["report_markdown"] = response_text
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"レポート生成に失敗しました: {e}")
        return state

