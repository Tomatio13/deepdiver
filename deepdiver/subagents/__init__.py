"""Sub-agents support for Deepdiver CLI.

This package provides:
- File-based sub-agent definitions (Markdown with YAML frontmatter)
- Project > user precedence resolution
- Runtime helpers to execute sub-agents with isolated Agent instances
"""

from .load import SubagentMetadata, get_subagent, list_subagents  # noqa: F401

