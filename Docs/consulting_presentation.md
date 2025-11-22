# Consulting機能 プレゼンテーション資料

---

## スライド 1: タイトル

# DDAWord CLI
## Consulting機能

**AIエージェントによる経営課題分析ワークフロー**

---

## スライド 2: 概要

### Consulting機能とは？

複数のCSVファイル（売上、人事、財務など）を読み込み、**AIエージェント**が経営課題を抽出・検証し、戦略を立案する**マルチステップワークフロー**

### 主な特徴

- 🤖 **AIエージェント**による自動分析
- 👤 **Human-in-the-Loop**による品質保証
- 📊 **複数CSVファイル**の横断分析
- 📝 **Markdown形式**での成果物管理
- 🔄 **フィードバック機能**による改善サイクル

---

## スライド 3: 解決する課題

### 従来の課題

❌ 複数のCSVファイルを手動で分析する必要がある  
❌ 分析結果の品質が分析者のスキルに依存する  
❌ 分析プロセスが非構造化で再現性が低い  
❌ フィードバックを反映する仕組みがない  

### Consulting機能の解決策

✅ **自動化された分析ワークフロー**  
✅ **AIエージェントによる高品質な分析**  
✅ **構造化された5ステッププロセス**  
✅ **フィードバック機能による継続的改善**  

---

## スライド 4: アーキテクチャ概要

```
ユーザー入力
    ↓
スラッシュコマンド (/consulting:*)
    ↓
コマンドハンドラー (consulting_commands.py)
    ↓
状態管理 (consulting_state.py)
    ↓
エージェント実行 (consulting_agents.py)
    ↓
Strands Agent (LLM)
    ↓
成果物生成 (Markdownファイル)
```

### 主要コンポーネント

- **コマンドハンドラー**: スラッシュコマンドの解析と実行制御
- **状態管理**: プロジェクト状態の永続化
- **エージェント実装**: 各ステップのLLM呼び出し
- **プロンプト管理**: エージェント用プロンプトテンプレート

---

## スライド 5: メモリ構造（4つのタイプ）

### 認知科学に基づく情報管理

#### 1. ワーキングメモリ（Working Memory）
**現在の会話・作業文脈**
- `.consulting/<project>/consulting.json` の現在状態
- 各ステップの成果物ファイル（Markdown）

#### 2. エピソード記憶（Episodic Memory）
**過去の出来事の履歴**
- タイムスタンプ（created_at, updated_at）
- 承認・否決の履歴
- フィードバック履歴

#### 3. 意味記憶（Semantic Memory）
**事実・知識のストック**
- 分析成果物（hypotheses.md, strategies.md など）
- プロンプトテンプレート
- 可視化指針などの知識ベース

#### 4. 手続き記憶（Procedural Memory）
**行動規則・How to**
- スラッシュコマンドのワークフロー
- 各ステップの処理手順
- Human-in-the-Loop プロセス

---

## スライド 6: ワークフロー（5ステップ）

```
1. 初期化 (/consulting:init)
   ↓
2. 仮説立案 (/consulting:hypothesis)
   ↓ [承認]
3. データ加工 (/consulting:process-data)
   ↓
4. 仮説検証 (/consulting:validate)
   ↓ [承認/否決]
   ├─ 承認 → 5. 戦略立案
   └─ 否決 → 2. 仮説立案（再実行）
   ↓
5. 戦略立案 (/consulting:strategy)
   ↓ [承認]
6. レポート生成 (/consulting:report)
   ↓ [承認]
   完了
```

### 各ステップの成果物

- **仮説立案** → `hypotheses.md`
- **データ加工** → `processed_data.md`
- **仮説検証** → `validation_results.md`
- **戦略立案** → `strategies.md`
- **レポート生成** → `report.md`

---

## スライド 7: 主要機能（1）

### 1. 柔軟なデータ入力

#### 単一ファイル
```bash
/consulting:init "売上向上" sales.csv
```

#### 複数ファイル
```bash
/consulting:init "総合分析" sales.csv hr.csv financial.csv
```

#### フォルダ指定（再帰的）
```bash
/consulting:init "総合分析" ./data/
```

#### ファイルとフォルダの混在
```bash
/consulting:init "分析" sales.csv ./hr_data/ financial.csv
```

---

## スライド 8: 主要機能（2）

### 2. Human-in-the-Loop

各ステップで**人間の承認**を必要とすることで、品質を保証

#### 承認フロー
1. エージェントが成果物を生成
2. ユーザーが内容を確認
3. `/consulting:approve` で承認 → 次のステップへ
4. `/consulting:reject` で否決 → 理由を入力 → 再実行

#### フィードバック機能
- 否決理由が自動的に記録される
- 次回実行時にフィードバックを参照
- 継続的な改善サイクル

---

## スライド 9: 主要機能（3）

