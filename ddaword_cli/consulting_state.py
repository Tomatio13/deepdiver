"""経営コンサルエージェント用の状態管理モジュール."""

from __future__ import annotations

import json
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


def load_state(project_name: str) -> dict[str, Any]:
    """consulting.jsonを読み込む。
    
    Args:
        project_name: プロジェクト名
        
    Returns:
        状態辞書
    """
    project_dir = get_project_dir(project_name)
    state_file = project_dir / "consulting.json"
    
    if state_file.exists():
        state = json.loads(state_file.read_text())
        # 既存の状態にfeedbackフィールドがない場合は初期化
        steps = state.get("steps", {})
        for step in ["hypothesis", "process_data", "validate", "strategy", "report"]:
            if step in steps:
                steps[step].setdefault("feedback", [])
        return state
    
    # 初期状態を作成
    return {
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


def save_state(project_name: str, state: dict[str, Any]) -> None:
    """consulting.jsonを保存。
    
    Args:
        project_name: プロジェクト名
        state: 状態辞書
    """
    project_dir = get_project_dir(project_name)
    state_file = project_dir / "consulting.json"
    state["updated_at"] = datetime.now().isoformat()
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))


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

