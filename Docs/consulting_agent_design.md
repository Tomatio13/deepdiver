# 経営コンサルエージェント設計書

## 1. 概要

### 1.1 目的
売上や人事情報が含まれるCSVファイルから経営課題を分析し、その対策を立案するマルチエージェントシステムを構築する。
cc-sddのようなスラッシュコマンド形式で、Human in the Loopを組み込んだワークフローを実現する。

### 1.2 アーキテクチャ
- **スラッシュコマンド形式**: `/consulting:*` コマンドで各ステップを実行
- **Human in the Loop**: 各重要なステップで人の承認を必要とする
- **状態管理**: `consulting.json`で現在の状態を管理（cc-sddの`spec.json`と同様）
- **成果物管理**: 全ての成果物（仮説、データ、検証結果など）をMarkdownファイルで保存
- **各エージェント**: `csv_tool.py`と同様に`@tool`デコレータで定義されたsubagentとして実装
- **プロンプト管理**: 各エージェントのプロンプトは一箇所で管理（`consulting_prompts.py`）

## 2. エージェントフロー

### 2.1 処理フロー（Human in the Loop付き）
```
/consulting:init <analysis_focus> <csv_path1> [csv_path2] ...
  ↓
/consulting:hypothesis
  ↓ [人が承認]
/consulting:process-data
  ↓
/consulting:validate
  ↓ [人が承認/否決]
  ├─ 否決 → /consulting:hypothesis (再実行)
  └─ 承認 → /consulting:strategy
              ↓ [人が承認]
              /consulting:report
                ↓ [人が承認]
                完了
```

- 否決が発生した場合、CLIが理由入力を必須化し、その内容を`feedback`として保存する。再実行時、各エージェントは直近のフィードバックを参照して出力を調整する。
- `/consulting:status [project_name]`は現在の進捗を表示した後、状態に応じた次のコマンド（例: `/consulting:hypothesis <project_name>`）を案内する。

### 2.2 スラッシュコマンド一覧

| コマンド | 説明 | 承認必要 |
|---------|------|---------|
| `/consulting:init <analysis_focus> <csv_path1> [csv_path2] ...` | 分析を初期化し、作業ディレクトリを作成。analysis_focusからAIで`単語_単語`形式（英小文字、数字なし、最大24文字）のproject_nameを生成。フォルダ指定の場合は、そのフォルダ内のすべてのCSVファイルを再帰的に検索 | - |
| `/consulting:hypothesis <project_name>` | 仮説を生成。複数ファイルを読み込み、過去のフィードバックも参照 | あり |
| `/consulting:process-data <project_name>` | データを整理・加工。仮説否決時のフィードバックを考慮 | - |
| `/consulting:validate <project_name>` | 仮説を検証。否決理由を収集し、再実行時に活用 | あり（承認/否決） |
| `/consulting:strategy <project_name>` | 戦略を立案。検証結果のフィードバックを参照 | あり |
| `/consulting:report <project_name>` | レポートを生成。各ステップの成果物とフィードバックを統合 | あり |
| `/consulting:status [project_name]` | 現在の状態を表示し、推奨される次のコマンドを案内 | - |
| `/consulting:approve <project_name>` | 現在のステップを承認 | - |
| `/consulting:reject <project_name>` | 現在のステップを否決（理由入力必須。検証否決時は仮説生成へ戻り、理由を共有） | - |

### 2.3 各エージェントの役割

#### 2.3.1 仮説立案エージェント (`hypothesis_generator`)
- **入力**: 複数のCSVファイルパス、データ概要、前回の検証結果（リトライ時）
- **出力**: 経営課題の仮説リスト（Markdown形式）
- **処理内容**:
  - 複数のCSVデータの概要を分析
  - 売上・人事情報から潜在的な経営課題を特定
  - ファイル間の関連性も考慮
  - 最新のフィードバック（否決理由など）を参照して仮説を再提示
  - 優先度付きの仮説リストを生成
  - Markdownファイルに保存

#### 2.3.2 データ整理・加工エージェント (`data_processor`)
- **入力**: 複数のCSVファイルパス、仮説リスト（consulting.jsonから取得）
- **出力**: 検証用に加工されたデータの説明（Markdown形式）
- **処理内容**:
  - 仮説検証に必要なデータを複数ファイルから抽出・集計
  - ファイル間の関連性を考慮したデータ加工
  - 時系列分析、部門別集計、トレンド分析など
  - 可視化用のデータ準備
  - 仮説で受け取ったフィードバックを踏まえて加工内容を調整
  - Markdownファイルに保存

