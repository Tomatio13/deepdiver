# Consulting機能 詳細設計書

## 1. 概要

### 1.1 目的
経営コンサルティング機能は、複数のCSVファイル（売上、人事、財務など）を読み込み、AIエージェントが経営課題を抽出・検証し、戦略を立案するマルチステップワークフローを提供します。Human-in-the-Loopを組み込むことで、各ステップで人間の承認を得ながら、高品質な分析結果を段階的に構築します。

### 1.2 アーキテクチャ概要

```
ユーザー入力
    ↓
スラッシュコマンド (/consulting:*)
    ↓
consulting_commands.py (コマンドハンドラー)
    ↓
consulting_state.py (状態管理)
    ↓
consulting_agents.py (各エージェント実行)
    ↓
consulting_prompts.py (プロンプト管理)
    ↓
Strands Agent (LLM呼び出し)
    ↓
成果物生成 (Markdownファイル)
    ↓
状態更新 (consulting.json)
```

### 1.3 主要コンポーネント

| コンポーネント | ファイル | 責務 |
|--------------|---------|------|
| コマンドハンドラー | `consulting_commands.py` | スラッシュコマンドの解析と実行制御 |
| 状態管理 | `consulting_state.py` | プロジェクト状態の永続化と管理 |
| エージェント実装 | `consulting_agents.py` | 各ステップのエージェント実行ロジック |
| プロンプト管理 | `consulting_prompts.py` | エージェント用プロンプトテンプレート |
| CSVツール | `csv_tool.py` | CSVファイル読み込みとフィルタリング |

## 2. メモリ構造

コンサルティング機能は、認知科学のメモリモデルに基づいて情報を4つのタイプに分類して管理します。

### 2.1 ワーキングメモリ（Working Memory）

現在の分析プロジェクトの状態と進捗を保持します。

#### 2.1.1 状態ファイル構造

`.consulting/<project_name>/consulting.json` の構造:

