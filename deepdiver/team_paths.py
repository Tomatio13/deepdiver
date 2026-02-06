"""Paths for team sessions and message bus storage."""

from __future__ import annotations

from pathlib import Path

from .paths import AGENT_ROOT

TEAMS_DIRNAME = "teams"
BUS_DIRNAME = "bus"
STATE_DIRNAME = "state"


def get_teams_root() -> Path:
    """Return the base directory for all team sessions."""
    return AGENT_ROOT / TEAMS_DIRNAME


def ensure_teams_root() -> Path:
    """Create and return the base directory for all team sessions."""
    root = get_teams_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_team_dir(session_id: str) -> Path:
    """Return the directory for a team session."""
    return get_teams_root() / session_id


def ensure_team_dir(session_id: str) -> Path:
    """Create and return the directory for a team session."""
    d = get_team_dir(session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_team_bus_dir(session_id: str) -> Path:
    """Return the bus directory for a team session."""
    return get_team_dir(session_id) / BUS_DIRNAME


def ensure_team_bus_dir(session_id: str) -> Path:
    """Create and return the bus directory for a team session."""
    d = get_team_bus_dir(session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_team_state_dir(session_id: str) -> Path:
    """Return the worker state directory for a team session."""
    return get_team_dir(session_id) / STATE_DIRNAME


def ensure_team_state_dir(session_id: str) -> Path:
    """Create and return the worker state directory for a team session."""
    d = get_team_state_dir(session_id)
    d.mkdir(parents=True, exist_ok=True)
    return d

