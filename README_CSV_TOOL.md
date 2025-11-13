# CSV経営情報ツールの使用方法

## 概要
`filter_csv_data`ツールは、経営情報が記載されたCSVファイルを読み込み、自然言語指示に従ってデータを絞り込みます。

## サンプルCSVファイル
`sample_financial_data.csv`にサンプルデータが含まれています。

### データ構造
- **年月**: 売上実績の年月（YYYY-MM形式）
- **部署**: 営業部、マーケティング部
- **商品カテゴリ**: PC、スマートフォン、タブレット
- **商品名**: 具体的な商品名
- **売上高（万円）**: 売上金額（万円単位）
- **原価（万円）**: 原価金額（万円単位）
- **利益（万円）**: 利益金額（万円単位）
- **販売数量**: 販売数量

## 使用例

### 1. 2024年の売上高が1000万円以上の行を抽出
```
filter_csv_data(
    csv_path="sample_financial_data.csv",
    query="2024年の売上高が1000万円以上の行を抽出",
    output_format="markdown"
)
```

### 2. 営業部のデータのみを抽出
```
filter_csv_data(
    csv_path="sample_financial_data.csv",
    query="営業部のデータのみを抽出",
    output_format="json"
)
```

### 3. 利益が500万円以上の行を抽出し、売上高で降順にソート
```
filter_csv_data(
    csv_path="sample_financial_data.csv",
    query="利益が500万円以上の行を抽出し、売上高で降順にソート",
    output_format="markdown"
)
```

### 4. PCカテゴリの2024年4月以降のデータを抽出
```
filter_csv_data(
    csv_path="sample_financial_data.csv",
    query="PCカテゴリの2024年4月以降のデータを抽出",
    output_format="csv"
)
```

### 5. スマートフォンのデータで、販売数量が25以上の行を抽出
```
filter_csv_data(
    csv_path="sample_financial_data.csv",
    query="スマートフォンのデータで、販売数量が25以上の行を抽出",
    output_format="markdown"
)
```

## 出力形式
- **markdown**: Markdownテーブル形式（デフォルト）
- **csv**: CSV形式
- **json**: JSON形式（配列）

## 注意事項
- CSVファイルのパスは相対パスまたは絶対パスで指定できます
- 自然言語指示は日本語で記述してください
- LLMモデルが設定されている必要があります（STRANDS_MODEL_PROVIDER環境変数）