```json
{
  "version": "1.0",
  "project_name": "sales_profit_improve",
  "csv_paths": [
    "sample_sales_data.csv",
    "sample_hr_data.csv"
  ],
  "analysis_focus": "売上向上と利益率改善",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00",
  "status": "hypothesis_completed",
  "current_step": "hypothesis",
  "steps": {
    "hypothesis": {
      "status": "completed",
      "approved": null,
      "completed_at": "2024-01-01T00:00:00",
      "output_file": "hypotheses.md",
      "feedback": []
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

#### 2.1.2 状態フィールドの説明

- **`version`**: スキーマバージョン（将来の互換性管理用）
- **`project_name`**: プロジェクト識別子（英小文字、アンダースコア区切り、最大24文字）
- **`csv_paths`**: 読み込まれたCSVファイルの絶対パスリスト
- **`analysis_focus`**: 分析の焦点（初期化時に設定）
- **`created_at`**: プロジェクト作成日時（ISO 8601形式）
- **`updated_at`**: 最終更新日時（ISO 8601形式）
- **`status`**: 現在のフェーズと状態（`{step}_{status}`形式）
- **`current_step`**: 現在実行中のステップ名
- **`steps.<step>.status`**: 各ステップの状態
  - `pending`: 未実行
  - `in_progress`: 実行中
  - `completed`: 完了（承認待ち）
  - `approved`: 承認済み
  - `rejected`: 否決済み
- **`steps.<step>.approved`**: 承認フラグ（`true`/`false`/`null`）
- **`steps.<step>.completed_at`**: ステップ完了日時
- **`steps.<step>.output_file`**: 生成されたMarkdownファイル名
- **`steps.<step>.feedback`**: フィードバック履歴（配列）

#### 2.1.3 成果物ファイル

各ステップで生成されるMarkdownファイル:

- **`hypotheses.md`**: 仮説一覧（仮説立案ステップ）
- **`processed_data.md`**: 加工済みデータの説明（データ加工ステップ）
- **`validation_results.md`**: 検証結果の詳細（仮説検証ステップ）
- **`strategies.md`**: 戦略提案一覧（戦略立案ステップ）
- **`report.md`**: 最終レポート（レポート生成ステップ）

### 2.2 エピソード記憶（Episodic Memory）

プロジェクトの実行履歴と承認プロセスを記録します。

#### 2.2.1 タイムスタンプ管理

- **`created_at`**: プロジェクト作成日時
- **`updated_at`**: 最終更新日時（各状態更新時に自動更新）
- **`steps.<step>.completed_at`**: 各ステップの完了日時

#### 2.2.2 承認・否決の履歴

- **`steps.<step>.approved`**: 承認フラグの推移
  - `null` → 未承認
  - `true` → 承認済み
  - `false` → 否決済み
- **`steps.<step>.feedback[]`**: フィードバック履歴
  ```json
  [
    {
      "reason": "否決理由や改善要望のテキスト",
      "timestamp": "2024-01-02T09:30:00"
    }
  ]
  ```

#### 2.2.3 ワークフロー巻き戻し履歴

否決時のワークフロー巻き戻しロジック:

- **検証否決時**: 仮説生成ステップに戻る
- **戦略否決時**: 検証ステップに戻る
- **レポート否決時**: 戦略ステップに戻る

#### 2.2.4 Git履歴（オプション）

`.consulting/<project_name>/` ディレクトリをGitで管理することで、各成果物ファイルの版管理が可能です。

### 2.3 意味記憶（Semantic Memory）

分析で得られた知見と構造化された知識を保存します。

#### 2.3.1 分析成果物（Markdownファイル）

各ステップで生成されるMarkdownファイルには、以下の情報が含まれます:

- **`hypotheses.md`**: 
  - 抽出された経営課題の仮説
  - 各仮説の根拠データ
  - 優先度評価
- **`processed_data.md`**: 
  - 検証用に加工された指標
  - データの説明と統計サマリー
  - 可視化用データの準備状況
- **`validation_results.md`**: 
  - 仮説検証の結果
  - 各仮説の成立/不成立判定
  - 根拠となるデータ分析
- **`strategies.md`**: 
  - 検証済み課題に対する施策提案
  - 優先度と影響度評価
  - 実装可能性の評価
- **`report.md`**: 
  - 全成果を統合した最終レポート
  - 実行サマリー
  - 推奨事項

#### 2.3.2 プロジェクトメタデータ

- **`analysis_focus`**: 分析の焦点（初期化時に設定）
- **`csv_paths`**: 使用したデータソースの記録

#### 2.3.3 プロンプトテンプレート

`ddaword_cli/consulting_prompts.py` に定義された知識ベース:

- **各エージェント用プロンプト**: 各ステップの標準的なプロンプトテンプレート
- **可視化指針**: matplotlib/seaborn を使用したグラフ作成ガイドライン
- **Quarto出力ガイド**: Quarto互換Markdown出力のガイドライン
- **ファイル読み込みガイド**: 大容量ファイルの効率的な読み込み方法

### 2.4 手続き記憶（Procedural Memory）

ワークフローの実行手順と各ステップの処理方法を定義します。

#### 2.4.1 スラッシュコマンドのワークフロー

```
/consulting:init <analysis_focus> <csv_path1> [csv_path2] ...
  ↓
/consulting:hypothesis <project_name>
  ↓ [承認が必要]
/consulting:approve <project_name>
  ↓
/consulting:process-data <project_name>
  ↓
/consulting:validate <project_name>
  ↓ [承認/否決が必要]
  ├─ /consulting:approve <project_name> → /consulting:strategy
  └─ /consulting:reject <project_name> → /consulting:hypothesis (再実行)
  ↓
/consulting:strategy <project_name>
  ↓ [承認が必要]
/consulting:approve <project_name>
  ↓
/consulting:report <project_name>
  ↓ [承認が必要]
/consulting:approve <project_name>
  ↓
