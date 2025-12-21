"""Skill prompt generation for Deepdiver."""

from __future__ import annotations

from pathlib import Path

from .load import SkillMetadata, list_skills
from .paths import get_project_skills_dir, get_user_skills_dir


SKILLS_SYSTEM_PROMPT = """

## Skills System

You have access to a skills library that provides specialized capabilities and domain knowledge.

{skills_locations}

**Available Skills:**

{skills_list}

**How to Use Skills (Progressive Disclosure):**

Skills follow a **progressive disclosure** pattern - you know they exist (name + description above), but you only read the full instructions when needed:

1. **Recognize when a skill applies**: Check if the user's task matches any skill's description
2. **Read the skill's full instructions**: The skill list above shows the exact path to use with read_file
3. **Follow the skill's instructions**: SKILL.md contains step-by-step workflows, best practices, and examples
4. **Access supporting files**: Skills may include Python scripts, configs, or reference docs - use absolute paths

**When to Use Skills:**
- When the user's request matches a skill's domain (e.g., "research X" → web-research skill)
- When you need specialized knowledge or structured workflows
- When a skill provides proven patterns for complex tasks

**Skills are Self-Documenting:**
- Each SKILL.md tells you exactly what the skill does and how to use it
- The skill list above shows the full path for each skill's SKILL.md file

**Executing Skill Scripts:**
Skills may contain Python scripts or other executable files. Always use absolute paths from the skill list.

**Example Workflow:**

User: "Can you research the latest developments in quantum computing?"

1. Check available skills above → See "web-research" skill with its full path
2. Read the skill using the path shown in the list
3. Follow the skill's research workflow (search → organize → synthesize)
4. Use any helper scripts with absolute paths

Remember: Skills are tools to make you more capable and consistent. When in doubt, check if a skill exists for the task!
"""


def _format_display_path(path: Path) -> str:
    home = str(Path.home())
    path_str = str(path)
    if path_str.startswith(home):
        return path_str.replace(home, "~", 1)
    return path_str


def _format_skills_locations(user_skills_dir: Path, project_skills_dir: Path | None) -> str:
    locations = [f"**User Skills**: `{_format_display_path(user_skills_dir)}`"]
    if project_skills_dir:
        locations.append(
            f"**Project Skills**: `{_format_display_path(project_skills_dir)}` (overrides user skills)"
        )
    return "\n".join(locations)


def _format_skills_list(skills: list[SkillMetadata], user_skills_dir: Path, project_skills_dir: Path | None) -> str:
    if not skills:
        locations = [_format_display_path(user_skills_dir)]
        if project_skills_dir:
            locations.append(_format_display_path(project_skills_dir))
        return f"(No skills available yet. You can create skills in {' or '.join(locations)})"

    user_skills = [s for s in skills if s["source"] == "user"]
    project_skills = [s for s in skills if s["source"] == "project"]

    lines: list[str] = []

    if user_skills:
        lines.append("**User Skills:**")
        for skill in user_skills:
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            lines.append(f"  → Read `{skill['path']}` for full instructions")
        lines.append("")

    if project_skills:
        lines.append("**Project Skills:**")
        for skill in project_skills:
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            lines.append(f"  → Read `{skill['path']}` for full instructions")

    return "\n".join(lines)


def build_skills_prompt(assistant_id: str) -> str | None:
    """Build the skills section for the system prompt."""
    user_skills_dir = get_user_skills_dir(assistant_id)
    project_skills_dir = get_project_skills_dir()

    skills = list_skills(
        user_skills_dir=user_skills_dir,
        project_skills_dir=project_skills_dir,
    )
    if not skills and not user_skills_dir.exists() and not (project_skills_dir and project_skills_dir.exists()):
        return None

    skills_locations = _format_skills_locations(user_skills_dir, project_skills_dir)
    skills_list = _format_skills_list(skills, user_skills_dir, project_skills_dir)

    return SKILLS_SYSTEM_PROMPT.format(
        skills_locations=skills_locations,
        skills_list=skills_list,
    )