#### 2.3.3 仮説検証エージェント (`hypothesis_validator`)
- **入力**: 加工済みデータ、仮説リスト（consulting.jsonから取得）
- **出力**: 検証結果（各仮説の成立/不成立、根拠データ）（Markdown形式）
- **処理内容**:
  - データに基づいて仮説を検証
  - 統計的分析を実施
  - 検証結果と根拠を出力
  - 否決理由を考慮した重点的な検証ポイントの提示
  - Markdownファイルに保存

#### 2.3.4 戦略立案エージェント (`strategy_planner`)
- **入力**: 検証済み仮説リスト、根拠データ（consulting.jsonから取得）
- **出力**: 対策・戦略案（優先度付き）（Markdown形式）
- **処理内容**:
  - 検証済み課題に対する対策を立案
  - 優先度と影響度を考慮
  - 実装可能性を評価
  - 検証段階で得られたフィードバックをもとに戦略を調整
  - Markdownファイルに保存

#### 2.3.5 レポート作成エージェント (`report_generator`)
- **入力**: 全エージェントの出力（consulting.jsonから取得）
- **出力**: 最終レポート（Markdown形式）
- **処理内容**:
  - 分析結果を統合
  - 構造化されたレポートを生成
  - グラフ・表の推奨を含む
  - 全ステップのフィードバックを反映した最終報告を作成
  - Markdownファイルに保存

## 3. 実装設計

### 3.1 ファイル構成
```
ddaword_cli/
├── consulting_commands.py      # スラッシュコマンドハンドラー
├── consulting_state.py          # 状態管理（consulting.json）
├── consulting_agents.py         # 各サブエージェントの実装
├── consulting_prompts.py        # プロンプト管理
└── consulting_utils.py           # 共通ユーティリティ関数

# 作業ディレクトリ構造（各分析プロジェクトごと）
.consulting/
└── <project_name>/
    ├── consulting.json          # 状態管理ファイル
    ├── hypotheses.md            # 仮説一覧
    ├── processed_data.md        # 加工済みデータ
    ├── validation_results.md    # 検証結果
    ├── strategies.md            # 戦略一覧
    └── report.md                # 最終レポート
```

### 3.2 状態管理（consulting.json）

cc-sddの`spec.json`と同様の構造で状態を管理：

```json
{
    "version": "1.0",
    "project_name": "sales_profit_improve",
    "csv_paths": [
        "sample_financial_data.csv",
        "hr_data.csv"
    ],
    "analysis_focus": "売上向上と利益率改善",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
    "status": "hypothesis_pending_approval",
    "current_step": "hypothesis",
    "steps": {
        "hypothesis": {
            "status": "completed",
            "approved": false,
            "completed_at": "2024-01-01T00:00:00",
            "output_file": "hypotheses.md",
            "feedback": [
                {
                    "reason": "信頼度が低い仮説を除外したい",
                    "timestamp": "2024-01-02T09:30:00"
                }
            ]
        },
        "process_data": {
            "status": "pending",
            "approved": null,
            "completed_at": null,
            "output_file": null,
            "feedback": []
        },
        "validate": {
            "status": "pending",
            "approved": null,
            "completed_at": null,
            "output_file": null,
            "feedback": []
        },
        "strategy": {
            "status": "pending",
            "approved": null,
            "completed_at": null,
            "output_file": null,
            "feedback": []
        },
        "report": {
            "status": "pending",
            "approved": null,
            "completed_at": null,
            "output_file": null,
            "feedback": []
        }
    },
    "retry_count": 0,
    "max_retry": 3
}
```

**注意**: 
- `project_name`は`analysis_focus`からAIで生成された英小文字のみの`単語_単語`形式（数字なし、最大24文字）
- `csv_paths`は複数のCSVファイルパスのリスト（後方互換性のため`csv_path`もサポート）
- `feedback`には否決時に入力された理由が時系列で蓄積され、再実行時のプロンプトに組み込まれる

**状態の種類**:
- `pending`: 未実行
- `in_progress`: 実行中
- `completed`: 完了（承認待ち）
- `approved`: 承認済み
- `rejected`: 否決済み

