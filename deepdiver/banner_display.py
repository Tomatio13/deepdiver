#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_BANNER_FILE = BASE_DIR / "banner.txt"
_BANNER_GRADIENT = (153, 117, 111, 104, 183, 169, 225, 168)


def _style():
    if not sys.stdout.isatty():
        return type("Style", (), {"dim": "", "bold": "", "gemma": "", "reset": ""})()
    return type("Style", (), {
        "dim": "\033[2m",
        "bold": "\033[1m",
        "gemma": "\033[32m",
        "reset": "\033[0m",
    })()


def apply_gradient_line(line: str, use_color: bool) -> str:
    if not use_color or not line:
        return line
    n = len(_BANNER_GRADIENT)
    out: list[str] = []
    last_idx = -1
    for i, char in enumerate(line):
        idx = (i * n) // len(line)
        if idx != last_idx:
            out.append(f"\033[38;5;{_BANNER_GRADIENT[idx]}m")
            last_idx = idx
        out.append(char)
    out.append("\033[0m")
    return "".join(out)


def print_banner(
    banner_file: Path = DEFAULT_BANNER_FILE,
    *,
    show_hint: bool = True,
    fallback_title: str = "GEM CHAT",
) -> None:
    s = _style()
    use_color = sys.stdout.isatty()
    print()
    if banner_file.is_file():
        try:
            raw = banner_file.read_text(encoding="utf-8")
            lines = [line.rstrip() for line in raw.splitlines() if line.strip()]
            for line in lines:
                print(f"  {s.bold}{apply_gradient_line(line, use_color)}{s.reset}")
        except OSError:
            print(f"  {s.bold}{s.gemma}{fallback_title}{s.reset}")
    else:
        print(f"  {s.bold}{s.gemma}{fallback_title}{s.reset}")
    print()
    if show_hint:
        print(f"  {s.dim}▸ Talk to me. Type quit or exit to end.{s.reset}")
        print()


def print_deepdiver_banner(*, show_hint: bool = False) -> None:
    """Render the Deepdiver banner with local defaults for this CLI."""
    print_banner(show_hint=show_hint, fallback_title="DEEPDIVER")
