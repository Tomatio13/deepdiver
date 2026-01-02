"""Paths for Deepdiver sub-agents storage."""

from __future__ import annotations

from pathlib import Path

from ..paths import find_project_root

SUBAGENTS_DIRNAME = "subagents"
SUBAGENTS_RUNS_DIRNAME = "runs"


def get_user_subagents_dir() -> Path:
    """Return the user-level sub-agents directory."""
    return Path.home() / ".deepdiver" / SUBAGENTS_DIRNAME


def ensure_user_subagents_dir() -> Path:
    """Create and return the user-level sub-agents directory."""
    d = get_user_subagents_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_project_subagents_dir(start: Path | None = None) -> Path | None:
    """Return the project-level sub-agents directory if inside a git repo."""
    project_root = find_project_root(start)
    if not project_root:
        return None
    return project_root / ".deepdiver" / SUBAGENTS_DIRNAME


def ensure_project_subagents_dir(start: Path | None = None) -> Path | None:
    """Create and return the project-level sub-agents directory if possible."""
    d = get_project_subagents_dir(start)
    if not d:
        return None
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_user_subagent_runs_dir() -> Path:
    """Return the directory where sub-agent run transcripts are stored."""
    return get_user_subagents_dir() / SUBAGENTS_RUNS_DIRNAME


def ensure_user_subagent_runs_dir() -> Path:
    """Create and return the directory where sub-agent run transcripts are stored."""
    d = get_user_subagent_runs_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d