### 3.3 プロンプト管理
- **形式**: Python辞書
- **構造**:
  ```python
  CONSULTING_PROMPTS = {
      "hypothesis_generator": "...",
      "data_processor": "...",
      "hypothesis_validator": "...",
      "strategy_planner": "...",
      "report_generator": "..."
  }
  ```
- フィードバックの要素 (`steps.<step>.feedback`) はそれぞれのプロンプトに動的に追記され、否決理由を踏まえた再提案が可能になる。

### 3.4 成果物管理（Markdown形式）

全ての成果物をMarkdownファイルで保存：

- **hypotheses.md**: 仮説一覧（JSON埋め込み可）
- **processed_data.md**: 加工済みデータの説明とデータ概要
- **validation_results.md**: 検証結果の詳細
- **strategies.md**: 戦略一覧と詳細
- **report.md**: 最終レポート

### 3.5 スラッシュコマンド実装パターン

`commands.py`の`handle_command`関数に統合：

```python
# commands.py に追加
if cmd.startswith("consulting:"):
    from .consulting_commands import handle_consulting_command
    return handle_consulting_command(cmd, assistant_id)
```

### 3.6 ツール実装パターン
`csv_tool.py`と同様のパターン:
- `@tool`デコレータでツール定義
- 内部で一時的なAgentインスタンスを作成
- `_get_model()`でモデルを取得
- `_create_temp_agent()`でエージェントを作成

## 4. Human in the Loop実装

### 4.1 承認フロー

各ステップで承認が必要な場合のフロー：

1. **仮説生成後**: `/consulting:hypothesis`実行 → Markdownファイル生成 → 承認待ち状態
   - ユーザーが内容を確認
   - `/consulting:approve <project_name>`で承認 → 次のステップへ
   - `/consulting:reject <project_name>`で否決 → 理由入力 → 仮説を再生成

2. **仮説検証後**: `/consulting:validate`実行 → Markdownファイル生成 → 承認待ち状態
   - ユーザーが検証結果を確認
   - `/consulting:approve <project_name>`で承認 → 戦略立案へ
   - `/consulting:reject <project_name>`で否決 → 理由入力 → 仮説生成に戻る（否決理由は仮説/データ加工ステップに共有）

3. **戦略立案後**: `/consulting:strategy`実行 → Markdownファイル生成 → 承認待ち状態
   - ユーザーが戦略を確認
   - `/consulting:approve <project_name>`で承認 → レポート生成へ

4. **レポート生成後**: `/consulting:report`実行 → Markdownファイル生成 → 承認待ち状態
   - ユーザーがレポートを確認
   - `/consulting:approve <project_name>`で承認 → 完了
   - `/consulting:reject <project_name>`で否決 → 理由入力 → 戦略ステップに戻り、レポートの再作成を求められる（否決理由は戦略ステップにも共有）

- 否決時の理由は`feedback`として永続化され、次回のエージェント実行時にプロンプトへ自動的に埋め込まれる。これにより、人からのレビュー結果を踏まえた再提案が実現できる。

### 4.2 承認UI

承認が必要な場合の表示例：

```
[bold yellow]承認が必要です[/bold yellow]

現在のステップ: 仮説生成
ファイル: .consulting/financial_analysis_2024/hypotheses.md

承認する場合は: /consulting:approve financial_analysis_2024
否決する場合は: /consulting:reject financial_analysis_2024
（否決時はCLIが理由入力を求め、その内容をfeedbackに保存）
```

### 4.3 状態遷移

```
init → hypothesis (pending)
  ↓
hypothesis → hypothesis (completed) → [承認] → hypothesis (approved)
  ↓
process_data → process_data (completed)
  ↓
validate → validate (completed) → [承認] → validate (approved)
                                    [否決] → hypothesis (pending) [リトライ]
  ↓
strategy → strategy (completed) → [承認] → strategy (approved)
  ↓
report → report (completed) → [承認] → report (approved) → 完了
```

## 5. エラーハンドリング

### 5.1 各エージェントでのエラー処理
- CSV読み込みエラー
- LLM呼び出しエラー
- データ処理エラー
- JSON解析エラー
- 状態ファイルの読み書きエラー

### 5.2 フォールバック
- エージェントが失敗した場合の代替処理
- 部分的な結果でもMarkdownファイルを生成
- エラー情報をconsulting.jsonに記録

