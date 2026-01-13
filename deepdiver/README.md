# Deepdiver CLI (package)

This package implements the Deepdiver interactive CLI on top of the Strands Agents SDK. It wraps common tools (filesystem, shell, HTTP, etc.) and adds agent profiles, skills, subagents, MCP integration, and JSONL transcripts.

## Architecture overview

```
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
├── subagents/             # Subagent system
└── examples/              # Examples
```

## Key modules

- **`agent.py`**: Creates Strands `Agent` instances backed by `~/.deepdiver/<agent>/`. Handles listing/resetting profiles and composing system prompts (including `agent.md`).
- **`config.py`**: Loads environment variables, provides shared console/colors, and resolves model providers via `STRANDS_MODEL_PROVIDER` / `STRANDS_MODEL_CONFIG`.
- **`execution.py`**: Normalizes requests to the agent, injects referenced file context, uses streaming when available, and falls back to blocking invocation.
- **`main.py`**: Parses CLI flags, checks dependencies, registers default tools, loads MCP tools, and runs the interactive loop.
- **`mcp_tools.py`**: Loads MCP tools and suppresses noisy transport errors.
- **`transcripts.py`**: Writes JSONL transcripts and Codex-compatible rollout logs.
- **`skills/`**: Progressive disclosure skills system and `/skills` command.
- **`subagents/`**: Subagent definitions, runtime, and `/subagents` command.

## Agent storage & prompts

- Agents live under `~/.deepdiver/<agent-name>/`.
- `agent.md` stores long-lived instructions. A `memories/` subdirectory is created for additional context files.
- Resetting an agent deletes the directory and restores the default prompt (or copies another agent’s instructions).

## Default tools

`main.py` registers the following Strands Tools by default:

- `file_read`, `file_write`, `editor` – Filesystem access
- `shell` – Terminal commands (subject to user approval)
- `http_request` – Lightweight HTTP requests
- `environment` – Environment variable access
- `calculator`, `current_time` – Utility tools
- `filter_csv_data` – CSV filtering helper
- `delegate_to_subagent`, `delegate_to_subagents_parallel` – Subagent delegation

Additional tools can be appended by extending `DEFAULT_TOOLS` before invoking `create_agent_with_config`.

## JSONL transcripts

When transcripts are enabled, the CLI writes logs under `~/.deepdiver/`:

- Main agent runs: `~/.deepdiver/<agent>/runs/agent-<run_id>.jsonl`
- Rollout sessions: `~/.deepdiver/sessions/YYYY/MM/DD/rollout-<timestamp>-<session_id>.jsonl`

Disable with:

```bash
export DEEPDIVER_TRANSCRIPT=0
```

## Interactive commands

- `/help` – Show an overview of shortcuts and tooling
- `/skills` – Skills management and discovery
- `/subagents` – Subagent management
- `/mcp` – MCP server status
- `/clear` – Clear the terminal
- `/quit` or `/exit` – Terminate the session
- `!<command>` – Execute a shell command (e.g. `!git status`)

## Running in development

```bash
# From project root
uv run python -m deepdiver

# Or install in editable mode
uv pip install -e .
deepdiver
```

## Model configuration

Set model configuration via environment variables, for example:

```bash
export STRANDS_MODEL_PROVIDER=bedrock
export STRANDS_MODEL_CONFIG='{"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "region_name": "us-east-1"}'
```

OpenAI/Anthropic style providers can reuse their existing API key variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). If `STRANDS_MODEL_PROVIDER` is omitted, the Strands Agent constructor selects its own default provider.
