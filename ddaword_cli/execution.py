"""Task execution helpers for the Strands-based CLI."""

from __future__ import annotations

import asyncio
from typing import Any, Iterable

from rich.markdown import Markdown
from rich.panel import Panel

from .config import COLORS, console
from .input import parse_file_mentions


def _assemble_prompt(user_input: str) -> str:
    prompt_text, mentioned_files = parse_file_mentions(user_input)

    if not mentioned_files:
        return prompt_text

    context_parts = [prompt_text, "\n\n## Referenced Files\n"]
    for file_path in mentioned_files:
        try:
            content = file_path.read_text()
            if len(content) > 50000:
                content = content[:50000] + "\n... (file truncated)"
            context_parts.append(
                f"\n### {file_path.name}\nPath: `{file_path}`\n```\n{content}\n```"
            )
        except Exception as exc:  # noqa: BLE001
            context_parts.append(f"\n### {file_path.name}\n[Error reading file: {exc}]")

    return "\n".join(context_parts)


def _stringify_response(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("output_text", "content", "text", "message"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, list):
                joined = "\n".join(str(item) for item in value)
                if joined.strip():
                    return joined
        return str(response)
    if isinstance(response, Iterable) and not isinstance(response, (bytes, bytearray)):
        joined = "\n".join(_stringify_response(item) for item in response)
        return joined
    return str(response)


def _render_tool_event(event: dict) -> None:
    tool_event = event.get("tool_stream_event")
    if not isinstance(tool_event, dict):
        return

    data = tool_event.get("data")
    if not data:
        return

    console.print(
        Panel(
            _stringify_response(data),
            title="Tool Update",
            border_style=COLORS["tool"],
        )
    )


def _render_model_delta(event: dict, buffer: list[str]) -> None:
    model_event = event.get("model_stream_event")
    if not isinstance(model_event, dict):
        return

    delta = model_event.get("delta") or model_event.get("output_text")
    if not isinstance(delta, str) or not delta:
        return

    buffer.append(delta)
    console.print(delta, style=COLORS["agent"], end="")


def _extract_final_response(event: dict) -> str:
    assistant_event = event.get("assistant_response")
    if isinstance(assistant_event, dict):
        return _stringify_response(assistant_event)
    return ""


async def _invoke_agent(agent: Any, prompt: str) -> str:
    # ステータス表示中はconsole.print()を呼び出さない
    if hasattr(agent, "invoke_async"):
        response = await agent.invoke_async(prompt)
        return _stringify_response(response)

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: agent(prompt))
    return _stringify_response(response)


async def _stream_agent(agent: Any, prompt: str) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    # ステータス表示中はconsole.print()を呼び出さない（ツールイベントやモデルデルタの表示は必要）
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            _render_tool_event(event)
            _render_model_delta(event, response_buffer)

            candidate = _extract_final_response(event)
            if candidate:
                final_response = candidate

        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        # エラー時はステータス表示をクリアしてからメッセージを表示
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
        return await _invoke_agent(agent, prompt)


async def execute_task(
    user_input: str,
    agent: Any,
    assistant_id: str | None,
    session_state,
):
    """Execute a task by delegating to the Strands agent."""

    final_input = _assemble_prompt(user_input)
    
    # 参考コードのパターンに従い、with文でstatusを管理
    # メッセージの最後に\nを追加して、ステータス終了後に改行が入るようにする

    if hasattr(agent, "stream_async"):
        response_text = await _stream_agent(agent, final_input)
    else:
        response_text = await _invoke_agent(agent, final_input)


    console.print()
    console.print(Markdown(response_text), style=COLORS["agent"])
    console.print()

