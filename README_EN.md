<h1 align="center">Deepdiver CLI (Package)</h1>
<p align="center">Interactive CLI implementation built on top of Strands Agents SDK</p>

<p align="center">
  <a href="README.md"><img src="https://img.shields.io/badge/ドキュメント-日本語-white.svg" alt="JA doc"/></a>
  <a href="README_EN.md"><img src="https://img.shields.io/badge/english-document-white.svg" alt="EN doc"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Strands-Agents-2B6CB0" alt="Strands Agents">
  <img src="https://img.shields.io/badge/MCP-Supported-0B5D7A" alt="MCP Supported">
  <img src="https://img.shields.io/badge/Skills-Supported-0B5D7A" alt="Skills Supported">
  <img src="https://img.shields.io/badge/SubAgents-Supported-0B5D7A" alt="SubAgents Supported">
</p>

<p align="center">
  <img src="./assets/screen.png" alt="Deepdiver CLI screen" width="760">
</p>

This package implements the Deepdiver interactive CLI on top of the Strands Agents SDK. It wraps common tools (filesystem, shell, HTTP, etc.) and adds agent profiles, Skills, SubAgents, MCP integration, and JSONL transcripts.

## 🧱 Architecture Overview

```text
deepdiver/
├── __init__.py            # Package exports
├── __main__.py            # Entry point for `python -m deepdiver`
├── agent.py               # Agent lifecycle (storage, prompts, reset)
├── commands.py            # Slash commands and shell integration
├── config.py              # Colors, console, model selection helpers
├── csv_tool.py            # CSV filtering helper
├── default_agent_prompt.md
├── execution.py           # Task execution + streaming helpers
├── input.py               # prompt_toolkit configuration & completions
├── main.py                # CLI orchestration / argument parsing
├── mcp_tools.py           # MCP tool loading / error filtering
├── paths.py               # Shared paths (AGENT_ROOT, project root)
├── transcripts.py         # JSONL transcripts + Codex rollout logs
├── ui.py                  # Help screen renderers
├── skills/                # Skills system
├── subagents/             # SubAgents system
└── examples/              # Examples
```

## 🔑 Key Modules

- **`agent.py`**: Creates Strands `Agent` instances backed by `~/.deepdiver/<agent>/`. Handles listing/resetting profiles and composing system prompts (including `AGENT.md`).
- **`config.py`**: Loads environment variables, provides shared console/colors, and resolves model providers via `STRANDS_MODEL_PROVIDER` / `STRANDS_MODEL_CONFIG`.
- **`execution.py`**: Normalizes requests to the agent, injects referenced file context, uses streaming when available, and falls back to blocking invocation.
- **`main.py`**: Parses CLI flags, checks dependencies, registers default tools, loads MCP tools, and runs the interactive loop.
- **`mcp_tools.py`**: Loads MCP tools and suppresses noisy transport errors.
- **`transcripts.py`**: Writes JSONL transcripts and Codex-compatible rollout logs.
- **`skills/`**: Progressive disclosure Skills system and `/skills` command.
- **`subagents/`**: SubAgents definitions, runtime, and `/subagents` command.

## 📦 Agent Storage & Prompts

- Agents live under `~/.deepdiver/<agent-name>/`.
- `AGENT.md` stores long-lived instructions. A `memories/` subdirectory is created for additional context files.
- Resetting an agent deletes the directory and restores the default prompt (or copies another agent’s instructions).

## 🧰 Default Tools

`main.py` registers the following Strands tools by default:

- `file_read`, `file_write`, `editor` - Filesystem access
- `shell` - Terminal commands (subject to user approval)
- `http_request` - Lightweight HTTP requests
- `environment` - Environment variable access
- `calculator`, `current_time` - Utility tools
- `filter_csv_data` - CSV filtering helper
- `delegate_to_subagent`, `delegate_to_subagents_parallel` - SubAgents delegation

Additional tools can be appended by extending `DEFAULT_TOOLS` before invoking `create_agent_with_config`.

## 📝 JSONL Transcripts

When transcripts are enabled, the CLI writes logs under `~/.deepdiver/`:

- Main agent runs: `~/.deepdiver/<agent>/runs/agent-<run_id>.jsonl`
- Rollout sessions: `~/.deepdiver/sessions/YYYY/MM/DD/rollout-<timestamp>-<session_id>.jsonl`

Disable with:

```bash
export DEEPDIVER_TRANSCRIPT=0
```

## ⌨️ Interactive Commands

- `/help` - Show an overview of shortcuts and tooling
- `/skills` - Skills management and discovery
- `/subagents` - SubAgents management
- `/mcp` - MCP server status
- `/clear` - Clear the terminal
- `/quit` or `/exit` - Terminate the session
- `!<command>` - Execute a shell command (e.g. `!git status`)

## 🔌 MCP Integration (How to Configure)

Deepdiver loads MCP settings per agent.

- Config file: `~/.deepdiver/<agent-name>/mcp.json`
- Check command: `/mcp`
- Format: top-level `mcpServers`, and each server must define either `url` or `command`

Minimal example (HTTP/SSE):

```json
{
  "mcpServers": {
    "docs": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

Minimal example (stdio):

```json
{
  "mcpServers": {
    "local": {
      "command": "node",
      "args": ["./server.js"],
      "env": {
        "API_KEY": "your_key"
      }
    }
  }
}
```

Notes:

- A `url` ending with `/sse` is treated as SSE transport.
- Other `url` values are treated as Streamable HTTP transport.
- If one MCP server fails to connect, it is skipped and the CLI continues.

## 🧩 Agent Skills (How to Configure)

Skills are loaded from directories that contain `SKILL.md`.

- User skills: `~/.deepdiver/<agent-name>/skills/`
- Project skills: `<git-root>/.deepdiver/skills/`
- Precedence: project skills override user skills with the same name
- Check command: `/skills`

Directory example:

```text
~/.deepdiver/agent/skills/
└── my-skill/
    └── SKILL.md
```

Minimal `SKILL.md` example:

```markdown
---
name: my-skill
description: Explain how and when to use this skill.
---

# My Skill
Use this workflow when the user asks for ...
```

How to use:

- Use `/skills` to list available skills
- Use `/skills <name>` to view details
- Prefix your prompt with `$my-skill` (example: `$my-skill break down this task`)

## 🚀 Running in Development

```bash
# From project root
uv run python -m deepdiver

# Or install in editable mode
uv pip install -e .
deepdiver
```

## ⚙️ Model Configuration

Set model configuration via environment variables, for example:

```bash
export STRANDS_MODEL_PROVIDER=bedrock
export STRANDS_MODEL_CONFIG='{"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "region_name": "us-east-1"}'
```

OpenAI/Anthropic-style providers can reuse their existing API key variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). If `STRANDS_MODEL_PROVIDER` is omitted, the Strands Agent constructor selects its own default provider.

## 🛡️ Prompt Injection Defender

The CLI includes a lightweight prompt-injection defender for user/SubAgents inputs.

```bash
export DEFENDER_ENABLED=true
export DEFENDER_DEFAULT_MODE=warn
export DEFENDER_WARN_THRESHOLD=0.35
export DEFENDER_BLOCK_THRESHOLD=0.95
export DEFENDER_SANITIZE_MODE=full-redact
```

- `DEFENDER_DEFAULT_MODE`: `warn`, `sanitize`, or `block`
- `DEFENDER_SANITIZE_MODE`: currently supports `full-redact`

## 📚 Terminology

This README consistently uses **`SubAgents`** as the canonical feature name.
