"""経営コンサルエージェントのサブエージェント実装."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any
import os,dotenv
import pandas as pd
from strands import Agent
from strands_tools import editor, environment, file_read, file_write, http_request, shell,calculator,current_time
from .csv_tool import filter_csv_data

from .config import create_model, console, COLORS
from .consulting_prompts import CONSULTING_PROMPTS, get_data_processing_prompt
from .consulting_state import (
    get_project_dir,
    load_state,
    initialize_process_data_tasks,
    get_pending_process_data_tasks,
    update_process_data_task_status,
)

# モデルキャッシュ
_cached_model: Any = None

DEFAULT_TOOLS = [file_read, file_write, editor, shell, http_request, environment,calculator,current_time]

def _get_model():
    """モデルインスタンスを取得（キャッシュを使用）。"""
    global _cached_model
    if _cached_model is None:
        _cached_model = create_model()
    return _cached_model


async def close_model():
    """キャッシュされたモデルのリソースを解放する。"""
    global _cached_model
    if _cached_model:
        # モデルがclient属性を持っていて、それがacloseメソッドを持っている場合
        if hasattr(_cached_model, "client") and hasattr(_cached_model.client, "aclose"):
            await _cached_model.client.aclose()
        # 同期closeの場合
        elif hasattr(_cached_model, "client") and hasattr(_cached_model.client, "close"):
            _cached_model.client.close()
            
        _cached_model = None


def _create_consulting_agent(agent_type: str, model: Any) -> Agent:
    """指定されたタイプのコンサルティングエージェントを作成。
    
    Args:
        agent_type: エージェントタイプ（"hypothesis_generator"など）
        model: LLMモデルインスタンス
        
    Returns:
        エージェントインスタンス
    """
    # .envファイルから環境変数を読み込む
    dotenv.load_dotenv()
    
    prompt = CONSULTING_PROMPTS.get(agent_type, "")
    return Agent(
        model=model,
        system_prompt=prompt,
        tools=list(DEFAULT_TOOLS),
        callback_handler=None,
    )


async def _invoke_agent_async(agent: Agent, prompt: str) -> str:
    """エージェントを非同期で呼び出し、ストリーミング表示と色付けを適用して結果を文字列で返す。"""
    import sys
    
    # ストリーミングをサポートしているか確認
    if hasattr(agent, "stream_async"):
        response_buffer: list[str] = []
        final_response = ""
        
        try:
            async for event in agent.stream_async(prompt):
                if not isinstance(event, dict):
                    continue
                
                # モデルデルタをレンダリング（リアルタイム表示）
                data = event.get("data")
                if isinstance(data, str) and data:
                    response_buffer.append(data)
                    console.print(data, style=COLORS["agent"], end="")
                    sys.stdout.flush()
                    continue
                
                
                # ツールイベントの表示
                if "current_tool_use" in event and event["current_tool_use"].get("name"):
                    tool_name = event["current_tool_use"]["name"]
                    console.print()
                    console.print(f"🔧 Using tool: {tool_name}")
                    sys.stdout.flush()
                
                # 後方互換性のため、delta もチェック
                delta = event.get("delta")
                if isinstance(delta, str) and delta:
                    response_buffer.append(delta)
                    console.print(delta, style=COLORS["agent"], end="")
                    sys.stdout.flush()
                    continue
                
                # 最終結果の取得
                if "result" in event:
                    result = event.get("result")
                    if result is not None:
                        if hasattr(result, "output_text"):
                            final_response = str(result.output_text)
                        elif hasattr(result, "content"):
                            final_response = str(result.content)
                        elif isinstance(result, dict):
                            final_response = str(result.get("output_text", result.get("content", result)))
                        else:
                            final_response = str(result)
            
            # 改行を追加
            console.print()
            
            # 最終結果があればそれを使用、なければバッファから構築
            combined = final_response or "".join(response_buffer)
            return combined.strip()
            
        except Exception as exc:
            # ストリーミングに失敗した場合は通常の呼び出しにフォールバック
            console.print(f"\n[{COLORS['warning']}]Streaming failed, using blocking call: {exc}[/]")
    
    # ストリーミングをサポートしていない場合は通常の呼び出し
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


def _read_csv_with_encoding(csv_path: Path, nrows: int | None = None) -> pd.DataFrame:
    """エンコーディングを自動検出してCSVファイルを読み込む。
    
    Args:
        csv_path: CSVファイルのパス
        nrows: 読み込む行数（Noneの場合は全行）
        
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
            df = pd.read_csv(csv_path, encoding=encoding, nrows=nrows)
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
        
        project_dir = get_project_dir(project_name)
        
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
            
            # コンテキスト生成用なので、先頭5行だけ読み込む（メモリ節約・高速化）
            df = _read_csv_with_encoding(csv_file, nrows=5)
            
            # 総行数を取得するために、メタデータのみ別途取得（必要であれば）
            # ここでは簡易的にファイルサイズ等から推測するか、
            # 正確な行数が必要なら別途カウントするが、
            # コンテキスト用としては「データの中身」が重要なので5行で十分。
            # ただし、総行数の表示があった方が親切なので、行数カウントだけ行う。
            try:
                with open(csv_file, 'rb') as f:
                    total_lines = sum(1 for _ in f) - 1 # ヘッダー分減らす（概算）
            except Exception:
                total_lines = "不明"

            dfs.append(df)
            
            # 各ファイルのデータ概要を生成
            file_summary = f"""
## ファイル: {csv_file.name}
- 推定総行数: {total_lines}
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
        feedback_section = ""
        if feedback_entries:
            data_summary += "\n## レビューコメント\n"
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
                data_summary += f"{prefix}{reason}\n"
            feedback_section = "\n## レビューコメント\n" + "\n".join(lines) + "\n"

        if state.get("analysis_focus"):
            data_summary += f"\n## 分析の焦点\n{state['analysis_focus']}\n"
        
        # 前回の検証結果がある場合は追加
        # 検証結果を取得
        project_dir = get_project_dir(project_name)
        validation_file_name = state["steps"]["validate"].get("output_file") or "validation_results.md"
        validation_file = project_dir / validation_file_name
        
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
        
        # csv_infoを構築（process_data_for_validationと同様のロジック）
        csv_info = []
        for csv_path in csv_paths:
            csv_file = Path(csv_path)
            if not csv_file.is_absolute():
                csv_file = Path.cwd() / csv_file
            
            if csv_file.exists():
                try:
                    # カラム名のみを取得（データは読み込まない）
                    df_sample = pd.read_csv(csv_file, encoding="utf-8", nrows=0)
                    csv_info.append({
                        "path": str(csv_file),
                        "name": csv_file.name,
                        "columns": df_sample.columns.tolist()
                    })
                except Exception:
                    # UTF-8で失敗した場合は他のエンコーディングを試す
                    try:
                        df_sample = pd.read_csv(csv_file, encoding="shift-jis", nrows=0)
                        csv_info.append({
                            "path": str(csv_file),
                            "name": csv_file.name,
                            "columns": df_sample.columns.tolist()
                        })
                    except Exception as e:
                        csv_info.append({
                            "path": str(csv_file),
                            "name": csv_file.name,
                            "columns": [],
                            "error": str(e)
                        })
        
        # CSVファイル情報を最小限の形式で構築
        csv_summary_lines = []
        csv_path_list = []
        for info in csv_info:
            csv_path_list.append(info['path'])
            if "error" in info:
                csv_summary_lines.append(f"- **{info['name']}** (`{info['path']}`): 読み込みエラー ({info['error']})")
            else:
                columns_str = ", ".join(info['columns'][:15])
                if len(info['columns']) > 15:
                    columns_str += f", ... (計{len(info['columns'])}列)"
                csv_summary_lines.append(f"- **{info['name']}** (`{info['path']}`): {len(info['columns'])}列 - {columns_str}")
        csv_summary_text = "\n".join(csv_summary_lines)
        csv_paths_text = "\n".join([f"- `{path}`" for path in csv_path_list])

        # 関連ドキュメントの取得
        docs_text = ""
        if state.get("docs_paths"):
            docs_content = []
            for doc_path_str in state["docs_paths"]:
                doc_path = Path(doc_path_str)
                if doc_path.exists():
                    docs_content.append(f"### {doc_path.name}\n```\n{doc_path.read_text()[:1000]}...\n```")
            if docs_content:
                docs_text = "\n## 関連ドキュメント\n" + "\n".join(docs_content) + "\n"

        # 再試行ループ（最大3回）
        max_retries = 3
        current_feedback = feedback_section
        final_response_text = ""
        
        for attempt in range(max_retries):
            is_last_attempt = (attempt == max_retries - 1)
            
            # プロンプト構築
            prompt = f"""
