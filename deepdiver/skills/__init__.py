"""Skills module for Deepdiver CLI.

Public API:
- execute_skills_command: Execute skills subcommands (list/create/info)
- setup_skills_parser: Setup argparse configuration for skills commands
- build_skills_prompt: Build skills section for the system prompt
"""

from .commands import execute_skills_command, setup_skills_parser
from .prompt import build_skills_prompt

__all__ = ["build_skills_prompt", "execute_skills_command", "setup_skills_parser"]