### 3. 状態管理と追跡

#### 状態確認コマンド
```bash
/consulting:status [project_name]
```

#### 表示される情報
- プロジェクト情報（名前、分析の焦点）
- 各ステップの状態
  - `pending`: 未実行
  - `completed`: 完了（承認待ち）
  - `approved`: 承認済み
  - `rejected`: 否決済み
- 推奨される次のコマンド

#### 永続化
- `.consulting/<project>/consulting.json` に状態を保存
- プロジェクトごとに独立した状態管理

---

## スライド 10: 使用例（基本フロー）

### 基本的な使用フロー

```bash
# 1. 分析を初期化
/consulting:init "売上向上と利益率改善" sample_sales_data.csv

# 2. 仮説を生成
/consulting:hypothesis sales_profit_improve

# 3. 仮説を確認して承認
/consulting:approve sales_profit_improve

# 4. データを整理・加工
/consulting:process-data sales_profit_improve

# 5. 仮説を検証
/consulting:validate sales_profit_improve

# 6. 検証結果を承認
/consulting:approve sales_profit_improve

# 7. 戦略を立案
/consulting:strategy sales_profit_improve

# 8. 戦略を承認
/consulting:approve sales_profit_improve

# 9. レポートを生成
/consulting:report sales_profit_improve

# 10. レポートを承認
/consulting:approve sales_profit_improve
```

---

## スライド 11: 使用例（否決と再実行）

### フィードバック機能の活用

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

### ワークフロー巻き戻し

- **検証否決時**: 仮説生成ステップに戻る
- **戦略否決時**: 検証ステップに戻る
- **レポート否決時**: 戦略ステップに戻る

---

## スライド 12: 成果物の構造

### プロジェクトディレクトリ構造

```
.consulting/
└── sales_profit_improve/
    ├── consulting.json          # 状態管理ファイル
    ├── hypotheses.md            # 仮説一覧
    ├── processed_data.md        # 加工済みデータ
    ├── validation_results.md    # 検証結果
    ├── strategies.md            # 戦略一覧
    └── report.md                # 最終レポート
```

### 各成果物の内容

- **hypotheses.md**: 経営課題の仮説と根拠
- **processed_data.md**: 検証用に加工された指標
- **validation_results.md**: 仮説検証の結果と結論
- **strategies.md**: 検証済み課題に対する施策提案
- **report.md**: 全成果を統合した最終レポート

---

## スライド 13: 技術的特徴

### AIエージェント技術

- **Strands Agents SDK**を使用
- **複数のLLMプロバイダ**に対応
  - Amazon Bedrock (Claude)
  - OpenAI (GPT-4)
  - Anthropic (Claude)
  - Gemini
  - Ollama

### プロンプトエンジニアリング

- **構造化されたプロンプトテンプレート**
- **動的なプロンプト構築**
  - データ概要の自動追加
  - 過去の成果物の参照
  - フィードバックの統合

### 知識ベース

- **可視化指針**: matplotlib/seaborn ガイドライン
- **Quarto出力ガイド**: レポート形式の標準化
- **ファイル読み込みガイド**: 効率的なデータ処理

---

## スライド 14: メリット・価値

### 1. 効率化

- ⚡ **自動化された分析プロセス**
- ⚡ **複数ファイルの横断分析**
- ⚡ **構造化されたワークフロー**

### 2. 品質保証

- ✅ **Human-in-the-Loop**による品質チェック
- ✅ **フィードバック機能**による継続的改善
- ✅ **再現可能な分析プロセス**

### 3. 柔軟性

- 🔄 **柔軟なデータ入力**（単一/複数/フォルダ）
- 🔄 **カスタマイズ可能なプロンプト**
- 🔄 **段階的な承認プロセス**

### 4. 追跡可能性

- 📊 **完全な状態管理**
- 📊 **タイムスタンプ付き履歴**
- 📊 **フィードバック履歴の記録**

---

## スライド 15: 適用シーン

### 適用可能なシーン

#### 1. 経営課題の分析
- 売上・利益率の分析
- 人事・組織の分析
- 財務状況の分析

#### 2. データドリブンな意思決定
- 複数のデータソースを統合分析
- 仮説検証による根拠のある判断
- 戦略立案の支援

#### 3. レポート作成の自動化
- 構造化されたレポート生成
- グラフ・表の推奨
- Quarto互換形式での出力

---

## スライド 16: アーキテクチャの詳細

### 状態管理の仕組み

```json
{
  "version": "1.0",
  "project_name": "sales_profit_improve",
  "csv_paths": ["sales.csv", "hr.csv"],
  "analysis_focus": "売上向上と利益率改善",
  "status": "hypothesis_completed",
  "current_step": "hypothesis",
  "steps": {
    "hypothesis": {
      "status": "completed",
      "approved": null,
      "completed_at": "2024-01-01T00:00:00",
      "output_file": "hypotheses.md",
      "feedback": []
    }
  }
}
```