## プロジェクト: {project_name}

## 利用可能なデータソース
### CSVファイルパス
{csv_paths_text}

### カラム情報
{csv_summary_text}

## 関連ドキュメント
{docs_text}

{current_feedback}

システムプロンプトの指示に従い、上記のデータから経営課題の仮説を立案してください。
"""
            
            # エージェント呼び出し
            console.print(f"[{COLORS['info']}]Generating hypotheses (Attempt {attempt + 1}/{max_retries})...[/]")
            response_text = await _invoke_agent_async(agent, prompt)
            
            # レビュー（自己検証）
            reviewer = _create_consulting_agent("hypothesis_reviewer", model)
            review_prompt = f"""
## 仮説リスト
{response_text}

上記の仮説リストをレビューしてください。
**重要: 出力は必ず "OK" または "NG: <理由>" の形式のみにしてください。余計な挨拶や説明は不要です。**
"""
            review_result = await _invoke_agent_async(reviewer, review_prompt)
            
            if review_result.strip().startswith("OK"):
                console.print(f"[{COLORS['success']}]  Review passed![/]")
                final_response_text = response_text
                break
            else:
                error_reason = review_result.replace("NG:", "").strip()
                console.print(f"[{COLORS['warning']}]  Review failed: {error_reason}[/]")
                
                if not is_last_attempt:
                    current_feedback += f"\n\n## 品質レビューからのフィードバック（再試行 {attempt+1}回目）\n{error_reason}\n修正して再生成してください。\n"
                else:
                    console.print(f"[{COLORS['error']}]  Max retries reached. Saving last result.[/]")
                    final_response_text = response_text

        # 結果を保存
        # 結果を保存
        state["hypotheses_markdown"] = final_response_text
        output_file = state["steps"]["hypothesis"].get("output_file") or "hypotheses.md"
        output_path = project_dir / output_file
        output_path.write_text(final_response_text)
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"仮説生成に失敗しました: {e}")
        return state


def extract_hypothesis_ids(hypotheses_content: str) -> list[str]:
    """仮説ファイルの内容から仮説ID（H1, H2, H3...）を抽出する。
    
    Args:
        hypotheses_content: 仮説ファイルの内容
        
    Returns:
        仮説IDのリスト（例: ["H1", "H2", "H3"]）
    """
    # H1, H2, H3... のパターンを検索
    pattern = r'\bH\d+\b'
    matches = re.findall(pattern, hypotheses_content, re.IGNORECASE)
    
    # 重複を除去し、数値順にソート
    unique_ids = sorted(set(matches), key=lambda x: int(re.search(r'\d+', x).group()))
    
    return unique_ids


def extract_hypothesis_section(hypotheses_content: str, hypothesis_id: str) -> str:
    """仮説ファイルから特定の仮説IDのセクションを抽出する。
    
    Args:
        hypotheses_content: 仮説ファイルの内容
        hypothesis_id: 仮説ID（例: "H1"）
        
    Returns:
        仮説セクションの内容
    """
    # 仮説IDで始まるセクションを検索
    pattern = rf'(?i)(##?\s*{re.escape(hypothesis_id)}[^\n]*\n.*?)(?=\n##?\s*H\d+|$)'
    match = re.search(pattern, hypotheses_content, re.DOTALL)
    
    if match:
        return match.group(1).strip()
    
    # 見つからない場合は、仮説IDを含む行から次のHで始まる行まで
    lines = hypotheses_content.split('\n')
    start_idx = None
    for i, line in enumerate(lines):
        if re.search(rf'\b{re.escape(hypothesis_id)}\b', line, re.IGNORECASE):
            start_idx = i
            break
    
    if start_idx is not None:
        # 次のHで始まる行を探す
        end_idx = len(lines)
        for i in range(start_idx + 1, len(lines)):
            if re.search(r'^##?\s*H\d+', lines[i], re.IGNORECASE):
                end_idx = i
                break
        return '\n'.join(lines[start_idx:end_idx]).strip()
    
    return ""


async def process_data_for_validation(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """仮説検証用にデータを加工し、統合データ構造を更新する。
    
    仮説ごとにタスクを作成し、未完了のタスクから順に処理します。
    各タスクの結果は個別のファイルに保存されます。
    
    Args:
        state: 統合データ構造
        project_name: プロジェクト名
        
    Returns:
        更新された統合データ構造
    """
    try:
        csv_paths = state.get("csv_paths", [])
        
        # 仮説を取得
        project_dir = get_project_dir(project_name)
        hypotheses_file_name = state["steps"]["hypothesis"].get("output_file") or "hypotheses.md"
        hypotheses_file = project_dir / hypotheses_file_name
        if not hypotheses_file.exists():
            raise ValueError("仮説ファイルが見つかりません。先に仮説を生成してください。")
        
        hypotheses_content = hypotheses_file.read_text()
        
        # 仮説IDを抽出
        hypothesis_ids = extract_hypothesis_ids(hypotheses_content)
        
        if not hypothesis_ids:
            raise ValueError("仮説IDが見つかりません。仮説ファイルを確認してください。")
        
        # タスクを初期化
        initialize_process_data_tasks(project_name, hypothesis_ids)
        
        # 未完了のタスクを取得
        pending_tasks = get_pending_process_data_tasks(project_name)
        
        if not pending_tasks:
            # すべてのタスクが完了している場合
            state = load_state(project_name)
            # 統合ファイルを作成（既存の個別ファイルを結合）
            all_outputs = []
            tasks = state["steps"]["process_data"].get("tasks", {})
            for hypothesis_id in sorted(hypothesis_ids, key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0):
                task = tasks.get(hypothesis_id, {})
                output_file = task.get("output_file")
                if output_file:
                    output_path = project_dir / output_file
                    if output_path.exists():
                        all_outputs.append(f"# {hypothesis_id}\n\n{output_path.read_text()}\n\n")
            
            if all_outputs:
                state["processed_data_markdown"] = "\n".join(all_outputs)
            
            return state
        
        # モデルを取得（各エージェントで共有）
        model = _get_model()
        if model is None:
            raise ValueError(
                "LLMモデルが設定されていません。"
                "STRANDS_MODEL_PROVIDER環境変数を設定してください。"
            )
        
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

        # CSVファイルの最小限の情報のみを取得（コンテキスト節約）
        csv_info = []
        for csv_path in csv_paths:
            csv_file = Path(csv_path)
            if not csv_file.is_absolute():
                csv_file = Path.cwd() / csv_file
            
            if csv_file.exists():
                try:
                    # カラム名のみを取得（データは読み込まない）
                    df_sample = pd.read_csv(csv_file, encoding="utf-8", nrows=0)
                    csv_info.append({
                        "path": str(csv_file),
                        "name": csv_file.name,
                        "columns": df_sample.columns.tolist()
                    })
                except Exception:
                    # UTF-8で失敗した場合は他のエンコーディングを試す
                    try:
                        df_sample = pd.read_csv(csv_file, encoding="shift-jis", nrows=0)
                        csv_info.append({
                            "path": str(csv_file),
                            "name": csv_file.name,
                            "columns": df_sample.columns.tolist()
                        })
                    except Exception as e:
                        csv_info.append({
                            "path": str(csv_file),
                            "name": csv_file.name,
                            "columns": [],
                            "error": str(e)
                        })
        
        # 各タスクを順に処理（仮説ごとに独立したエージェントを作成）
        processed_outputs = []
        
        if pending_tasks:
            console.print(f"\n[bold {COLORS['info']}]Starting data processing for {len(pending_tasks)} hypotheses...[/]")
            
            for hypothesis_id in pending_tasks:
                console.print(f"[{COLORS['info']}]Processing {hypothesis_id}...[/]")
                
                try:
                    # タスクステータスをin_progressに更新
                    update_process_data_task_status(project_name, hypothesis_id, "in_progress")
                    
                    # 該当仮説のセクションを抽出
                    hypothesis_section = extract_hypothesis_section(hypotheses_content, hypothesis_id)
                    
                    if not hypothesis_section:
                        # 仮説セクションが見つからない場合は、仮説IDを含む行を探す
                        lines = hypotheses_content.split('\n')
                        for i, line in enumerate(lines):
                            if re.search(rf'\b{re.escape(hypothesis_id)}\b', line, re.IGNORECASE):
                                # 次の数行を含める
                                hypothesis_section = '\n'.join(lines[max(0, i-2):min(len(lines), i+20)])
                                break
                    
                    # 仮説ごとに独立したサブエージェントを作成
                    agent = _create_consulting_agent("data_processor", model)
                    
                    # CSVファイル情報を最小限の形式で構築
                    csv_summary_lines = []
                    csv_path_list = []
                    for info in csv_info:
                        csv_path_list.append(info['path'])
                        if "error" in info:
                            csv_summary_lines.append(f"- **{info['name']}** (`{info['path']}`): 読み込みエラー ({info['error']})")
                        else:
                            columns_str = ", ".join(info['columns'][:15])
                            if len(info['columns']) > 15:
                                columns_str += f", ... (計{len(info['columns'])}列)"
                            csv_summary_lines.append(f"- **{info['name']}** (`{info['path']}`): {len(info['columns'])}列 - {columns_str}")
                    csv_summary_text = "\n".join(csv_summary_lines)
                    csv_paths_text = "\n".join([f"- `{path}`" for path in csv_path_list])
                    
                    # 再試行ループ（最大3回）
                    max_retries = 3
                    current_feedback = feedback_section
                    final_response_text = ""
                    
                    for attempt in range(max_retries):
                        is_last_attempt = (attempt == max_retries - 1)
                        
                        # プロンプト構築
                        prompt = get_data_processing_prompt(
                            hypothesis_id=hypothesis_id,
                            hypothesis_section=hypothesis_section,
                            csv_paths_text=csv_paths_text,
                            csv_summary_text=csv_summary_text,
                            feedback_section=current_feedback,
                            project_dir=str(project_dir),
                        )
                        
                        # サブエージェント呼び出し
                        console.print(f"[{COLORS['info']}]  Attempt {attempt + 1}/{max_retries}...[/]")
                        response_text = await _invoke_agent_async(agent, prompt)
                        
                        # レビュー（自己検証）
                        reviewer = _create_consulting_agent("data_processing_reviewer", model)
                        review_prompt = f"""
