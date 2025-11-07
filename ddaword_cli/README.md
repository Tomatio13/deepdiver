# Strands Agents CLI

This package provides an interactive command-line interface powered by the Strands Agents SDK. The CLI wraps the Strands toolchain (filesystem, shell, HTTP, etc.) so you can collaborate with an autonomous agent directly from the terminal.

## Architecture overview

```
ddaword_cli/
├── __init__.py      # Package exports
├── __main__.py      # Entry point for `python -m ddaword_cli`
├── agent.py         # Agent lifecycle (storage, prompts, reset)
├── commands.py      # Slash commands and shell integration
├── config.py        # Colors, console, model selection helpers
├── execution.py     # Task execution + streaming helpers
├── input.py         # prompt_toolkit configuration & completions
├── main.py          # CLI orchestration / argument parsing
└── ui.py            # Help screen renderers
```

### Key modules

- **`agent.py`** – Creates Strands `Agent` instances backed by `~/.strands-agents-cli/<agent>/`. Handles listing/resetting profiles and composing system prompts that embed `agent.md` instructions.
- **`config.py`** – Loads environment variables, provides shared colors/console objects, and resolves model providers via `STRANDS_MODEL_PROVIDER` / `STRANDS_MODEL_CONFIG`.
- **`execution.py`** – Normalises requests to the agent. Adds referenced file context, uses streaming when available, and falls back to blocking invocation otherwise.
- **`commands.py`** – Implements `/help`, `/clear`, and bang-prefixed shell commands.
- **`input.py`** – Configures prompt_toolkit (multiline input, history, `/` + `@` completions, toolbar bindings).
- **`main.py`** – Parses CLI flags, performs dependency checks, selects the model, registers default Strands tools (`file_read`, `file_write`, `editor`, `shell`, `http_request`, `environment`), and runs the interactive loop.
- **`ui.py`** – Provides interactive/help renderers.

## Agent storage & prompts

- Agents live under `~/.strands-agents-cli/<agent-name>/`.
- `agent.md` stores long-lived instructions. A `memories/` subdirectory is created for additional context files.
- Resetting an agent deletes the directory and restores the default prompt (or copies another agent’s instructions).

## Default tools

`main.py` registers the following Strands Tools by default:

- `file_read`, `file_write`, `editor` – Filesystem access
- `shell` – Terminal commands (subject to user approval)
- `http_request` – Lightweight HTTP requests
- `environment` – Environment variable management

Additional tools can be appended by extending the list before invoking `create_agent_with_config`.

## Interactive commands

- `/help` – Show an overview of shortcuts and tooling
- `/clear` – Clear the terminal
- `/quit` or `/exit` – Terminate the session
- `!<command>` – Execute a shell command (e.g. `!git status`)

## Running in development

```bash
# From project root
uv run python -m ddaword_cli

# Or install in editable mode
uv pip install -e .
ddaword
```

### Model configuration

Set model configuration via environment variables, for example:

```bash
export STRANDS_MODEL_PROVIDER=bedrock
export STRANDS_MODEL_CONFIG='{"model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0", "region_name": "us-east-1"}'
```

OpenAI/Anthropic style providers can reuse their existing API key variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.). If `STRANDS_MODEL_PROVIDER` is omitted, the Strands Agent constructor selects its own default provider.

