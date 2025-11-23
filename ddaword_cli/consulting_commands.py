"""経営コンサルエージェント用のスラッシュコマンドハンドラー."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from pathlib import Path

from .config import COLORS, console
from .consulting_state import (
    CONSULTING_DIR,
    get_current_project,
    get_project_dir,
    load_state,
    save_state,
    update_step_status,
    approve_step,
    reject_step,
    add_feedback,
    get_pending_process_data_tasks,
)
from .consulting_agents import (
    generate_hypotheses,
    process_data_for_validation,
    validate_hypotheses,
    plan_strategies,
    generate_consulting_report,
)





async def handle_consulting_command(command: str, assistant_id: str = "agent") -> bool:
    """経営コンサルコマンドを処理。
    
    Args:
        command: コマンド文字列（"consulting:init ..."など）
        assistant_id: アシスタントID（未使用だが互換性のため保持）
        
    Returns:
        コマンドが処理された場合はTrue
    """
    # コマンド名部分だけ小文字に変換（project_nameは大文字小文字を保持）
    original_parts = command.strip().split()
    if not original_parts:
        return False
    
    cmd_base = original_parts[0].lower()
    cmd = cmd_base  # コマンド名の判定用（小文字）
    
    # /consulting:init <analysis_focus> <csv_path1> [csv_path2] ...
    if cmd.startswith("consulting:init"):
        # コマンドを解析（analysis_focusと複数のCSVパスを取得）
        # 元の文字列から取得（大文字小文字を保持）
        parts = original_parts
        if len(parts) < 3:
            console.print("[red]使用方法: /consulting:init <analysis_focus> <csv_path1> [csv_path2] ...[/red]")
            console.print("[dim]例: /consulting:init \"売上向上と利益率改善\" sample_financial_data.csv[/dim]")
            console.print("[dim]例（複数ファイル）: /consulting:init \"売上と人事分析\" sales.csv hr.csv[/dim]")
            console.print("[dim]例（フォルダ指定）: /consulting:init \"売上分析\" ./data/[/dim]")
            console.print("[dim]例（混在）: /consulting:init \"分析\" sales.csv ./data/ hr.csv[/dim]")
            console.print()
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
        
        if not csv_paths:
            console.print("[red]エラー: CSVファイルが指定されていません[/red]")
            console.print()
            return True
        
        # CSVファイルの存在確認とフォルダ展開
        resolved_csv_paths = []
        for csv_path in csv_paths:
            path_obj = Path(csv_path)
            if not path_obj.is_absolute():
                path_obj = Path.cwd() / path_obj
            
            if not path_obj.exists():
                console.print(f"[red]エラー: パスが見つかりません: {csv_path}[/red]")
                console.print()
                return True
            
            # フォルダの場合は、その中のすべてのCSVファイルを検索
            if path_obj.is_dir():
                csv_files = list(path_obj.rglob("*.csv"))
                if not csv_files:
                    console.print(f"[yellow]警告: フォルダ内にCSVファイルが見つかりません: {csv_path}[/yellow]")
                    console.print()
                    return True
                resolved_csv_paths.extend([str(f) for f in csv_files])
            else:
                # ファイルの場合はそのまま追加
                resolved_csv_paths.append(str(path_obj))
        
        if not resolved_csv_paths:
            console.print("[red]エラー: CSVファイルが1つも見つかりませんでした[/red]")
            console.print()
            return True
        
        # analysis_focusからproject_nameを生成（AIを使用）
        console.print("[dim]プロジェクト名を生成中...[/dim]")
        from .consulting_agents import generate_project_name
        
        try:
            project_name = await generate_project_name(analysis_focus)
        except Exception as e:
            console.print(f"[yellow]警告: プロジェクト名生成に失敗しました。デフォルト名を使用します: {e}[/yellow]")
            # フォールバック: analysis_focusから簡易的に生成
            project_name = re.sub(r"[^a-zA-Z0-9_-]", "_", analysis_focus)[:20]
            if not project_name:
                project_name = "consulting_project"
        
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
        console.print(f"[dim]次のステップ: /consulting:hypothesis {project_name}[/dim]")
        console.print()
        return True
    
    # /consulting:hypothesis <project_name>
    elif cmd.startswith("consulting:hypothesis"):
        if len(original_parts) < 2:
            console.print("[red]エラー: プロジェクト名が指定されていません[/red]")
            console.print("[dim]使用方法: /consulting:hypothesis <project_name>[/dim]")
            console.print("[dim]例: /consulting:hypothesis sales_profit_improve[/dim]")
            console.print()
            return True
        
        project_name = original_parts[1]
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print("[dim]先に /consulting:init を実行してください[/dim]")
            console.print()
            return True
        
        state = load_state(project_name)
        
        # CSVファイルの確認
        csv_paths = state.get("csv_paths", [])
        if csv_paths:
            console.print(f"[dim]読み込むCSVファイル数: {len(csv_paths)}[/dim]")
            for i, csv_path in enumerate(csv_paths, 1):
                console.print(f"[dim]  {i}. {Path(csv_path).name}[/dim]")
        else:
            console.print("[yellow]警告: CSVファイルが指定されていません[/yellow]")
        
        # 仮説を生成
        console.print("[dim]仮説を生成中...[/dim]")
        
        try:
            state = await generate_hypotheses(state, project_name)
        except Exception as e:
            console.print(f"[red]エラー: 仮説生成中にエラーが発生しました: {e}[/red]")
            console.print()
            return True
        
        # エラーチェック
        if state.get("errors"):
            console.print(f"[red]エラー: {state['errors'][-1]}[/red]")
            console.print()
            return True
        
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
        console.print(f"  承認: /consulting:approve {project_name}")
        console.print(f"  否決: /consulting:reject {project_name}")
        console.print()
        return True
    
    # /consulting:process-data <project_name>
    elif cmd.startswith("consulting:process-data"):
        if len(original_parts) < 2:
            console.print("[red]エラー: プロジェクト名が指定されていません[/red]")
            console.print("[dim]使用方法: /consulting:process-data <project_name>[/dim]")
            console.print()
            return True
        
        project_name = original_parts[1]
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print()
            return True
        
        state = load_state(project_name)
        
        # 仮説が承認されているか確認
        if state["steps"]["hypothesis"]["status"] != "approved":
            console.print("[red]エラー: 仮説が承認されていません[/red]")
            console.print("[dim]先に /consulting:approve を実行してください[/dim]")
            console.print()
            return True
        
        # タスク状況を確認
        pending_tasks = get_pending_process_data_tasks(project_name)
        state = load_state(project_name)
        tasks = state["steps"]["process_data"].get("tasks", {})
        
        if tasks:
            console.print("[bold]タスク状況:[/bold]")
            for hypothesis_id in sorted(tasks.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0):
                task = tasks[hypothesis_id]
                status = task.get("status", "pending")
                if status == "completed":
                    console.print(f"  [green]✓ {hypothesis_id}: 完了[/green]")
                elif status == "in_progress":
                    console.print(f"  [yellow]→ {hypothesis_id}: 処理中[/yellow]")
                elif status == "failed":
                    error = task.get("error", "")
                    console.print(f"  [red]✗ {hypothesis_id}: 失敗[/red]")
                    if error:
                        console.print(f"    [dim]エラー: {error[:100]}[/dim]")
                else:
                    console.print(f"  [dim]○ {hypothesis_id}: 未実施[/dim]")
            console.print()
        
        if pending_tasks:
            console.print(f"[dim]未完了タスク数: {len(pending_tasks)}[/dim]")
            console.print(f"[dim]処理中のタスク: {', '.join(pending_tasks)}[/dim]")
            console.print()
        
        console.print("[dim]データを整理・加工中...[/dim]")
        
        try:
            state = await process_data_for_validation(state, project_name)
        except Exception as e:
            console.print(f"[red]エラー: データ加工中にエラーが発生しました: {e}[/red]")
            console.print()
            return True
        
        # エラーチェック（エラーがあっても成果物があれば保存を試みる）
        if state.get("errors"):
            console.print(f"[yellow]警告: 処理中に以下のエラーが発生しました:[/yellow]")
            for error in state["errors"]:
                console.print(f"[red]  - {error}[/red]")
            console.print()
            
            # 成果物がない場合はここで終了
            if not state.get("processed_data_markdown"):
                return True
            
            console.print("[yellow]一部の処理に失敗しましたが、生成されたデータを保存します。[/yellow]")
        
        # Markdownファイルに保存（統合ファイル）
        project_dir = get_project_dir(project_name)
        processed_data_file = project_dir / "processed_data.md"
        if state.get("processed_data_markdown"):
            processed_data_file.write_text(state.get("processed_data_markdown", ""))
        
        # タスク状況を再確認
        state = load_state(project_name)
        tasks = state["steps"]["process_data"].get("tasks", {})
        completed_count = sum(1 for t in tasks.values() if t.get("status") == "completed")
        total_count = len(tasks)
        
        if completed_count == total_count and total_count > 0:
            update_step_status(project_name, "process_data", "completed", "processed_data.md")
            console.print(f"[green]✓ すべてのタスクが完了しました[/green]")
            console.print(f"  完了タスク数: {completed_count}/{total_count}")
            console.print(f"  統合ファイル: {processed_data_file}")
            console.print()
            console.print(f"[dim]次のステップ: /consulting:validate {project_name}[/dim]")
            console.print()
        else:
            console.print(f"[yellow]部分完了: {completed_count}/{total_count} タスク完了[/yellow]")
            remaining = get_pending_process_data_tasks(project_name)
            if remaining:
                console.print(f"[dim]残りのタスク: {', '.join(remaining)}[/dim]")
                console.print(f"[dim]再実行: /consulting:process-data {project_name}[/dim]")
            console.print()
        
        return True
    
    # /consulting:validate <project_name>
    elif cmd.startswith("consulting:validate"):
        if len(original_parts) < 2:
            console.print("[red]エラー: プロジェクト名が指定されていません[/red]")
            console.print("[dim]使用方法: /consulting:validate <project_name>[/dim]")
            console.print()
            return True
        
        project_name = original_parts[1]
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print()
            return True
        
        state = load_state(project_name)
        
        # データ加工が完了しているか確認
        if state["steps"]["process_data"]["status"] != "completed":
            console.print("[red]エラー: データ加工が完了していません[/red]")
            console.print("[dim]先に /consulting:process-data を実行してください[/dim]")
            console.print()
            return True
        
        console.print("[dim]仮説を検証中...[/dim]")
        
        try:
            state = await validate_hypotheses(state, project_name)
        except Exception as e:
            console.print(f"[red]エラー: 仮説検証中にエラーが発生しました: {e}[/red]")
            console.print()
            return True
        
        # エラーチェック
        if state.get("errors"):
            console.print(f"[red]エラー: {state['errors'][-1]}[/red]")
            console.print()
            return True
        
        # Markdownファイルに保存
        project_dir = get_project_dir(project_name)
        validation_file = project_dir / "validation_results.md"
        validation_file.write_text(state.get("validation_results_markdown", ""))
        
        update_step_status(project_name, "validate", "completed", "validation_results.md")
        
        console.print(f"[green]✓ 仮説を検証しました[/green]")
        console.print(f"  ファイル: {validation_file}")
        console.print()
        console.print("[yellow]承認が必要です[/yellow]")
        console.print(f"  承認: /consulting:approve {project_name} ")
        console.print(f"  否決: /consulting:reject {project_name} ")
        console.print()
        return True
    
    # /consulting:strategy <project_name>
    elif cmd.startswith("consulting:strategy"):
        if len(original_parts) < 2:
            console.print("[red]エラー: プロジェクト名が指定されていません[/red]")
            console.print("[dim]使用方法: /consulting:strategy <project_name>[/dim]")
            console.print()
            return True
        
        project_name = original_parts[1]
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print()
            return True
        
        state = load_state(project_name)
        
        # 検証が承認されているか確認
        if state["steps"]["validate"]["status"] != "approved":
            console.print("[red]エラー: 検証結果が承認されていません[/red]")
            console.print("[dim]先に /consulting:approve を実行してください[/dim]")
            console.print()
            return True
        
        console.print("[dim]戦略を立案中...[/dim]")
        
        try:
            state = await plan_strategies(state, project_name)
        except Exception as e:
            console.print(f"[red]エラー: 戦略立案中にエラーが発生しました: {e}[/red]")
            console.print()
            return True
        
        # エラーチェック
        if state.get("errors"):
            console.print(f"[red]エラー: {state['errors'][-1]}[/red]")
            console.print()
            return True
        
        # Markdownファイルに保存
        project_dir = get_project_dir(project_name)
        strategies_file = project_dir / "strategies.md"
        strategies_file.write_text(state.get("strategies_markdown", ""))
        
        update_step_status(project_name, "strategy", "completed", "strategies.md")
        
        console.print(f"[green]✓ 戦略を立案しました[/green]")
        console.print(f"  ファイル: {strategies_file}")
        console.print()
        console.print("[yellow]承認が必要です[/yellow]")
        console.print(f"  承認: /consulting:approve {project_name}")
        console.print(f"  否決: /consulting:reject {project_name} ")
        console.print()
        return True
    
    # /consulting:report <project_name>
    elif cmd.startswith("consulting:report"):
        if len(original_parts) < 2:
            console.print("[red]エラー: プロジェクト名が指定されていません[/red]")
            console.print("[dim]使用方法: /consulting:report <project_name>[/dim]")
            console.print()
            return True
        
        project_name = original_parts[1]
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print()
            return True
        
        state = load_state(project_name)
        
        # 戦略が承認されているか確認
        if state["steps"]["strategy"]["status"] != "approved":
            console.print("[red]エラー: 戦略が承認されていません[/red]")
            console.print("[dim]先に /consulting:approve を実行してください[/dim]")
            console.print()
            return True
        
        console.print("[dim]レポートを生成中...[/dim]")
        
        try:
            state = await generate_consulting_report(state, project_name)
        except Exception as e:
            console.print(f"[red]エラー: レポート生成中にエラーが発生しました: {e}[/red]")
            console.print()
            return True
        
        # エラーチェック
        if state.get("errors"):
            console.print(f"[yellow]警告: 処理中に以下のエラーが発生しました:[/yellow]")
            for error in state["errors"]:
                console.print(f"[red]  - {error}[/red]")
            console.print()
            
            # 成果物がない場合はここで終了
            if not state.get("report_markdown"):
                return True
                
            console.print("[yellow]エラーが発生しましたが、生成されたレポートを保存します。[/yellow]")
        
        # Markdownファイルに保存
        project_dir = get_project_dir(project_name)
        report_file = project_dir / "report.md"
        report_file.write_text(state.get("report_markdown", ""))
        
        update_step_status(project_name, "report", "completed", "report.md")
        
        console.print(f"[green]✓ レポートを生成しました[/green]")
        console.print(f"  ファイル: {report_file}")
        console.print()
        console.print("[yellow]承認が必要です[/yellow]")
        console.print(f"  承認: /consulting:approve {project_name}")
        console.print(f"  否決: /consulting:reject {project_name} ")
        console.print()
        return True
    
    # /consulting:approve <project_name>
    elif cmd.startswith("consulting:approve"):
        if len(original_parts) < 2:
            console.print("[red]エラー: プロジェクト名が指定されていません[/red]")
            console.print("[dim]使用方法: /consulting:approve <project_name>[/dim]")
            console.print()
            return True
        
        project_name = original_parts[1]
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print()
            return True
        
        state = load_state(project_name)
        current_step = state["current_step"]
        
        if not current_step:
            console.print("[red]エラー: 承認するステップがありません[/red]")
            console.print()
            return True
        
        if state["steps"][current_step]["status"] != "completed":
            console.print(f"[red]エラー: ステップ '{current_step}' は完了していません[/red]")
            console.print()
            return True
        
        approve_step(project_name, current_step)
        console.print(f"[green]✓ ステップ '{current_step}' を承認しました[/green]")
        console.print()
        
        # 次のステップを案内
        _show_next_steps(state, current_step, project_name)
        return True
    
    # /consulting:reject <project_name>
    elif cmd.startswith("consulting:reject"):
        if len(original_parts) < 2:
            console.print("[red]エラー: プロジェクト名が指定されていません[/red]")
            console.print("[dim]使用方法: /consulting:reject <project_name>[/dim]")
            console.print()
            return True
        
        project_name = original_parts[1]
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print()
            return True
        
        state = load_state(project_name)
        current_step = state["current_step"]
        
        if not current_step:
            console.print("[red]エラー: 否決するステップがありません[/red]")
            console.print()
            return True

        # 否決理由を入力
        console.print("[yellow]ステップを否決する理由を入力してください。[/yellow]")
        console.print("[dim]Enterで確定します（空欄は許可されません）。[/dim]")
        while True:
            try:
                reason = input("Review reason: ").strip()
            except EOFError:
                reason = ""
            if reason:
                break
            console.print("[red]否決理由は必須です。[/red]")

        reject_step(project_name, current_step, reason)
        console.print(f"[yellow]ステップ '{current_step}' を否決しました[/yellow]")
        console.print(f"[dim]否決理由: {reason}[/dim]")
        console.print()

        # 最新の状態を再読み込み
        state = load_state(project_name)

        # 否決内容に応じてステップを巻き戻す
        if current_step == "validate":
            console.print(f"[dim]仮説生成に戻ります。[/consulting:hypothesis {project_name} を実行してください[/dim]")
            console.print()
            # 仮説およびデータ加工ステップにもフィードバックを共有
            add_feedback(project_name, "hypothesis", f"検証否決理由: {reason}")
            add_feedback(project_name, "process_data", f"検証否決理由: {reason}")
            state = load_state(project_name)
            # 仮説ステップをリセット
            state["steps"]["hypothesis"]["status"] = "pending"
            state["steps"]["hypothesis"]["approved"] = None
            # 検証ステップを再実行待ちに戻す
            state["steps"]["validate"]["status"] = "pending"
            state["steps"]["validate"]["approved"] = None
            # 現在ステップを仮説に戻す
            state["current_step"] = "hypothesis"
            state["status"] = "hypothesis_pending"
            state["retry_count"] = state.get("retry_count", 0) + 1
            save_state(project_name, state)
        elif current_step == "hypothesis":
            console.print(f"[dim]仮説を再生成するには /consulting:hypothesis {project_name} を実行してください[/dim]")
        elif current_step == "strategy":
            console.print(f"[dim]仮説検証の見直しから行います。/consulting:validate {project_name} を実行してください[/dim]")
            add_feedback(project_name, "validate", f"戦略否決理由: {reason}")
            state = load_state(project_name)
            state["steps"]["strategy"]["status"] = "pending"
            state["steps"]["strategy"]["approved"] = None
            state["steps"]["report"]["status"] = "pending"
            state["steps"]["report"]["approved"] = None
            state["current_step"] = "validate"
            state["status"] = "validate_pending"
            save_state(project_name, state)
        elif current_step == "report":
            console.print(f"[dim]戦略の再検討からやり直してください。/consulting:strategy {project_name} を実行してください[/dim]")
            add_feedback(project_name, "strategy", f"レポート否決理由: {reason}")
            state = load_state(project_name)
            state["steps"]["report"]["status"] = "pending"
            state["steps"]["report"]["approved"] = None
            state["current_step"] = "strategy"
            state["status"] = "strategy_pending"
            save_state(project_name, state)

        console.print()

        next_step = state.get("current_step")
        if next_step:
            console.print("[bold]次のステップ:[/bold]")
            _show_next_steps(state, next_step, project_name)
        else:
            step_order = ["hypothesis", "process_data", "validate", "strategy", "report"]
            pending_step = None
            for name in step_order:
                info = state["steps"].get(name, {})
                if info.get("status") in {"pending", "in_progress"}:
                    pending_step = name
                    break
            if pending_step:
                console.print("[bold]推奨コマンド:[/bold]")
                if pending_step == "hypothesis":
                    console.print(f"  /consulting:hypothesis {project_name}")
                elif pending_step == "process_data":
                    console.print(f"  /consulting:process-data {project_name}")
                elif pending_step == "validate":
                    console.print(f"  /consulting:validate {project_name}")
                elif pending_step == "strategy":
                    console.print(f"  /consulting:strategy {project_name}")
                elif pending_step == "report":
                    console.print(f"  /consulting:report {project_name}")
                console.print()
        
        return True
    
    # /consulting:status [project_name]
    elif cmd.startswith("consulting:status"):
        if len(original_parts) >= 2:
            project_name = original_parts[1]
        else:
            # プロジェクト名が指定されていない場合は最新のプロジェクトを使用
            project_name = get_current_project()
            if not project_name:
                console.print("[red]エラー: プロジェクトが初期化されていません[/red]")
                console.print("[dim]使用方法: /consulting:status [project_name][/dim]")
                console.print()
                return True
        
        # プロジェクトの存在確認
        project_dir = get_project_dir(project_name)
        state_file = project_dir / "consulting.json"
        if not state_file.exists():
            console.print(f"[red]エラー: プロジェクト '{project_name}' が見つかりません[/red]")
            console.print()
            return True
        
        state = load_state(project_name)
        
        console.print(f"[bold]プロジェクト: {project_name}[/bold]")
        console.print(f"  状態: {state['status']}")
        console.print(f"  現在のステップ: {state['current_step'] or 'なし'}")
        
        # CSVファイル情報を表示（複数ファイル対応）
        csv_paths = state.get("csv_paths", [])
        if not csv_paths:
            # 後方互換性のため、csv_pathもチェック
            csv_path = state.get("csv_path", "")
            if csv_path:
                csv_paths = [csv_path]
        
        if csv_paths:
            console.print(f"  CSVファイル数: {len(csv_paths)}")
            for i, csv_path in enumerate(csv_paths, 1):
                console.print(f"    {i}. {Path(csv_path).name}")
        else:
            console.print(f"  CSVファイル: 未設定")
        
        if state.get("analysis_focus"):
            console.print(f"  分析の焦点: {state['analysis_focus']}")
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
            
            output_file = step_info.get("output_file")
            if output_file:
                status_display += f" - {output_file}"
            
            console.print(f"  {step_name}: {status_display}")
            
            # process_dataステップの場合はタスク状況も表示
            if step_name == "process_data" and "tasks" in step_info:
                tasks = step_info["tasks"]
                if tasks:
                    completed = sum(1 for t in tasks.values() if t.get("status") == "completed")
                    total = len(tasks)
                    console.print(f"    タスク: {completed}/{total} 完了")
                    for hypothesis_id in sorted(tasks.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0):
                        task = tasks[hypothesis_id]
                        task_status = task.get("status", "pending")
                        if task_status == "completed":
                            console.print(f"      [green]✓ {hypothesis_id}[/green]")
                        elif task_status == "failed":
                            console.print(f"      [red]✗ {hypothesis_id}[/red]")
                        elif task_status == "in_progress":
                            console.print(f"      [yellow]→ {hypothesis_id}[/yellow]")
                        else:
                            console.print(f"      [dim]○ {hypothesis_id}[/dim]")
        
        if state.get("retry_count", 0) > 0:
            console.print()
            console.print(f"[dim]リトライ回数: {state['retry_count']}[/dim]")
        
        if state.get("errors"):
            console.print()
            console.print("[yellow]エラー:[/yellow]")
            for error in state["errors"]:
                console.print(f"  - {error}")
        
        console.print()

        next_step = state.get("current_step")
        if next_step:
            console.print("[bold]次のステップ:[/bold]")
            _show_next_steps(state, next_step, project_name)
        else:
            step_order = ["hypothesis", "process_data", "validate", "strategy", "report"]
            pending_step = None
            for name in step_order:
                info = state["steps"].get(name, {})
                if info.get("status") in {"pending", "in_progress"}:
                    pending_step = name
                    break
            if pending_step:
                console.print("[bold]推奨コマンド:[/bold]")
                if pending_step == "hypothesis":
                    console.print(f"  /consulting:hypothesis {project_name}")
                elif pending_step == "process_data":
                    console.print(f"  /consulting:process-data {project_name}")
                elif pending_step == "validate":
                    console.print(f"  /consulting:validate {project_name}")
                elif pending_step == "strategy":
                    console.print(f"  /consulting:strategy {project_name}")
                elif pending_step == "report":
                    console.print(f"  /consulting:report {project_name}")
                console.print()

        return True
    
    else:
        console.print(f"[yellow]未知のコマンド: /{cmd}[/yellow]")
        console.print(
            "[dim]利用可能なコマンド: "
            "/consulting:init, /consulting:hypothesis, /consulting:process-data, "
            "/consulting:validate, /consulting:strategy, /consulting:report, "
            "/consulting:approve, /consulting:reject, /consulting:status[/dim]"
        )
        console.print()
        return True


def _show_next_steps(state: dict, current_step: str, project_name: str) -> None:
    """次のステップを案内。"""
    step_order = ["hypothesis", "process_data", "validate", "strategy", "report"]
    command_map = {
        "hypothesis": f"/consulting:hypothesis {project_name}",
        "process_data": f"/consulting:process-data {project_name}",
        "validate": f"/consulting:validate {project_name}",
        "strategy": f"/consulting:strategy {project_name}",
        "report": f"/consulting:report {project_name}",
    }

    if current_step in step_order:
        current_info = state["steps"].get(current_step, {})
        if current_info.get("status") in {"pending", "in_progress"}:
            console.print(f"[dim]次に実行してください: {command_map[current_step]}[/dim]")
            console.print()
            return
        # 探索を現在ステップの次から開始
        start_index = step_order.index(current_step) + 1
    else:
        start_index = 0

    for step in step_order[start_index:]:
        info = state["steps"].get(step, {})
        if info.get("status") not in {"approved", "completed"}:
            console.print(f"[dim]次のステップ: {command_map[step]}[/dim]")
            console.print()
            return

    console.print("[green]✓ 分析が完了しました！[/green]")
    console.print()