## 6. 実装イメージ

### 6.1 状態管理モジュール (`consulting_state.py`)

```python
"""経営コンサルエージェント用の状態管理モジュール."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

CONSULTING_DIR = Path(".consulting")

def get_project_dir(project_name: str) -> Path:
    """プロジェクトディレクトリを取得または作成。"""
    project_dir = CONSULTING_DIR / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir

def load_state(project_name: str) -> dict[str, Any]:
    """consulting.jsonを読み込む。"""
    project_dir = get_project_dir(project_name)
    state_file = project_dir / "consulting.json"
    
    if state_file.exists():
        state = json.loads(state_file.read_text())
        for step in ["hypothesis", "process_data", "validate", "strategy", "report"]:
            state["steps"].setdefault(step, {}).setdefault("feedback", [])
        return state
    
    # 初期状態を作成
    now = datetime.now().isoformat()
    return {
        "version": "1.0",
        "project_name": project_name,
        "csv_paths": [],
        "analysis_focus": "",
        "created_at": now,
        "updated_at": now,
        "status": "pending",
        "current_step": None,
        "steps": {
            step: {
                "status": "pending",
                "approved": None,
                "completed_at": None,
                "output_file": None,
                "feedback": [],
            }
            for step in ["hypothesis", "process_data", "validate", "strategy", "report"]
        },
        "retry_count": 0,
        "max_retry": 3,
    }

def save_state(project_name: str, state: dict[str, Any]) -> None:
    """consulting.jsonを保存。"""
    project_dir = get_project_dir(project_name)
    state_file = project_dir / "consulting.json"
    state["updated_at"] = datetime.now().isoformat()
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def update_step_status(
    project_name: str,
    step: str,
    status: str,
    output_file: str | None = None,
) -> None:
    """ステップの状態を更新。"""
    state = load_state(project_name)
    state["steps"][step]["status"] = status
    state["current_step"] = step
    state["status"] = f"{step}_{status}"
    
    if output_file:
        state["steps"][step]["output_file"] = output_file
    
    if status == "completed":
        state["steps"][step]["completed_at"] = datetime.now().isoformat()
    
    save_state(project_name, state)

def approve_step(project_name: str, step: str) -> None:
    """ステップを承認。"""
    state = load_state(project_name)
    state["steps"][step]["approved"] = True
    state["steps"][step]["status"] = "approved"
    save_state(project_name, state)

def add_feedback(project_name: str, step: str, reason: str) -> None:
    """ステップにフィードバックを追加。"""
    state = load_state(project_name)
    entry = {"reason": reason, "timestamp": datetime.now().isoformat()}
    state["steps"][step].setdefault("feedback", []).append(entry)
    save_state(project_name, state)

def reject_step(project_name: str, step: str, reason: str | None = None) -> None:
    """ステップを否決。否決理由があれば記録。"""
    state = load_state(project_name)
    if reason:
        entry = {"reason": reason, "timestamp": datetime.now().isoformat()}
        state["steps"][step].setdefault("feedback", []).append(entry)
    state["steps"][step]["approved"] = False
    state["steps"][step]["status"] = "rejected"
    state["status"] = f"{step}_rejected"
    save_state(project_name, state)
```
- `reject_step`は理由付きで呼び出され、`add_feedback`と合わせてHuman in the Loopの指摘内容を永続化する。
- `feedback`は仮説・加工・検証・戦略・レポート各ステップの再実行時に参照される。

### 6.2 スラッシュコマンドハンドラー (`consulting_commands.py`)

主要なコマンドの実装イメージ：