### メモリ構造の実装

- **ワーキングメモリ**: `consulting.json` + Markdownファイル
- **エピソード記憶**: タイムスタンプ + フィードバック履歴
- **意味記憶**: 成果物ファイル + プロンプトテンプレート
- **手続き記憶**: コマンドハンドラー + エージェント実装

---

## スライド 17: エラーハンドリング

### エラー種類と対応

#### CSV読み込みエラー
- **原因**: ファイルが存在しない、エンコーディングエラー
- **対応**: エラーメッセージを表示し、処理を中断

#### LLM呼び出しエラー
- **原因**: API キー未設定、ネットワークエラー
- **対応**: エラーメッセージを表示し、状態を更新

#### データ処理エラー
- **原因**: データ形式の不一致、メモリ不足
- **対応**: 部分的な結果を保存し、エラーを記録

### リトライロジック

- **`retry_count`**: リトライ回数を記録
- **`max_retry`**: 最大リトライ回数（デフォルト: 3）
- リトライ時は前回のフィードバックを参照

---

## スライド 18: 拡張性

### 拡張可能なポイント

#### 1. 新しいステップの追加
- ワークフローに新しいステップを追加可能
- 例: リスク分析ステップ、ROI計算ステップ

#### 2. カスタムエージェント
- 独自のエージェントを追加可能
- ドメイン特化型のエージェント

#### 3. プロンプトのカスタマイズ
- プロンプトテンプレートをカスタマイズ可能
- 組織固有の知識ベースの統合

#### 4. 出力形式の拡張
- Markdown以外の形式への対応
- PDF、HTML、Excel など

---

## スライド 19: 将来の改善案

### 計画中の機能

#### 1. バッチ処理
- 複数プロジェクトの一括処理
- スケジュール実行

#### 2. テンプレート機能
- よく使う分析パターンのテンプレート化
- 再利用可能なワークフロー

#### 3. 可視化の自動生成
- グラフやチャートの自動生成
- インタラクティブなダッシュボード

#### 4. コラボレーション機能
- 複数ユーザーでの共同分析
- コメント機能

#### 5. バージョン管理統合
- Gitとの統合強化
- 変更履歴の追跡

---

## スライド 20: まとめ

### Consulting機能の価値

✅ **AIエージェント**による自動化された分析  
✅ **Human-in-the-Loop**による品質保証  
✅ **構造化されたワークフロー**による再現性  
✅ **フィードバック機能**による継続的改善  
✅ **柔軟なデータ入力**による汎用性  

### 適用シーン

- 経営課題の分析
- データドリブンな意思決定
- レポート作成の自動化

### 今後の展開

- 機能の拡張
- パフォーマンスの最適化
- ユーザビリティの向上

---

## スライド 21: デモ

### デモの流れ

1. **初期化**: 複数CSVファイルを指定
2. **仮説生成**: AIエージェントが仮説を生成
3. **承認**: ユーザーが内容を確認して承認
4. **データ加工**: 検証用データを準備
5. **検証**: 仮説をデータで検証
6. **戦略立案**: 検証済み課題に対する施策を提案
7. **レポート生成**: 全成果を統合した最終レポート

### 実際の使用例

```bash
# サンプルデータを使用
/consulting:init "給与水準の引き上げ要否" \
  sample_data/sample_sales_data.csv \
  sample_data/sample_hr_data.csv \
  sample_data/sample_customer_data.csv
```

---

## スライド 22: Q&A

### よくある質問

**Q: どのようなCSVファイルに対応していますか？**  
A: 任意のCSVファイルに対応しています。売上、人事、財務など、様々なデータソースを統合分析できます。

**Q: 分析の精度はどの程度ですか？**  
A: Human-in-the-Loopにより、各ステップで人間が承認することで品質を保証します。フィードバック機能により継続的に改善されます。

**Q: 複数のプロジェクトを同時に管理できますか？**  
A: はい、プロジェクトごとに独立したディレクトリで管理されるため、複数のプロジェクトを同時に進行できます。

**Q: カスタマイズは可能ですか？**  
A: はい、プロンプトテンプレートやエージェントの動作をカスタマイズできます。

---

## スライド 23: お問い合わせ

### ドキュメント

- **README**: `/README.md`
- **詳細設計書**: `/Docs/consulting_detailed_design.md`
- **サンプルデータ**: `/sample_data/`

### サポート

- **GitHub Issues**: バグ報告・機能要望
- **ドキュメント**: 詳細な使用方法とAPIリファレンス

---

## スライド 24: ありがとうございました

# DDAWord CLI
## Consulting機能

**AIエージェントによる経営課題分析ワークフロー**

ご質問・ご意見をお待ちしております