## レポート内容
{response_text}

上記のレポートをレビューしてください。
**重要: 出力は必ず "OK" または "NG: <理由>" の形式のみにしてください。余計な挨拶や説明は不要です。**
"""
                        review_result = await _invoke_agent_async(reviewer, review_prompt)
                        
                        if review_result.strip().startswith("OK"):
                            console.print(f"[{COLORS['success']}]  Review passed![/]")
                            final_response_text = response_text
                            break
                        else:
                            error_reason = review_result.replace("NG:", "").strip()
                            console.print(f"[{COLORS['warning']}]  Review failed: {error_reason}[/]")
                            
                            if not is_last_attempt:
                                current_feedback += f"\n\n## 品質レビューからのフィードバック（再試行 {attempt+1}回目）\n{error_reason}\n修正して再生成してください。\n"
                            else:
                                console.print(f"[{COLORS['error']}]  Max retries reached. Saving last result.[/]")
                                final_response_text = response_text
                    
                    # 個別ファイルに保存
                    output_file = f"processed_data_{hypothesis_id}.md"
                    output_path = project_dir / output_file
                    output_path.write_text(final_response_text)
                    
                    # タスクステータスを完了に更新
                    update_process_data_task_status(
                        project_name,
                        hypothesis_id,
                        "completed",
                        output_file=output_file,
                    )
                    
                    processed_outputs.append(f"# {hypothesis_id}\n\n{final_response_text}\n\n")
                    
                except Exception as e:
                    # タスクステータスを失敗に更新
                    error_msg = str(e)
                    update_process_data_task_status(
                        project_name,
                        hypothesis_id,
                        "failed",
                        error=error_msg,
                    )
                    state["errors"] = state.get("errors", [])
                    state["errors"].append(f"仮説 {hypothesis_id} のデータ加工に失敗しました: {e}")
                    # エラーが発生しても次のタスクを続行
        
        # 統合ファイルを作成
        if processed_outputs:
            state["processed_data_markdown"] = "\n".join(processed_outputs)
        
        # 既存の完了済みタスクの内容も統合ファイルに追加
        state = load_state(project_name)
        tasks = state["steps"]["process_data"].get("tasks", {})
        all_outputs = []
        for hypothesis_id in sorted(hypothesis_ids, key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0):
            task = tasks.get(hypothesis_id, {})
            output_file = task.get("output_file")
            if output_file:
                output_path = project_dir / output_file
                if output_path.exists():
                    all_outputs.append(f"# {hypothesis_id}\n\n{output_path.read_text()}\n\n")
        
        if all_outputs:
            state["processed_data_markdown"] = "\n".join(all_outputs)
        
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
        hypotheses_file_name = state["steps"]["hypothesis"].get("output_file") or "hypotheses.md"
        processed_data_file_name = state["steps"]["process_data"].get("output_file") or "processed_data.md"
        
        hypotheses_file = project_dir / hypotheses_file_name
        processed_data_file = project_dir / processed_data_file_name
        
        if not hypotheses_file.exists():
            raise ValueError("仮説ファイルが見つかりません。")
        if not processed_data_file.exists():
            raise ValueError("加工済みデータファイルが見つかりません。")
        
        hypotheses_content = hypotheses_file.read_text()
        processed_data_text = processed_data_file.read_text() # Renamed from processed_data_content
        
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

        # 再試行ループ（最大3回）
        max_retries = 3
        current_feedback = feedback_section
        final_response_text = ""
        
        for attempt in range(max_retries):
            is_last_attempt = (attempt == max_retries - 1)
            
            # プロンプト構築
            prompt = f"""