```python
"""経営コンサルエージェント用のスラッシュコマンドハンドラー."""

from __future__ import annotations

import re
from pathlib import Path

from .config import COLORS, console
from .consulting_state import (
    load_state,
    save_state,
    update_step_status,
    approve_step,
    reject_step,
    get_project_dir,
)
from .consulting_agents import (
    generate_hypotheses,
    process_data_for_validation,
    validate_hypotheses,
    plan_strategies,
    generate_consulting_report,
)

def handle_consulting_command(command: str, assistant_id: str = "agent") -> bool:
    """経営コンサルコマンドを処理。"""
    cmd = command.lower().strip()
    
    # /consulting:init <analysis_focus> <csv_path1> [csv_path2] ...
    if cmd.startswith("consulting:init"):
        # コマンドを解析（analysis_focusと複数のCSVパスを取得）
        parts = cmd.split()
        if len(parts) < 3:
            console.print("[red]使用方法: /consulting:init <analysis_focus> <csv_path1> [csv_path2] ...[/red]")
            console.print("[dim]例: /consulting:init \"売上向上と利益率改善\" sample_financial_data.csv[/dim]")
            console.print("[dim]例（複数ファイル）: /consulting:init \"売上と人事分析\" sales.csv hr.csv[/dim]")
            return True
        
        # analysis_focusは最初の引数（引用符で囲まれている可能性がある）
        analysis_focus = parts[1]
        # 引用符を除去
        if analysis_focus.startswith('"') and analysis_focus.endswith('"'):
            analysis_focus = analysis_focus[1:-1]
        elif analysis_focus.startswith("'") and analysis_focus.endswith("'"):
            analysis_focus = analysis_focus[1:-1]
        
        # CSVファイルパスは残りの引数
        csv_paths = parts[2:]
        
        # CSVファイルの存在確認とフォルダ展開
        resolved_csv_paths = []
        for csv_path in csv_paths:
            path_obj = Path(csv_path)
            if not path_obj.is_absolute():
                path_obj = Path.cwd() / path_obj
            
            if not path_obj.exists():
                console.print(f"[red]エラー: パスが見つかりません: {csv_path}[/red]")
                return True
            
            # フォルダの場合は、その中のすべてのCSVファイルを再帰的に検索
            if path_obj.is_dir():
                csv_files = list(path_obj.rglob("*.csv"))
                if not csv_files:
                    console.print(f"[yellow]警告: フォルダ内にCSVファイルが見つかりません: {csv_path}[/yellow]")
                    return True
                resolved_csv_paths.extend([str(f) for f in csv_files])
            else:
                # ファイルの場合はそのまま追加
                resolved_csv_paths.append(str(path_obj))
        
        if not resolved_csv_paths:
            console.print("[red]エラー: CSVファイルが1つも見つかりませんでした[/red]")
            return True
        
        # analysis_focusからproject_nameを生成（AIを使用）
        from .consulting_agents import generate_project_name
        import asyncio
        project_name = asyncio.run(generate_project_name(analysis_focus))
        
        # 状態を初期化
        state = load_state(project_name)
        state["csv_paths"] = resolved_csv_paths
        state["analysis_focus"] = analysis_focus
        state["status"] = "initialized"
        save_state(project_name, state)
        
        console.print(f"[green]✓ 分析プロジェクト '{project_name}' を初期化しました[/green]")
        console.print(f"  分析の焦点: {analysis_focus}")
        console.print(f"  CSVファイル数: {len(resolved_csv_paths)}")
        
        # ファイルをグループ化して表示（同じディレクトリのものはまとめて表示）
        from collections import defaultdict
        by_dir = defaultdict(list)
        for csv_path in resolved_csv_paths:
            path_obj = Path(csv_path)
            by_dir[str(path_obj.parent)].append(path_obj.name)
        
        for dir_path, files in sorted(by_dir.items()):
            if len(by_dir) > 1:
                console.print(f"  [{dir_path}]")
            for file_name in sorted(files):
                console.print(f"    - {file_name}")
        
        console.print(f"  作業ディレクトリ: .consulting/{project_name}/")
        console.print()
        return True
    
    # /consulting:hypothesis
    elif cmd == "consulting:hypothesis":
        project_name = _get_current_project()
        if not project_name:
            console.print("[red]エラー: プロジェクトが初期化されていません[/red]")
            return True
        
        state = load_state(project_name)
        
        # 仮説を生成
        console.print("[dim]仮説を生成中...[/dim]")
        state = generate_hypotheses(state, project_name)
        
        # Markdownファイルに保存
        project_dir = get_project_dir(project_name)
        hypotheses_file = project_dir / "hypotheses.md"
        hypotheses_file.write_text(state.get("hypotheses_markdown", ""))
        
        # 状態を更新
        update_step_status(project_name, "hypothesis", "completed", "hypotheses.md")
        
        console.print(f"[green]✓ 仮説を生成しました[/green]")
        console.print(f"  ファイル: {hypotheses_file}")
        console.print()
        console.print("[yellow]承認が必要です[/yellow]")
        console.print("  承認: /consulting:approve")
        console.print("  否決: /consulting:reject")
        console.print()
        return True
    
    # /consulting:approve
    elif cmd == "consulting:approve":
        project_name = _get_current_project()
        if not project_name:
            console.print("[red]エラー: プロジェクトが初期化されていません[/red]")
            return True
        
        state = load_state(project_name)
        current_step = state["current_step"]
        
        if not current_step:
            console.print("[red]エラー: 承認するステップがありません[/red]")
            return True
        
        if state["steps"][current_step]["status"] != "completed":
            console.print(f"[red]エラー: ステップ '{current_step}' は完了していません[/red]")
            return True
        
        approve_step(project_name, current_step)
        console.print(f"[green]✓ ステップ '{current_step}' を承認しました[/green]")
        
        # 次のステップを案内
        _show_next_steps(state, current_step)
        return True
    
    # /consulting:reject
    elif cmd == "consulting:reject":
        project_name = _get_current_project()
        if not project_name:
            console.print("[red]エラー: プロジェクトが初期化されていません[/red]")
            return True
        
        state = load_state(project_name)
        current_step = state["current_step"]
        
        if not current_step:
            console.print("[red]エラー: 否決するステップがありません[/red]")
            return True
        
        reject_step(project_name, current_step)
        console.print(f"[yellow]ステップ '{current_step}' を否決しました[/yellow]")
        
        # 仮説検証を否決した場合は仮説生成に戻る
        if current_step == "validate":
            console.print("[dim]仮説生成に戻ります。[/consulting:hypothesis を実行してください[/dim]")
            # 仮説ステップをリセット
            state["steps"]["hypothesis"]["status"] = "pending"
            state["steps"]["hypothesis"]["approved"] = None
            state["retry_count"] += 1
            save_state(project_name, state)
        return True
    
    # /consulting:status
    elif cmd == "consulting:status":
        project_name = _get_current_project()
        if not project_name:
            console.print("[red]エラー: プロジェクトが初期化されていません[/red]")
            return True
        
        state = load_state(project_name)
        
        console.print(f"[bold]プロジェクト: {project_name}[/bold]")
        console.print(f"  状態: {state['status']}")
        console.print(f"  現在のステップ: {state['current_step'] or 'なし'}")
        console.print()
        console.print("[bold]ステップ状況:[/bold]")
        for step_name, step_info in state["steps"].items():
            status = step_info["status"]
            approved = step_info["approved"]
            if approved is True:
                status_display = f"[green]{status} (承認済み)[/green]"
            elif approved is False:
                status_display = f"[red]{status} (否決済み)[/red]"
            else:
                status_display = status
            
            console.print(f"  {step_name}: {status_display}")
        console.print()
        return True
    
    else:
        console.print(f"[yellow]未知のコマンド: /{cmd}[/yellow]")
        console.print("[dim]利用可能なコマンド: /consulting:init, /consulting:hypothesis, /consulting:process-data, /consulting:validate, /consulting:strategy, /consulting:report, /consulting:approve, /consulting:reject, /consulting:status[/dim]")
        return True

def _get_current_project() -> str | None:
    """現在のプロジェクト名を取得（簡易実装）。"""
    if not CONSULTING_DIR.exists():
        return None
    
    # 最新のプロジェクトを取得
    projects = [d for d in CONSULTING_DIR.iterdir() if d.is_dir()]
    if not projects:
        return None
    
    # 最新の更新日時のプロジェクトを返す
    latest_project = max(projects, key=lambda p: (p / "consulting.json").stat().st_mtime if (p / "consulting.json").exists() else 0)
    return latest_project.name

def _show_next_steps(state: dict, current_step: str) -> None:
    """次のステップを案内。"""
    if current_step == "hypothesis":
        console.print("[dim]次のステップ: /consulting:process-data[/dim]")
    elif current_step == "process_data":
        console.print("[dim]次のステップ: /consulting:validate[/dim]")
    elif current_step == "validate":
        console.print("[dim]次のステップ: /consulting:strategy[/dim]")
    elif current_step == "strategy":
        console.print("[dim]次のステップ: /consulting:report[/dim]")
    elif current_step == "report":
        console.print("[green]✓ 分析が完了しました！[/green]")
```
- 実装ではコマンド名のみ小文字化し、`project_name`などの引数は元のケースを維持する。
- `_run_async`ヘルパーを通じて非同期エージェント呼び出しを行い、イベントループ終了時に未処理タスクを確実に収束させる。
- `/consulting:reject <project_name>`はCLI上で理由入力を求め、`feedback`へ記録した上で該当ステップや関連ステップを`pending`状態に戻す。
  - 検証否決時は仮説生成から、戦略否決時は検証から、レポート否決時は戦略から再実行する。
