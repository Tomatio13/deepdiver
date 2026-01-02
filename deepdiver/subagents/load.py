"""Sub-agent loader (Markdown + YAML frontmatter) for Deepdiver.

Design goals:
- Simple, safe parsing (no full YAML dependency)
- Progressive disclosure friendly: list metadata without loading full bodies unless needed
- Project > user precedence (same as skills)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict

from .paths import get_project_subagents_dir, get_user_subagents_dir

if TYPE_CHECKING:
    from collections.abc import Iterable

# Maximum size for sub-agent definition files (10MB)
MAX_SUBAGENT_FILE_SIZE = 10 * 1024 * 1024


class SubagentMetadata(TypedDict):
    """Metadata for a sub-agent."""

    name: str
    description: str
    path: str
    source: str  # 'user' or 'project'
    tools: NotRequired[list[str]]
    enable_skills: NotRequired[bool]


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _is_safe_path(path: Path, base_dir: Path) -> bool:
    """Check if a path is safely contained within base_dir."""
    try:
        resolved_path = path.resolve()
        resolved_base = base_dir.resolve()
        resolved_path.relative_to(resolved_base)
        return True
    except ValueError:
        return False
    except (OSError, RuntimeError):
        return False


def _parse_bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in ("true", "yes", "1", "on"):
        return True
    if v in ("false", "no", "0", "off"):
        return False
    return None


def _parse_tools(value: str) -> list[str]:
    # allow comma-separated, ignore empty tokens
    return [t.strip() for t in value.split(",") if t.strip()]


def _parse_frontmatter(content: str) -> dict[str, str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    frontmatter = match.group(1)
    metadata: dict[str, str] = {}
    for line in frontmatter.split("\n"):
        kv = re.match(r"^(\w+):\s*(.+)$", line.strip())
        if kv:
            key, value = kv.groups()
            metadata[key] = value.strip()
    return metadata


def _strip_frontmatter(content: str) -> str:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content
    return content[match.end() :]


def _parse_subagent_metadata(md_path: Path, source: str) -> SubagentMetadata | None:
    try:
        size = md_path.stat().st_size
        if size > MAX_SUBAGENT_FILE_SIZE:
            return None

        content = md_path.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        if not meta:
            return None

        if "name" not in meta or "description" not in meta:
            return None

        parsed: SubagentMetadata = {
            "name": meta["name"],
            "description": meta["description"],
            "path": str(md_path),
            "source": source,
        }

        if "tools" in meta and meta["tools"].strip():
            parsed["tools"] = _parse_tools(meta["tools"])

        if "enable_skills" in meta:
            b = _parse_bool(meta["enable_skills"])
            if b is not None:
                parsed["enable_skills"] = b

        return parsed
    except (OSError, UnicodeDecodeError):
        return None


def _iter_subagent_md_files(subagents_dir: Path) -> Iterable[Path]:
    # Definition files are .md directly under subagents_dir (no recursion by design)
    for p in subagents_dir.iterdir():
        if p.is_file() and p.suffix.lower() == ".md":
            yield p


def _list_subagents(subagents_dir: Path, *, source: str) -> list[SubagentMetadata]:
    subagents_dir = subagents_dir.expanduser()
    if not subagents_dir.exists():
        return []

    try:
        resolved_base = subagents_dir.resolve()
    except (OSError, RuntimeError):
        return []

    items: list[SubagentMetadata] = []
    for md_path in _iter_subagent_md_files(subagents_dir):
        if not _is_safe_path(md_path, resolved_base):
            continue
        meta = _parse_subagent_metadata(md_path, source=source)
        if meta:
            items.append(meta)
    return items


def list_subagents(
    *,
    user_subagents_dir: Path | None = None,
    project_subagents_dir: Path | None = None,
) -> list[SubagentMetadata]:
    """List sub-agents from user and/or project directories.

    Project sub-agents override user sub-agents with the same name.
    """
    merged: dict[str, SubagentMetadata] = {}

    if user_subagents_dir:
        for item in _list_subagents(user_subagents_dir, source="user"):
            merged[item["name"]] = item

    if project_subagents_dir:
        for item in _list_subagents(project_subagents_dir, source="project"):
            merged[item["name"]] = item

    return list(merged.values())


def get_subagent(name: str, *, start: Path | None = None) -> SubagentMetadata | None:
    """Find a sub-agent by name using project>user precedence."""
    user_dir = get_user_subagents_dir()
    project_dir = get_project_subagents_dir(start)
    items = list_subagents(user_subagents_dir=user_dir, project_subagents_dir=project_dir)
    return next((s for s in items if s["name"] == name), None)


def read_subagent_definition(md_path: Path) -> tuple[dict[str, str], str]:
    """Read and split a sub-agent definition into (frontmatter_dict, body_markdown)."""
    content = md_path.read_text(encoding="utf-8")
    meta = _parse_frontmatter(content)
    body = _strip_frontmatter(content).lstrip()
    return meta, body

