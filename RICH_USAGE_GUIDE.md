# Rich 活用マニュアル（LangCode 抽出版）

LangCode CLI は `rich` を UI レイヤーの中核に据え、メッセージの可視化から対話型ランチャーまで一貫して表現しています。本書は主要パターンを切り出し、他プロジェクトでも `rich` をフル活用できるようサンプルコード付きで説明します。ファイルパスは `src/langchain_code/` からの相対指定です。

## 凡例
- `ファイルパス:開始行` 形式で由来を記載。ただし、以下サンプルだけで完結するよう構成しているため、手元に元リポジトリがなくても利用可能です。
- コードは最小限の依存でそのままコピーできる形を目指しています。`...` の部分のみ各環境に合わせて実装してください。

---

## 1. Console 単一化と共有状態
由来: `cli_components/state.py:7-51`

```python
# state.py
from contextlib import contextmanager
from typing import Optional
from rich.console import Console

console = Console()
current_live = None  # Liveインスタンスを共有
_edit_feedback_enabled = False

def set_live(live) -> None:
    global current_live
    current_live = live

def edit_feedback_enabled() -> bool:
    return _edit_feedback_enabled

@contextmanager
def edit_feedback():
    global _edit_feedback_enabled
    prev = _edit_feedback_enabled
    _edit_feedback_enabled = True
    try:
        yield
    finally:
        _edit_feedback_enabled = prev
```

ポイント:
- `Console()` は 1 箇所で生成し、他モジュールは `from .state import console` で利用。
- Live 表示を跨ぐ処理（入力パッチなど）のために `current_live` を共有。

---

## 2. トースト/通知パネル
由来: `cli/commands/configure.py:16-32`, `cli_components/env.py:148-168`

```python
# notifications.py
from rich.panel import Panel
from rich.text import Text
from .state import console

def toast(message: str, kind: str = "info") -> None:
    color = {
        "success": "green",
        "warning": "yellow",
        "error": "red",
    }.get(kind, "cyan")
    console.print(Panel.fit(Text(message, style=color), border_style=color))
```

ポイント:
- `Panel.fit` で幅を抑えつつメッセージを目立たせる。
- スタイル種別を固定して CLI 全体で統一感を出す。

---

## 3. セッションヘッダーと画面レイアウト
由来: `cli_components/display.py:21-191`

```python
# display.py
from rich import box
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from pyfiglet import Figlet
from .state import console

def ascii_banner(text: str = "LangCode") -> None:
    fig = Figlet(font="ansi_shadow", width=getattr(console.size, "width", 80))
    console.print(fig.renderText(text), style="bold green")

def print_session_header(title: str, project: str, provider: str | None) -> None:
    console.clear()
    ascii_banner()
    body = Text()
    body.append(f"{title}\n", style="bold magenta")
    body.append(f"Project: {project}\nProvider: {provider or 'not set'}", style="dim")
    console.print(Panel(body, border_style="green", box=box.HEAVY, padding=(1, 2)))
    console.print(Rule(style="green"))
```

ポイント:
- セクション分けに `Rule` を入れて画面遷移を明示。
- 重要メタ情報（プロバイダ、モードなど）を `Text` 組み立てで表示。

---

## 4. Markdown/ANSI 出力の自動判別
由来: `cli_components/display.py:193-285`

```python
from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

def looks_like_markdown(text: str) -> bool:
    return any(token in text for token in ("```", "# ", "- ", "* ", "`"))

def render_agent_output(raw: str, title: str = "Agent") -> Panel:
    if looks_like_markdown(raw):
        body = Markdown(raw)
    else:
        body = Text.from_ansi(raw) if "\x1b[" in raw else Text(raw)
        body.overflow = "fold"
    return Panel(body, title=title, border_style="cyan", box=box.ROUNDED, padding=(1, 2))
```

ポイント:
- Markdown 判定を挟むことで LLM 出力を崩さず表示。
- ANSI コード付きログも `Text.from_ansi` で見やすく整形。

---

## 5. ダッシュボード（Table + Panel + Columns）
由来: `cli/commands/system.py:31-141`

```python
from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from .state import console

def provider_table(status_map: dict[str, bool]) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column("Provider")
    table.add_column("Status")
    for name, ok in status_map.items():
        table.add_row(name.upper(), "[green]OK[/green]" if ok else "[red]missing[/red]")
    return Panel(table, title="Providers", border_style="cyan")

def show_cards(cards: dict[str, str]) -> None:
    panels = [Panel(Text(msg), title=title, border_style="green") for title, msg in cards.items()]
    console.print(Columns(panels))
```

ポイント:
- `Table.grid` で柔軟なレイアウト、`Columns` でカードを横置き。
- ステータスカードは 1 トピック 1 パネルで視認性アップ。

---

## 6. TODO ボードと差分表示
由来: `cli_components/todos.py:11-68`, `cli_components/runtime.py:60-116`

```python
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ICON = {"pending": "○", "in_progress": "◔", "completed": "✓"}
STYLE = {"pending": "dim", "in_progress": "yellow", "completed": "green"}

def normalize_todos(todos):
    blocked = False
    output = []
    for todo in todos:
        status = todo.get("status", "pending")
        if blocked and status != "completed":
            status = "pending"
        if status != "completed":
            blocked = True
        output.append({**todo, "status": status})
    return output

def render_todos_panel(todos):
    todos = normalize_todos(todos)
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", width=3, no_wrap=True)
    table.add_column()
    for idx, item in enumerate(todos, 1):
        status = item["status"]
        text = Text(item.get("content", "(empty)"), style=STYLE[status])
        if status == "completed":
            text.stylize("strike")
        table.add_row(f"{idx}.", Text.assemble(Text(ICON[status] + " ", style=STYLE[status]), text))
    return Panel(table, title="TODOs", border_style="blue", box=box.ROUNDED, padding=(1, 1))
```

差分例:

```python
def diff_todos(before, after):
    changes = []
    for idx, (prev, curr) in enumerate(zip(normalize_todos(before), normalize_todos(after)), 1):
        if prev["status"] != curr["status"]:
            changes.append(f"[{idx}] {curr.get('content', '')} -> {curr['status']}")
    return changes
```

---

## 7. Live 表示とアニメーション
由来: `cli/commands/chat.py:76-133`, `cli_components/launcher.py:377-420`

```python
from time import sleep
from rich.live import Live
from .state import console, set_live
from .todos import render_todos_panel

def animate_todos(todos):
    placeholder = render_todos_panel([])
    with Live(placeholder, console=console, refresh_per_second=12) as live:
        set_live(live)
        for idx in range(len(todos)):
            view = []
            for j, todo in enumerate(todos):
                status = "completed" if j < idx else "in_progress" if j == idx else "pending"
                view.append({**todo, "status": status})
            live.update(render_todos_panel(view))
            sleep(0.2)
        set_live(None)
```

ポイント:
- `Live` を context manager で扱い、状態を `state.set_live` に保存。
- 他の処理（入力ダイアログ等）が Live と競合しないよう pause/fallback を準備。

---

## 8. 入力/確認 UX（InputPatch + Confirm）
由来: `cli_components/runtime.py:19-57`, `safety/confirm.py:1-10`

```python
import builtins
from contextlib import nullcontext
from rich import box
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
from .state import console, current_live

class InputPatch:
    def __enter__(self):
        self._orig = builtins.input
        def _rich_input(prompt: str = "") -> str:
            cm = current_live.pause() if current_live and getattr(current_live, "pause", None) else nullcontext()
            with cm:
                body = Text(prompt or "Provide input (Y/N).", style="bold")
                console.print(Panel(body, border_style="yellow", box=box.ROUNDED))
                return console.input("[bold yellow]›[/bold yellow] ").strip()
        builtins.input = _rich_input
        return self
    def __exit__(self, exc_type, exc, tb):
        builtins.input = self._orig
        return False

def confirm_action(message: str, auto: bool = False) -> bool:
    if auto:
        return True
    return Confirm.ask(message)
```

ポイント:
- `current_live.pause()` を呼んで Live 更新と競合しないようにする。
- Confirm 1 つで Yes/No を統一処理。

---

## 9. ローダー／スピナー
由来: `cli_components/display.py:287-289`

```python
from .state import console

def show_loader():
    return console.status("[bold]Processing...[/bold]", spinner="dots", spinner_style="green")

def run_with_loader(fn, *args, **kwargs):
    with show_loader():
        return fn(*args, **kwargs)
```

ポイント:
- `console.status` context manager を返し、`with show_loader():` 形式で簡潔に利用。
- spinner の種類・色を統一してブランド感を出す。

---

## 10. エディタ操作と編集サマリ
由来: `cli_components/env.py:148-309`, `cli_components/mcp.py:52-103`

```python
from pathlib import Path
import difflib
from rich.panel import Panel
from rich.text import Text
from .state import console, edit_feedback

def diff_stats(before: str, after: str) -> tuple[int, int]:
    added = removed = 0
    for line in difflib.ndiff(before.splitlines(), after.splitlines()):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1
    return added, removed

def edit_text_file(path: Path, new_content: str) -> None:
    with edit_feedback():
        before = path.read_text()
        if before == new_content:
            console.print(Panel.fit(Text("No changes saved.", style="yellow"), border_style="yellow"))
            return
        path.write_text(new_content)
        added, removed = diff_stats(before, new_content)
        console.print(Panel.fit(Text(f"Saved {path}\n+{added} / -{removed}", style="green"), border_style="green"))
```

ポイント:
- 編集中のみ通知を出したい場合は `edit_feedback()` コンテキストで制御。
- 変更量を表示し、設定ファイル編集の可視性を高める。

---

## 11. 実装チェックリスト
1. `state.py` で `Console` と Live 参照を一元管理。
2. 成功／警告トースト、Markdown レンダリング、TODO 表示、ダッシュボードなど View コンポーネントを `display.py` 相当へ集約。
3. リアルタイム描画は `Live` を使い、必ず `state.current_live` を更新して他の入出力と連携。
4. 入力確認フローは `InputPatch` + `Confirm.ask` で統一し、Live やスピナーと干渉しないよう pause 処理を追加。
5. 設定ファイル編集や環境変数ローダーは「編集→差分計測→Panel.fit で結果表示」をセットで実装。

---

これらのパターンを組み合わせれば、LangCode が提供するエージェント CLI 体験を他プロジェクトでも再現できます。描画ロジックをヘルパーモジュールに閉じ込め、業務ロジックと疎結合に保つことが最大のコツです。コピー可能なサンプルを土台に、各プロジェクトの要件へカスタマイズしてください。