完了
```

#### 2.4.2 各ステップの処理手順

**仮説立案 (`generate_hypotheses`)**:
1. CSVファイルを読み込み
2. データ概要を生成
3. 過去のフィードバックを参照
4. LLMエージェントに仮説生成を依頼
5. Markdown形式で仮説一覧を生成
6. `hypotheses.md` に保存
7. 状態を `completed` に更新

**データ加工 (`process_data_for_validation`)**:
1. 承認済み仮説を読み込み
2. CSVファイルから検証に必要なデータを抽出
3. データを集計・加工
4. 過去のフィードバックを参照
5. LLMエージェントにデータ加工を依頼
6. Markdown形式で加工結果を生成
7. `processed_data.md` に保存
8. 状態を `completed` に更新

**仮説検証 (`validate_hypotheses`)**:
1. 加工済みデータと仮説を読み込み
2. データに基づいて仮説を検証
3. 統計的分析を実施
4. 過去のフィードバックを参照
5. LLMエージェントに検証を依頼
6. Markdown形式で検証結果を生成
7. `validation_results.md` に保存
8. 状態を `completed` に更新

**戦略立案 (`plan_strategies`)**:
1. 検証済み仮説を読み込み
2. 検証結果に基づいて戦略を立案
3. 優先度と影響度を評価
4. 過去のフィードバックを参照
5. LLMエージェントに戦略立案を依頼
6. Markdown形式で戦略一覧を生成
7. `strategies.md` に保存
8. 状態を `completed` に更新

**レポート生成 (`generate_consulting_report`)**:
1. 全ステップの成果物を読み込み
2. 全成果を統合
3. 過去のフィードバックを参照
4. LLMエージェントにレポート生成を依頼
5. Markdown形式で最終レポートを生成
6. `report.md` に保存
7. 状態を `completed` に更新

#### 2.4.3 Human-in-the-Loop プロセス

**承認フロー**:
1. ステップ完了後、ユーザーに承認を求める
2. `/consulting:approve <project_name>` で承認
3. 状態を `approved` に更新
4. 次のステップを案内

**否決フロー**:
1. `/consulting:reject <project_name>` で否決
2. CLIが理由入力を求める
3. 理由を `feedback` に追加
4. 状態を `rejected` に更新
5. 適切なステップに巻き戻し
6. 次の実行時にフィードバックを参照

**状態確認**:
1. `/consulting:status [project_name]` で現在の状態を表示
2. 各ステップの状態を表示
3. 推奨される次のコマンドを案内

#### 2.4.4 状態管理ロジック

`consulting_state.py` の主要関数:

- **`load_state(project_name)`**: 状態ファイルを読み込み
- **`save_state(project_name, state)`**: 状態ファイルを保存
- **`update_step_status(project_name, step, status, output_file)`**: ステップ状態を更新
- **`approve_step(project_name, step)`**: ステップを承認
- **`reject_step(project_name, step, reason)`**: ステップを否決
- **`add_feedback(project_name, step, reason)`**: フィードバックを追加
- **`get_current_project()`**: 最新のプロジェクト名を取得

## 3. スラッシュコマンド詳細

### 3.1 コマンド一覧

| コマンド | 説明 | 承認必要 | 引数 |
|---------|------|---------|------|
| `/consulting:init` | 分析を初期化し、作業ディレクトリを作成 | - | `<analysis_focus> <csv_path1> [csv_path2] ...` |
| `/consulting:hypothesis` | 仮説を生成 | あり | `<project_name>` |
| `/consulting:process-data` | データを整理・加工 | - | `<project_name>` |
| `/consulting:validate` | 仮説を検証 | あり（承認/否決） | `<project_name>` |
| `/consulting:strategy` | 戦略を立案 | あり | `<project_name>` |
| `/consulting:report` | レポートを生成 | あり | `<project_name>` |
| `/consulting:status` | 現在の状態を表示 | - | `[project_name]` |
| `/consulting:approve` | 現在のステップを承認 | - | `<project_name>` |
| `/consulting:reject` | 現在のステップを否決 | - | `<project_name>` |

### 3.2 コマンド実装詳細

#### 3.2.1 `/consulting:init`

**機能**: 分析プロジェクトを初期化し、作業ディレクトリを作成します。

**処理フロー**:
1. `analysis_focus` と CSV パスを解析
2. CSV パスの存在確認
3. フォルダ指定の場合は再帰的に `.csv` ファイルを収集
4. `analysis_focus` から AI で `project_name` を生成
   - 英小文字のみ
   - 数字なし
   - `単語_単語` 形式
   - 最大24文字
5. `.consulting/<project_name>/` ディレクトリを作成
6. `consulting.json` を初期化
7. 状態を保存

**エラーハンドリング**:
- CSV ファイルが見つからない場合: エラーメッセージを表示
- フォルダ内に CSV ファイルがない場合: 警告を表示
- プロジェクト名生成に失敗した場合: フォールバック名を使用

#### 3.2.2 `/consulting:hypothesis`

**機能**: CSV データから経営課題の仮説を生成します。

**処理フロー**:
1. プロジェクトの存在確認
2. CSV ファイルの確認
3. CSV ファイルを読み込み
4. データ概要を生成
5. 過去のフィードバックを参照
6. LLM エージェントに仮説生成を依頼
7. `hypotheses.md` に保存
8. 状態を `completed` に更新
9. 承認を求める

**前提条件**:
- プロジェクトが初期化されていること
- CSV ファイルが指定されていること

#### 3.2.3 `/consulting:process-data`

**機能**: 仮説検証に必要なデータを抽出・加工します。

**処理フロー**:
1. プロジェクトの存在確認
2. 仮説が承認されているか確認
3. 承認済み仮説を読み込み
4. CSV ファイルから検証に必要なデータを抽出
5. データを集計・加工
6. 過去のフィードバックを参照
7. LLM エージェントにデータ加工を依頼
8. `processed_data.md` に保存
9. 状態を `completed` に更新

**前提条件**:
- 仮説が承認されていること

#### 3.2.4 `/consulting:validate`

**機能**: 仮説をデータで検証します。

**処理フロー**:
1. プロジェクトの存在確認
2. 加工済みデータと仮説を読み込み
3. データに基づいて仮説を検証
4. 統計的分析を実施
5. 過去のフィードバックを参照
6. LLM エージェントに検証を依頼
7. `validation_results.md` に保存
8. 状態を `completed` に更新
9. 承認/否決を求める

**前提条件**:
- データ加工が完了していること

#### 3.2.5 `/consulting:strategy`

**機能**: 検証済み課題に対する施策を提案します。

**処理フロー**:
1. プロジェクトの存在確認
2. 検証が承認されているか確認
3. 検証済み仮説を読み込み
4. 検証結果に基づいて戦略を立案
5. 優先度と影響度を評価
6. 過去のフィードバックを参照
7. LLM エージェントに戦略立案を依頼
8. `strategies.md` に保存
9. 状態を `completed` に更新
10. 承認を求める

**前提条件**:
- 検証が承認されていること

#### 3.2.6 `/consulting:report`

**機能**: 全成果を統合した最終レポートを生成します。

**処理フロー**:
1. プロジェクトの存在確認
2. 戦略が承認されているか確認
3. 全ステップの成果物を読み込み
4. 全成果を統合
5. 過去のフィードバックを参照
6. LLM エージェントにレポート生成を依頼
7. `report.md` に保存
8. 状態を `completed` に更新
9. 承認を求める

**前提条件**:
- 戦略が承認されていること

#### 3.2.7 `/consulting:status`

**機能**: 現在の状態を表示し、推奨される次のコマンドを案内します。

**処理フロー**:
1. プロジェクト名を取得（省略時は最新プロジェクト）
2. 状態ファイルを読み込み
3. プロジェクト情報を表示
4. 各ステップの状態を表示
5. 推奨される次のコマンドを案内

#### 3.2.8 `/consulting:approve`

**機能**: 現在のステップを承認します。

**処理フロー**:
1. プロジェクトの存在確認
2. 現在のステップを取得
3. ステップが完了しているか確認
4. ステップを承認
5. 状態を `approved` に更新
6. 次のステップを案内

**前提条件**:
- ステップが `completed` 状態であること

#### 3.2.9 `/consulting:reject`

**機能**: 現在のステップを否決し、理由を記録します。

**処理フロー**:
1. プロジェクトの存在確認
2. 現在のステップを取得
3. 理由入力を求める
4. 理由を `feedback` に追加
5. ステップを否決
6. 状態を `rejected` に更新
7. 適切なステップに巻き戻し
8. 次の実行時にフィードバックを参照するよう案内

**ワークフロー巻き戻し**:
- 検証否決時: 仮説生成ステップに戻る
- 戦略否決時: 検証ステップに戻る
- レポート否決時: 戦略ステップに戻る

## 4. エージェント実装詳細

### 4.1 エージェントアーキテクチャ

各エージェントは以下の構造で実装されています:

```python
async def generate_hypotheses(
    state: dict[str, Any],
    project_name: str,
) -> dict[str, Any]:
    """仮説生成エージェント"""
    # 1. 状態とCSVファイルを読み込み
    # 2. データ概要を生成
    # 3. 過去のフィードバックを参照
    # 4. LLMエージェントを作成
    # 5. プロンプトを構築
    # 6. エージェントを呼び出し
    # 7. 結果をMarkdown形式で保存
    # 8. 状態を更新して返す
