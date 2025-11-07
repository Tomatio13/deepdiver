"""Utilities for token tracking within the Strands CLI runtime."""

from __future__ import annotations

from typing import Any

from .config import console


def calculate_baseline_tokens(model: Any, system_prompt: str) -> int:
    """Best-effort baseline token counting.

    Strands Agents SDK does not expose a universal token counting API. This helper
    attempts to leverage common methods when available and otherwise falls back to
    returning zero so the CLI can continue without crashing.
    """

    if model is None or system_prompt is None:
        return 0

    candidate_methods = (
        "count_tokens",
        "get_num_tokens_from_messages",
        "get_num_tokens",
    )

    for method_name in candidate_methods:
        method = getattr(model, method_name, None)
        if method is None:
            continue

        try:
            if method_name == "get_num_tokens_from_messages":
                result = method([{"role": "system", "content": system_prompt}])
            else:
                result = method(system_prompt)

            if isinstance(result, dict):
                for key in ("total_tokens", "input_tokens", "tokens"):
                    if key in result:
                        return int(result[key])
                continue

            return int(result)
        except Exception as exc:  # noqa: BLE001 - log and try the next method
            console.print(
                f"[yellow]Warning: Token counting via {method_name} failed: {exc}[/yellow]"
            )

    return 0