- `/consulting:status [project_name]`は現在の状態だけでなく、次に実行すべきコマンド（例: `/consulting:hypothesis <project_name>`）を案内する。

### 6.3 サブエージェント実装例 (`consulting_agents.py`)

各エージェントは統合データ構造（state）を受け取り、更新して返す：

```python
"""経営コンサルエージェントのサブエージェント実装."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from strands import Agent

from .config import create_model
from .consulting_prompts import CONSULTING_PROMPTS
from .consulting_state import load_state, get_project_dir

# モデルキャッシュ
_cached_model: Any = None

def _get_model():
    """モデルインスタンスを取得（キャッシュを使用）。"""
    global _cached_model
    if _cached_model is None:
        _cached_model = create_model()
    return _cached_model

def _create_consulting_agent(agent_type: str, model: Any) -> Agent:
    """指定されたタイプのコンサルティングエージェントを作成。"""
    prompt = CONSULTING_PROMPTS.get(agent_type, "")
    return Agent(
        model=model,
        system_prompt=prompt,
        tools=[],
    )

async def _invoke_agent_async(agent: Agent, prompt: str) -> str:
    """エージェントを非同期で呼び出し、結果を文字列で返す。"""
    if hasattr(agent, "invoke_async"):
        response = await agent.invoke_async(prompt)
    else:
        import asyncio
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: agent.invoke(prompt))
    
    # レスポンスからテキストを抽出
    if hasattr(response, "output_text"):
        return str(response.output_text)
    elif hasattr(response, "content"):
        return str(response.content)
    elif isinstance(response, dict):
        return str(response.get("output_text", response.get("content", response)))
    return str(response)

def _extract_json_from_response(response_text: str) -> dict:
    """レスポンステキストからJSONを抽出。"""
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        if end != -1:
            response_text = response_text[start:end].strip()
        else:
            response_text = response_text[start:].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        if end != -1:
            response_text = response_text[start:end].strip()
        else:
            response_text = response_text[start:].strip()
    
    return json.loads(response_text)

async def generate_project_name(analysis_focus: str) -> str:
    """analysis_focusから英数字20文字程度のユニークなproject_nameを生成する。"""
    model = _get_model()
    agent = Agent(
        model=model,
        system_prompt="あなたはプロジェクト名生成の専門家です。分析の焦点を表す、英数字のみで構成された20文字程度のユニークなプロジェクト名を生成してください。",
        tools=[],
    )
    prompt = f"""
以下の分析の焦点を表す、英数字のみで構成された20文字程度のユニークなプロジェクト名を生成してください。

分析の焦点: {analysis_focus}

要件:
- 英数字のみ（a-z, A-Z, 0-9, ハイフン、アンダースコアのみ）
- 20文字程度
- 分析の焦点を表す内容
- ユニークで識別しやすい

プロジェクト名のみを返してください。説明は不要です。
"""
    response_text = await _invoke_agent_async(agent, prompt)
    # レスポンスからプロジェクト名を抽出（改行や空白を除去）
    project_name = "".join(response_text.split()).strip()
    # 英数字、ハイフン、アンダースコア以外の文字を除去
    import re
    project_name = re.sub(r"[^a-zA-Z0-9_-]", "", project_name)
    # 20文字に制限
    if len(project_name) > 20:
        project_name = project_name[:20]
    # 空の場合はデフォルト値を返す
    if not project_name:
        project_name = "consulting_project"
    return project_name

async def generate_hypotheses(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """CSVデータから経営課題の仮説を生成し、統合データ構造を更新する。"""
    try:
        csv_paths = state.get("csv_paths", [])
        if not csv_paths:
            # 後方互換性のため、csv_pathもチェック
            csv_path = state.get("csv_path", "")
            if csv_path:
                csv_paths = [csv_path]
            else:
                raise ValueError("CSVファイルが指定されていません。")
        
        # 複数のCSVファイルを読み込む
        dfs = []
        data_summaries = []
        
        for csv_path in csv_paths:
            csv_file = Path(csv_path)
            if not csv_file.is_absolute():
                csv_file = Path.cwd() / csv_file
            
            df = _read_csv_with_encoding(csv_file)
            dfs.append(df)
            
            # 各ファイルのデータ概要を生成
            file_summary = f"""
## ファイル: {csv_file.name}
- 総行数: {len(df)}
- カラム: {', '.join(df.columns.tolist())}
- サンプルデータ（最初の5行）:
{df.head(5).to_string()}
"""
            data_summaries.append(file_summary)
        
        # データ概要を統合
        data_summary = "\n".join(data_summaries)
        
        # 複数ファイルの場合は統合情報も追加
        if len(dfs) > 1:
            total_rows = sum(len(df) for df in dfs)
            all_columns = set()
            for df in dfs:
                all_columns.update(df.columns.tolist())
            data_summary += f"""
## 統合データ概要
- ファイル数: {len(dfs)}
- 総行数: {total_rows}
- 全カラム数: {len(all_columns)}
- カラム一覧: {', '.join(sorted(all_columns))}
"""
        
        if state.get("analysis_focus"):
            data_summary += f"\n## 分析の焦点\n{state['analysis_focus']}"
        
        # エージェント作成
        model = _get_model()
        agent = _create_consulting_agent("hypothesis_generator", model)
        
        # プロンプト構築
        prompt = f"""
{data_summary}

上記のデータを分析し、経営課題の仮説を生成してください。
Markdown形式で出力し、各仮説にはID、タイトル、説明、優先度を含めてください。
"""
        
        # エージェント呼び出し
        response_text = await _invoke_agent_async(agent, prompt)
        
        # Markdownを保存
        state["hypotheses_markdown"] = response_text
        
        return state
        
    except Exception as e:
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"仮説生成に失敗しました: {e}")
        return state

# 他のエージェント関数も同様のパターンで実装
```