## 仮説リスト
{hypotheses_content}

## 加工済みデータ
{processed_data_text}

{current_feedback}

システムプロンプトの指示に従い、加工済みデータを用いて仮説を検証してください。
"""
            
            # エージェント呼び出し
            console.print(f"[{COLORS['info']}]Validating hypotheses (Attempt {attempt + 1}/{max_retries})...[/]")
            response_text = await _invoke_agent_async(agent, prompt)
            
            # レビュー（自己検証）
            reviewer = _create_consulting_agent("validation_reviewer", model)
            review_prompt = f"""
## 検証結果レポート
{response_text}

上記の検証結果レポートをレビューしてください。
**重要: 出力は必ず "OK" または "NG: <理由>" の形式のみにしてください。余計な挨拶や説明は不要です。**
"""
            review_result = await _invoke_agent_async(reviewer, review_prompt)
            
            if review_result.strip().startswith("OK"):
                console.print(f"[{COLORS['success']}]  Review passed![/]")
                final_response_text = response_text
                break
            else:
                error_reason = review_result.replace("NG:", "").strip()
                console.print(f"[{COLORS['warning']}]  Review failed: {error_reason}[/]")
                
                if not is_last_attempt:
                    current_feedback += f"\n\n## 品質レビューからのフィードバック（再試行 {attempt+1}回目）\n{error_reason}\n修正して再生成してください。\n"
                else:
                    console.print(f"[{COLORS['error']}]  Max retries reached. Saving last result.[/]")
                    final_response_text = response_text
        
        # 結果を保存
        state["validation_results_markdown"] = final_response_text
        output_file = state["steps"]["validate"].get("output_file") or "validation_results.md"
        output_path = project_dir / output_file
        output_path.write_text(final_response_text)
        
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
        
        hypotheses_content = hypotheses_file.read_text() # This is not used in the new prompt, but kept for context if needed later.
        validation_results = validation_file.read_text() # Renamed from validation_content
        
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

        # 再試行ループ（最大3回）
        max_retries = 3
        current_feedback = feedback_section
        final_response_text = ""
        
        for attempt in range(max_retries):
            is_last_attempt = (attempt == max_retries - 1)
            
            # プロンプト構築
            prompt = f"""
## 検証結果
{validation_results}

{current_feedback}

システムプロンプトの指示に従い、検証済みの課題に対する戦略を立案してください。
"""
            
            # エージェント呼び出し
            console.print(f"[{COLORS['info']}]Planning strategies (Attempt {attempt + 1}/{max_retries})...[/]")
            response_text = await _invoke_agent_async(agent, prompt)
            
            # レビュー（自己検証）
            reviewer = _create_consulting_agent("strategy_reviewer", model)
            review_prompt = f"""
## 戦略立案レポート
{response_text}

上記の戦略立案レポートをレビューしてください。
**重要: 出力は必ず "OK" または "NG: <理由>" の形式のみにしてください。余計な挨拶や説明は不要です。**
"""
            review_result = await _invoke_agent_async(reviewer, review_prompt)
            
            if review_result.strip().startswith("OK"):
                console.print(f"[{COLORS['success']}]  Review passed![/]")
                final_response_text = response_text
                break
            else:
                error_reason = review_result.replace("NG:", "").strip()
                console.print(f"[{COLORS['warning']}]  Review failed: {error_reason}[/]")
                
                if not is_last_attempt:
                    current_feedback += f"\n\n## 品質レビューからのフィードバック（再試行 {attempt+1}回目）\n{error_reason}\n修正して再生成してください。\n"
                else:
                    console.print(f"[{COLORS['error']}]  Max retries reached. Saving last result.[/]")
                    final_response_text = response_text
        
        # 結果を保存
        # 結果を保存
        state["strategies_markdown"] = final_response_text
        output_file = state["steps"].get("plan", {}).get("output_file") or "strategies.md"
        output_path = project_dir / output_file
        output_path.write_text(final_response_text)
        
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

        # 再試行ループ（最大3回）
        max_retries = 3
        current_feedback = feedback_section
        final_response_text = ""

        reviewer = _create_consulting_agent("report_reviewer", model)

        for attempt in range(max_retries):
            is_last_attempt = (attempt == max_retries - 1)

            # プロンプト構築
            prompt = f"""
{all_content}