```

### 4.2 エージェント共通処理

#### 4.2.1 モデル取得

```python
def _get_model():
    """モデルインスタンスを取得（キャッシュを使用）。"""
    global _cached_model
    if _cached_model is None:
        _cached_model = create_model()
    return _cached_model
```

#### 4.2.2 エージェント作成

```python
def _create_consulting_agent(agent_type: str, model: Any) -> Agent:
    """指定されたタイプのコンサルティングエージェントを作成。"""
    prompt = CONSULTING_PROMPTS.get(agent_type, "")
    return Agent(
        model=model,
        system_prompt=prompt,
        tools=[],
    )
```

#### 4.2.3 非同期呼び出し

```python
async def _invoke_agent_async(agent: Agent, prompt: str) -> str:
    """エージェントを非同期で呼び出し、結果を文字列で返す。"""
    if hasattr(agent, "invoke_async"):
        response = await agent.invoke_async(prompt)
    else:
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
```

### 4.3 各エージェントの詳細

#### 4.3.1 仮説立案エージェント (`generate_hypotheses`)

**入力**:
- `state`: プロジェクト状態
- `project_name`: プロジェクト名

**処理**:
1. CSV ファイルを読み込み
2. 各ファイルのデータ概要を生成
3. 複数ファイルの場合は統合情報を追加
4. 過去のフィードバックを参照
5. LLM エージェントに仮説生成を依頼

**出力**:
- `state["hypotheses_markdown"]`: Markdown形式の仮説一覧

**プロンプト構造**:
- データ概要
- 分析の焦点
- 過去のフィードバック（存在する場合）
- 出力形式の指示

#### 4.3.2 データ加工エージェント (`process_data_for_validation`)

**入力**:
- `state`: プロジェクト状態
- `project_name`: プロジェクト名

**処理**:
1. 承認済み仮説を読み込み
2. CSV ファイルから検証に必要なデータを抽出
3. データを集計・加工
4. 過去のフィードバックを参照
5. LLM エージェントにデータ加工を依頼

**出力**:
- `state["processed_data_markdown"]`: Markdown形式の加工結果

**プロンプト構造**:
- 承認済み仮説
- CSV データ概要
- 過去のフィードバック（存在する場合）
- 出力形式の指示

#### 4.3.3 仮説検証エージェント (`validate_hypotheses`)

**入力**:
- `state`: プロジェクト状態
- `project_name`: プロジェクト名

**処理**:
1. 加工済みデータと仮説を読み込み
2. データに基づいて仮説を検証
3. 統計的分析を実施
4. 過去のフィードバックを参照
5. LLM エージェントに検証を依頼

**出力**:
- `state["validation_results_markdown"]`: Markdown形式の検証結果

**プロンプト構造**:
- 承認済み仮説
- 加工済みデータ
- 過去のフィードバック（存在する場合）
- 出力形式の指示

#### 4.3.4 戦略立案エージェント (`plan_strategies`)

**入力**:
- `state`: プロジェクト状態
- `project_name`: プロジェクト名

**処理**:
1. 検証済み仮説を読み込み
2. 検証結果に基づいて戦略を立案
3. 優先度と影響度を評価
4. 過去のフィードバックを参照
5. LLM エージェントに戦略立案を依頼

**出力**:
- `state["strategies_markdown"]`: Markdown形式の戦略一覧

**プロンプト構造**:
- 検証済み仮説
- 検証結果
- 過去のフィードバック（存在する場合）
- 出力形式の指示

#### 4.3.5 レポート生成エージェント (`generate_consulting_report`)

**入力**:
- `state`: プロジェクト状態
- `project_name`: プロジェクト名

**処理**:
1. 全ステップの成果物を読み込み
2. 全成果を統合
3. 過去のフィードバックを参照
4. LLM エージェントにレポート生成を依頼

**出力**:
- `state["report_markdown"]`: Markdown形式の最終レポート

**プロンプト構造**:
- 全ステップの成果物
- 過去のフィードバック（存在する場合）
- 出力形式の指示（Quarto互換）

## 5. プロンプト管理

### 5.1 プロンプト構造

各エージェント用のプロンプトは `consulting_prompts.py` に定義されています。

```python
CONSULTING_PROMPTS = {
    "hypothesis_generator": "...",
    "data_processor": "...",
    "hypothesis_validator": "...",
    "strategy_planner": "...",
    "report_generator": "..."
}
```

### 5.2 プロンプトの動的構築

各エージェント実行時に、以下の情報がプロンプトに動的に追加されます:

1. **データ概要**: CSV ファイルの内容概要
2. **過去の成果物**: 前のステップで生成されたMarkdownファイル
3. **フィードバック**: 否決理由や改善要望
4. **分析の焦点**: 初期化時に設定された分析の焦点

### 5.3 知識ベース

プロンプトには以下の知識ベースが含まれています:

- **可視化指針**: matplotlib/seaborn を使用したグラフ作成ガイドライン
- **Quarto出力ガイド**: Quarto互換Markdown出力のガイドライン
- **ファイル読み込みガイド**: 大容量ファイルの効率的な読み込み方法

## 6. エラーハンドリング

### 6.1 エラー種類

#### 6.1.1 CSV読み込みエラー

- **原因**: ファイルが存在しない、エンコーディングエラー、形式エラー
- **処理**: エラーメッセージを表示し、処理を中断

#### 6.1.2 LLM呼び出しエラー

- **原因**: API キー未設定、ネットワークエラー、レート制限
- **処理**: エラーメッセージを表示し、状態を `error` に更新

#### 6.1.3 データ処理エラー

- **原因**: データ形式の不一致、メモリ不足
- **処理**: エラーメッセージを表示し、部分的な結果を保存

#### 6.1.4 状態ファイルエラー

- **原因**: ファイル読み書きエラー、JSON解析エラー
- **処理**: エラーメッセージを表示し、バックアップを試行

### 6.2 リトライロジック

- **`retry_count`**: リトライ回数を記録
- **`max_retry`**: 最大リトライ回数（デフォルト: 3）
- リトライ時は前回のフィードバックを参照

### 6.3 フォールバック処理

- エージェントが失敗した場合でも、部分的な結果をMarkdownファイルに保存
- エラー情報を `consulting.json` に記録
- ユーザーにエラー内容を通知

## 7. ファイル構造

### 7.1 ソースコード構造

```
ddaword_cli/
├── consulting_commands.py      # スラッシュコマンドハンドラー
├── consulting_state.py          # 状態管理（consulting.json）
├── consulting_agents.py         # 各サブエージェントの実装
├── consulting_prompts.py        # プロンプト管理
└── csv_tool.py                 # CSV読み込みツール
```

### 7.2 作業ディレクトリ構造

```
.consulting/
└── <project_name>/
    ├── consulting.json          # 状態管理ファイル
    ├── hypotheses.md            # 仮説一覧
    ├── processed_data.md        # 加工済みデータ
    ├── validation_results.md    # 検証結果
    ├── strategies.md            # 戦略一覧
    └── report.md                # 最終レポート
