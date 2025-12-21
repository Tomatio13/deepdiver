"""Paths for Deepdiver skills storage."""

from __future__ import annotations

from pathlib import Path

from deepdiver.paths import AGENT_ROOT, find_project_root

SKILLS_DIRNAME = "skills"


def get_user_skills_dir(agent: str) -> Path:
    """Return the per-agent skills directory."""
    return AGENT_ROOT / agent / SKILLS_DIRNAME


def ensure_user_skills_dir(agent: str) -> Path:
    """Create and return the per-agent skills directory."""
    skills_dir = get_user_skills_dir(agent)
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def get_project_skills_dir(start: Path | None = None) -> Path | None:
    """Return the project skills directory if inside a git repo."""
    project_root = find_project_root(start)
    if not project_root:
        return None
    return project_root / ".deepdiver" / SKILLS_DIRNAME


def ensure_project_skills_dir(start: Path | None = None) -> Path | None:
    """Create and return the project skills directory if possible."""
    skills_dir = get_project_skills_dir(start)
    if not skills_dir:
        return None
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir
