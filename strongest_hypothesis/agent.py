"""Strongest hypothesis selector and report generator.

design.mdの要件に従って、reports配下の複数レポートから仮説情報を抽出し、
カテゴリ分けと総当たり比較で最強仮説を選定し、13章構成の統合レポートを生成します。

追加要件:
- 生成物は「選定サマリー（選定理由と元レポート・仮説ID付き）」と「最終レポート（元レポート名は記載しない）」の2本立て
- レビュー（consulting_promptsのreport_reviewer）を実施し、フィードバックを反映しながら最大3回リトライ
- 選定サマリーは別ファイルに保存し、最終レポートは元レポート名を含めない
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from strands import Agent

from ddaword_cli.config import COLORS, console, create_model
from ddaword_cli.consulting_prompts import CONSULTING_PROMPTS


MAX_SECTION_CHARS = 5000


STRONGEST_SYSTEM_PROMPT = """
あなたは経営コンサルタント兼レポート統合エージェントです。
- design.mdに記載された手順を厳守し、複数レポートの仮説をカテゴリ分け、総当たり比較を行い、カテゴリごとに最強の仮説を選定します。
- 選定サマリーでは必ず元レポート名と仮説IDを併記します（例: reportA:H1）。
- 最終レポートでは元レポート名・IDを記載してはなりません。
- 判定・信頼度・主要指標などが不足している場合は「不明」と明示し、前提を合理的に補足します。
- 90日アクションプランは実行可能な具体策を3〜5項目で提示します。
- 出力は日本語で行い、マークダウンの見出し・表現を簡潔にまとめます。
- 必ず次の2部構成で出力します:
  1) 「## 選定サマリー」: カテゴリ別の最強仮説概要と選定理由、元レポート名・仮説ID付き
  2) 「## 統合レポート」: 13セクション構成（design.md準拠）、元レポート名・IDは記載しない
"""

SUMMARY_HEADING = "## 選定サマリー"
FINAL_HEADING = "## 統合レポート"


def _stringify_response(response: Any) -> str:
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if hasattr(response, "output_text"):
        return str(response.output_text)
    if hasattr(response, "content"):
        return str(response.content)
    if isinstance(response, dict):
        for key in ("output_text", "content", "text", "message"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return str(response)
    return str(response)


def _sanitize_final_report(text: str) -> str:
    # reportA:H1のような参照は最終レポートから除去する
    cleaned = re.sub(r"report[\w-]*:H\d+", "", text, flags=re.IGNORECASE)
    # 連続スペースのみを1個に圧縮（改行は保持）
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    # 3つ以上の連続改行は2つに圧縮
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _clamp(text: str, limit: int = MAX_SECTION_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = limit - 200
    tail = 200
    return text[:head] + "\n... (truncated) ...\n" + text[-tail:]


def _extract_markdown_section(content: str, keyword: str) -> str | None:
    pattern = rf"(?ms)^#{1,6}\s.*{re.escape(keyword)}.*?$.*?(?=^#{1,6}\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE)
    if match:
        return match.group(0).strip()
    return None


def _extract_hypothesis_blocks(content: str) -> list[str]:
    patterns = [
        r"(?ms)^###\s+ID:\s*(H\d+).*?(?=^###\s+ID:|^##\s+ID:|^#|\Z)",
        r"(?ms)^##\s*(H\d+).*?(?=^##\s*H\d+|^#|\Z)",
    ]
    blocks: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, content, re.MULTILINE):
            blocks.append(match.group(0).strip())
    return blocks


def _build_report_context(report_path: Path) -> str:
    raw = report_path.read_text()
    sections: list[str] = []

    for keyword in [
        "仮説の整理",
        "仮説検証",
        "仮説検証の結果",
        "意思決定",
        "エグゼクティブサマリー",
    ]:
        section = _extract_markdown_section(raw, keyword)
        if section:
            sections.append(section)

    hypothesis_blocks = _extract_hypothesis_blocks(raw)
    if hypothesis_blocks:
        sections.append("## 抽出した仮説\n" + "\n\n".join(hypothesis_blocks))

    if not sections:
        sections.append(_clamp(raw))

    combined = "\n\n".join(sections)
    combined = _clamp(combined)
    return f"### レポート: {report_path.name}\n{combined}"


def _build_prompt(design_text: str, report_contexts: list[str]) -> str:
    reports_block = "\n\n".join(report_contexts)
    return (
        "# design.mdの要件\n"
        + design_text.strip()
        + "\n\n# 入力レポート概要\n"
        + reports_block
        + "\n\n# 出力指示\n"
        "- design.mdに沿ってカテゴリ分けと最強仮説選定を行うこと\n"
        "- 必ず2部構成で出力すること: 1) 選定サマリー, 2) 統合レポート\n"
        "- 選定サマリーでは参照元レポート名と仮説IDを明記すること\n"
        "- 統合レポートには元レポート名/IDを記載しないこと\n"
        "- 統合レポートは13セクション構成（design.md準拠）で書くこと\n"
    )


async def generate_strongest_report(
    reports_dir: Path | None = None,
    design_path: Path | None = None,
    output_path: Path | None = None,
    selection_output_path: Path | None = None,
) -> Path:
    """design.mdとレポート群を入力に、統合レポートを生成する。"""

    base_dir = Path.cwd() / "strongest_hypothesis"
    reports_dir = (reports_dir or base_dir / "reports").resolve()
    design_path = (design_path or base_dir / "design.md").resolve()

    if not design_path.exists():
        raise FileNotFoundError(f"design.mdが見つかりません: {design_path}")
    if not reports_dir.exists() or not reports_dir.is_dir():
        raise FileNotFoundError(f"レポートディレクトリが見つかりません: {reports_dir}")

    report_files = sorted(reports_dir.glob("*.md"))
    if not report_files:
        raise FileNotFoundError(f"{reports_dir} にMarkdownレポートがありません")

    design_text = design_path.read_text()
    report_contexts = [_build_report_context(path) for path in report_files]
    prompt = _build_prompt(design_text, report_contexts)

    model = create_model()
    writer_agent = Agent(model=model, system_prompt=STRONGEST_SYSTEM_PROMPT, tools=[])
    reviewer_agent = Agent(model=model, system_prompt=CONSULTING_PROMPTS["report_reviewer"], tools=[])

    max_retries = 3
    current_feedback = ""
    final_summary = ""
    final_report = ""

    for attempt in range(max_retries):
        is_last = attempt == max_retries - 1
        attempt_note = f"(Attempt {attempt + 1}/{max_retries})"
        console.print(f"[{COLORS['info']}]最強仮説の集約を実行中... {attempt_note}[/]")

        body_prompt = prompt
        if current_feedback:
            body_prompt += f"\n\n# レビューからのフィードバック\n{current_feedback}\n"

        response = await writer_agent.invoke_async(body_prompt)
        content = _stringify_response(response).strip()

        # セクション分割
        summary_match = re.search(
            rf"(?ms){SUMMARY_HEADING}.*?(?=^##\s|\Z)", content, re.MULTILINE
        )
        report_match = re.search(
            rf"(?ms){FINAL_HEADING}.*", content, re.MULTILINE
        )
        summary_text = summary_match.group(0).strip() if summary_match else ""
        report_text = report_match.group(0).strip() if report_match else content

        report_text = _sanitize_final_report(report_text)

        # レビュー
        review_prompt = f"{FINAL_HEADING}\n{report_text}\n\n上記のレポートをレビューしてください。\n**重要: 出力は必ず \"OK\" または \"NG: <理由>\" の形式のみにしてください。余計な挨拶や説明は不要です。**"
        review_result = await reviewer_agent.invoke_async(review_prompt)
        review_text = _stringify_response(review_result).strip()

        if review_text.startswith("OK"):
            console.print(f"[{COLORS['success']}]  Review passed![/]")
            final_summary = summary_text
            final_report = report_text
            break
        else:
            error_reason = review_text.replace("NG:", "").strip()
            console.print(f"[{COLORS['warning']}]  Review failed: {error_reason}[/]")
            if not is_last:
                current_feedback += f"\n- {error_reason}"
                continue
            final_summary = summary_text
            final_report = report_text
            console.print(f"[{COLORS['error']}]  Max retries reached. Saving last result.[/]")

    # 保存
    target_path = (output_path or reports_dir.parent / "strongest_report.md").resolve()
    summary_path = (selection_output_path or reports_dir.parent / "selection_summary.md").resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    if final_summary:
        summary_path.write_text(final_summary + "\n")
    final_report = final_report if final_report else content
    target_path.write_text(final_report + "\n")

    console.print(f"[green]✓ 統合レポートを生成しました[/green] {target_path}", style=COLORS["success"])
    console.print(f"[green]✓ 選定サマリーを保存しました[/green] {summary_path}", style=COLORS["success"])
    return target_path


if __name__ == "__main__":
    asyncio.run(generate_strongest_report())