```

## 8. 使用例

### 8.1 基本的な使用フロー

```bash
# 1. 分析を初期化（単一ファイル）
/consulting:init "売上向上と利益率改善" sample_sales_data.csv

# 2. 仮説を生成
/consulting:hypothesis sales_profit_improve

# 3. 仮説を確認して承認
/consulting:approve sales_profit_improve

# 4. データを整理・加工
/consulting:process-data sales_profit_improve

# 5. 仮説を検証
/consulting:validate sales_profit_improve

# 6. 検証結果を確認して承認
/consulting:approve sales_profit_improve

# 7. 戦略を立案
/consulting:strategy sales_profit_improve

# 8. 戦略を確認して承認
/consulting:approve sales_profit_improve

# 9. レポートを生成
/consulting:report sales_profit_improve

# 10. レポートを確認して承認
/consulting:approve sales_profit_improve
```

### 8.2 複数ファイルでの分析

```bash
# 複数ファイルを指定
/consulting:init "売上と人事の総合分析" sample_sales_data.csv sample_hr_data.csv

# フォルダ指定（再帰的にCSVを収集）
/consulting:init "総合経営分析" ./data/

# ファイルとフォルダの混在
/consulting:init "総合分析" sales.csv ./hr_data/ financial.csv
```

### 8.3 否決と再実行

```bash
# 仮説を否決
/consulting:reject sales_profit_improve
# 理由を入力: "信頼度が低い仮説を除外したい"

# 仮説を再生成（フィードバックを参照）
/consulting:hypothesis sales_profit_improve

# 検証を否決（仮説生成に戻る）
/consulting:reject sales_profit_improve
# 理由を入力: "データの解釈が不十分"

# 仮説を再生成
/consulting:hypothesis sales_profit_improve
```

### 8.4 状態確認

```bash
# 現在の状態を確認（最新プロジェクト）
/consulting:status

# 特定のプロジェクトの状態を確認
/consulting:status sales_profit_improve
```

## 9. 拡張性と将来の改善

### 9.1 拡張可能なポイント

1. **新しいステップの追加**: ワークフローに新しいステップを追加可能
2. **カスタムエージェント**: 独自のエージェントを追加可能
3. **プロンプトのカスタマイズ**: プロンプトテンプレートをカスタマイズ可能
4. **出力形式の拡張**: Markdown以外の形式（PDF、HTMLなど）への対応

### 9.2 将来の改善案

1. **バッチ処理**: 複数プロジェクトの一括処理
2. **テンプレート機能**: よく使う分析パターンのテンプレート化
3. **可視化の自動生成**: グラフやチャートの自動生成
4. **コラボレーション機能**: 複数ユーザーでの共同分析
5. **バージョン管理統合**: Gitとの統合強化

## 10. テスト戦略

### 10.1 単体テスト

- 状態管理関数のテスト
- CSV読み込み関数のテスト
- プロンプト構築関数のテスト

### 10.2 統合テスト

- エンドツーエンドのワークフローテスト
- エラーハンドリングのテスト
- フィードバック機能のテスト

### 10.3 パフォーマンステスト

- 大容量CSVファイルの処理テスト
- 複数ファイルの同時処理テスト
- LLM呼び出しのレート制限テスト

## 11. まとめ

Consulting機能は、認知科学のメモリモデルに基づいて設計された、Human-in-the-Loopを組み込んだマルチステップワークフローです。各ステップで人間の承認を得ながら、段階的に高品質な分析結果を構築します。

主要な特徴:
- **4つのメモリタイプ**: ワーキングメモリ、エピソード記憶、意味記憶、手続き記憶
- **Human-in-the-Loop**: 各ステップでの承認・否決プロセス
- **フィードバック機能**: 否決理由を記録し、次回実行時に参照
- **柔軟なデータ入力**: 単一ファイル、複数ファイル、フォルダ指定に対応
- **構造化された成果物**: Markdown形式で各ステップの成果を保存

この設計により、ユーザーはAIエージェントと協働しながら、段階的に経営課題を分析し、戦略を立案できます。