### 6.4 commands.pyへの統合

```python
# commands.py の handle_command 関数に追加

if cmd.startswith("consulting:"):
    from .consulting_commands import handle_consulting_command
    return handle_consulting_command(cmd, assistant_id)
```

### 6.5 使用例

```
# 1. 分析を初期化（単一ファイル）
/consulting:init "売上向上と利益率改善" sample_financial_data.csv

# 1. 分析を初期化（複数ファイル）
/consulting:init "売上と人事分析" sales.csv hr.csv employee.csv

# 1. 分析を初期化（フォルダ指定）
/consulting:init "売上分析" ./data/

# 1. 分析を初期化（混在：ファイルとフォルダ）
/consulting:init "総合分析" sales.csv ./hr_data/ financial.csv

# 2. 仮説を生成
/consulting:hypothesis

# 3. 仮説を確認して承認
/consulting:approve

# 4. データを整理・加工
/consulting:process-data

# 5. 仮説を検証
/consulting:validate

# 6. 検証結果を確認して承認
/consulting:approve

# 7. 戦略を立案
/consulting:strategy

# 8. 戦略を確認して承認
/consulting:approve

# 9. レポートを生成
/consulting:report

# 10. レポートを確認して承認
/consulting:approve

# 状態確認
/consulting:status
```

## 7. 実装順序

1. **状態管理モジュール** (`consulting_state.py`)
   - `load_state`, `save_state`, `update_step_status`など

2. **プロンプト管理モジュール** (`consulting_prompts.py`)
   - 各エージェント用のプロンプト定義

3. **サブエージェントの実装** (`consulting_agents.py`)
   - `generate_hypotheses`: 仮説生成とMarkdown出力
   - `process_data_for_validation`: データ加工とMarkdown出力
   - `validate_hypotheses`: 仮説検証とMarkdown出力
   - `plan_strategies`: 戦略立案とMarkdown出力
   - `generate_consulting_report`: レポート生成とMarkdown出力

4. **スラッシュコマンドハンドラー** (`consulting_commands.py`)
   - 各コマンドの処理ロジック
   - Human in the Loopの実装

5. **commands.pyへの統合**
   - `handle_command`関数に`consulting:`コマンドの処理を追加

6. **エラーハンドリングの強化**
   - 各ステップでのエラー処理
   - リトライロジック

7. **テストとデバッグ**
   - 各コマンドの動作確認
   - 状態遷移の確認

8. **ドキュメント整備**
   - コマンドリファレンス
   - 使用例

