"""Shared filesystem paths for Deepdiver."""

from __future__ import annotations

from pathlib import Path

AGENT_ROOT = Path.home() / ".deepdriver"


def find_project_root(start: Path | None = None) -> Path | None:
    """Locate the nearest git project root by walking parents."""
    current = (start or Path.cwd()).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None