{current_feedback}

上記の情報を統合し、経営コンサルレポートを作成してください。
Markdown形式で、エグゼクティブサマリー、分析概要、検証された課題、推奨対策、データ可視化の推奨、次のステップを含めてください。
"""

            console.print(f"[{COLORS['info']}]Generating report (Attempt {attempt + 1}/{max_retries})...[/]")
            response_text = await _invoke_agent_async(agent, prompt)

            review_prompt = f"""
## 経営コンサルレポート
{response_text}

上記のレポートをレビューしてください。
**重要: 出力は必ず "OK" または "NG: <理由>" の形式のみにしてください。余計な挨拶や説明は不要です。**
"""
            review_result = await _invoke_agent_async(reviewer, review_prompt)

            if review_result.strip().startswith("OK"):
                console.print(f"[{COLORS['success']}]  Review passed![/]")
                final_response_text = response_text
                break
            else:
                error_reason = review_result.replace("NG:", "").strip()
                console.print(f"[{COLORS['warning']}]  Review failed: {error_reason}[/]")

                if not is_last_attempt:
                    current_feedback += f"\n\n## 品質レビューからのフィードバック（再試行 {attempt+1}回目）\n{error_reason}\n修正して再生成してください。\n"
                else:
                    console.print(f"[{COLORS['error']}]  Max retries reached. Saving last result.[/]")
                    final_response_text = response_text

        # Markdownを保存
        state["report_markdown"] = final_response_text
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"レポート生成に失敗しました: {e}")
        return state
