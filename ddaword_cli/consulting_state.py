"""経営コンサルエージェント用の状態管理モジュール."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

CONSULTING_DIR = Path(".consulting")


def get_project_dir(project_name: str) -> Path:
    """プロジェクトディレクトリを取得または作成。
    
    Args:
        project_name: プロジェクト名
        
    Returns:
        プロジェクトディレクトリのPath
    """
    project_dir = CONSULTING_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


# 状態キャッシュ: {project_name: {"data": state_dict, "mtime": float}}
_state_cache: dict[str, dict[str, Any]] = {}


def load_state(project_name: str) -> dict[str, Any]:
    """consulting.jsonを読み込む（キャッシュ対応）。
    
    Args:
        project_name: プロジェクト名
        
    Returns:
        状態辞書
    """
    project_dir = get_project_dir(project_name)
    state_file = project_dir / "consulting.json"
    
    # キャッシュチェック
    current_mtime = 0.0
    if state_file.exists():
        current_mtime = state_file.stat().st_mtime
        
    if project_name in _state_cache:
        cache_entry = _state_cache[project_name]
        # キャッシュが有効（ファイルの更新日時がキャッシュの記録と同じか古い）ならキャッシュを返す
        if current_mtime <= cache_entry["mtime"]:
            return cache_entry["data"]
    
    if state_file.exists():
        state = json.loads(state_file.read_text())
        # 既存の状態にfeedbackフィールドがない場合は初期化
        steps = state.get("steps", {})
        for step in ["hypothesis", "process_data", "validate", "strategy", "report"]:
            if step in steps:
                steps[step].setdefault("feedback", [])
        
        # キャッシュ更新
        _state_cache[project_name] = {
            "data": state,
            "mtime": current_mtime
        }
        return state
    
    # 初期状態を作成
    initial_state = {
        "version": "1.0",
        "project_name": project_name,
        "csv_paths": [],
        "analysis_focus": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "status": "pending",
        "current_step": None,
        "steps": {
            "hypothesis": {
                "status": "pending",
                "approved": None,
                "completed_at": None,
                "output_file": None,
                "feedback": [],
            },
            "process_data": {
                "status": "pending",
                "approved": None,
                "completed_at": None,
                "output_file": None,
                "feedback": [],
            },
            "validate": {
                "status": "pending",
                "approved": None,
                "completed_at": None,
                "output_file": None,
                "feedback": [],
            },
            "strategy": {
                "status": "pending",
                "approved": None,
                "completed_at": None,
                "output_file": None,
                "feedback": [],
            },
            "report": {
                "status": "pending",
                "approved": None,
                "completed_at": None,
                "output_file": None,
                "feedback": [],
            },
        },
        "retry_count": 0,
        "max_retry": 3,
    }
    
    # 新規作成時はキャッシュしない（ファイルがないためmtimeが0）
    return initial_state


def save_state(project_name: str, state: dict[str, Any]) -> None:
    """consulting.jsonを保存（キャッシュ更新）。
    
    Args:
        project_name: プロジェクト名
        state: 状態辞書
    """
    project_dir = get_project_dir(project_name)
    state_file = project_dir / "consulting.json"
    state["updated_at"] = datetime.now().isoformat()
    
    # ファイル書き込み
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    
    # キャッシュ更新（mtimeを最新に）
    _state_cache[project_name] = {
        "data": state,
        "mtime": state_file.stat().st_mtime
    }


def update_step_status(
    project_name: str,
    step: str,
    status: str,
    output_file: str | None = None,
) -> None:
    """ステップの状態を更新。
    
    Args:
        project_name: プロジェクト名
        step: ステップ名（"hypothesis", "process_data", "validate", "strategy", "report"）
        status: 状態（"pending", "in_progress", "completed", "approved", "rejected"）
        output_file: 出力ファイル名（オプション）
    """
    state = load_state(project_name)
    state["steps"][step]["status"] = status
    state["current_step"] = step
    state["status"] = f"{step}_{status}"
    
    if output_file:
        state["steps"][step]["output_file"] = output_file
    
    if status == "completed":
        state["steps"][step]["completed_at"] = datetime.now().isoformat()
    
    save_state(project_name, state)


def approve_step(project_name: str, step: str) -> None:
    """ステップを承認。
    
    Args:
        project_name: プロジェクト名
        step: ステップ名
    """
    state = load_state(project_name)
    state["steps"][step]["approved"] = True
    state["steps"][step]["status"] = "approved"
    state["status"] = f"{step}_approved"
    save_state(project_name, state)


def add_feedback(project_name: str, step: str, reason: str) -> None:
    """指定したステップにフィードバックを追加。
    
    Args:
        project_name: プロジェクト名
        step: ステップ名
        reason: フィードバック内容
    """
    state = load_state(project_name)
    feedback_entry = {
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }
    state["steps"][step].setdefault("feedback", [])
    state["steps"][step]["feedback"].append(feedback_entry)
    save_state(project_name, state)


def reject_step(project_name: str, step: str, reason: str | None = None) -> None:
    """ステップを否決。
    
    Args:
        project_name: プロジェクト名
        step: ステップ名
    """
    state = load_state(project_name)
    if reason:
        feedback_entry = {
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        state["steps"][step].setdefault("feedback", [])
        state["steps"][step]["feedback"].append(feedback_entry)
    state["steps"][step]["approved"] = False
    state["steps"][step]["status"] = "rejected"
    state["status"] = f"{step}_rejected"
    save_state(project_name, state)


def get_current_project() -> str | None:
    """現在のプロジェクト名を取得（最新のプロジェクトを返す）。
    
    Returns:
        プロジェクト名、またはNone（プロジェクトが存在しない場合）
    """
    if not CONSULTING_DIR.exists():
        return None
    
    # 最新のプロジェクトを取得
    projects = [d for d in CONSULTING_DIR.iterdir() if d.is_dir()]
    if not projects:
        return None
    
    # 最新の更新日時のプロジェクトを返す
    def get_mtime(project_path: Path) -> float:
        state_file = project_path / "consulting.json"
        if state_file.exists():
            return state_file.stat().st_mtime
        return 0.0
    
    latest_project = max(projects, key=get_mtime)
    return latest_project.name


def initialize_process_data_tasks(project_name: str, hypothesis_ids: list[str]) -> None:
    """process_dataステップのタスクを初期化する。
    
    Args:
        project_name: プロジェクト名
        hypothesis_ids: 仮説IDのリスト（例: ["H1", "H2", "H3"]）
    """
    state = load_state(project_name)
    
    # process_dataステップにtasksフィールドがない場合は初期化
    if "tasks" not in state["steps"]["process_data"]:
        state["steps"]["process_data"]["tasks"] = {}
    
    tasks = state["steps"]["process_data"]["tasks"]
    
    # 既存のタスクを保持しつつ、新しい仮説IDのタスクを追加
    for hypothesis_id in hypothesis_ids:
        if hypothesis_id not in tasks:
            tasks[hypothesis_id] = {
                "status": "pending",
                "output_file": None,
                "started_at": None,
                "completed_at": None,
                "error": None,
            }
    
    # 存在しない仮説IDのタスクを削除（仮説が削除された場合）
    existing_ids = set(tasks.keys())
    new_ids = set(hypothesis_ids)
    for removed_id in existing_ids - new_ids:
        del tasks[removed_id]
    
    save_state(project_name, state)


def get_pending_process_data_tasks(project_name: str) -> list[str]:
    """未完了のprocess_dataタスクのIDリストを取得する。
    
    Args:
        project_name: プロジェクト名
        
    Returns:
        未完了タスクの仮説IDリスト
    """
    state = load_state(project_name)
    tasks = state["steps"]["process_data"].get("tasks", {})
    
    pending_tasks = []
    for hypothesis_id, task_info in tasks.items():
        status = task_info.get("status", "pending")
        if status in ["pending", "in_progress", "failed"]:
            pending_tasks.append(hypothesis_id)
    
    # 数値順にソート
    pending_tasks.sort(key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)
    
    return pending_tasks


def update_process_data_task_status(
    project_name: str,
    hypothesis_id: str,
    status: str,
    output_file: str | None = None,
    error: str | None = None,
) -> None:
    """process_dataタスクのステータスを更新する。
    
    Args:
        project_name: プロジェクト名
        hypothesis_id: 仮説ID（例: "H1"）
        status: ステータス（"pending", "in_progress", "completed", "failed"）
        output_file: 出力ファイル名（オプション）
        error: エラーメッセージ（オプション、failedの場合）
    """
    state = load_state(project_name)
    
    if "tasks" not in state["steps"]["process_data"]:
        state["steps"]["process_data"]["tasks"] = {}
    
    if hypothesis_id not in state["steps"]["process_data"]["tasks"]:
        state["steps"]["process_data"]["tasks"][hypothesis_id] = {
            "status": "pending",
            "output_file": None,
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
    
    task = state["steps"]["process_data"]["tasks"][hypothesis_id]
    task["status"] = status
    
    if status == "in_progress" and not task.get("started_at"):
        task["started_at"] = datetime.now().isoformat()
    
    if status == "completed":
        task["completed_at"] = datetime.now().isoformat()
        if output_file:
            task["output_file"] = output_file
    
    if status == "failed":
        task["error"] = error
    
    # すべてのタスクが完了したら、process_dataステップも完了にする
    all_tasks = state["steps"]["process_data"]["tasks"]
    all_completed = all(
        task_info.get("status") == "completed"
        for task_info in all_tasks.values()
    )
    
    if all_completed and all_tasks:
        state["steps"]["process_data"]["status"] = "completed"
        state["steps"]["process_data"]["completed_at"] = datetime.now().isoformat()
    
    save_state(project_name, state)

