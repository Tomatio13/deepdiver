# ストリーミングイベント実装の比較

## Strands Agentsドキュメントのイベントタイプ

[Strands Agents Streaming Overview](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/overview/)によると、以下のイベントタイプがあります：

### Lifecycle Events
- `init_event_loop`: True at the start of agent invocation initializing
- `start_event_loop`: True when the event loop is starting
- `message`: Present when a new message is created
- `event`: Raw event from the model stream
- `force_stop`: True if the event loop was forced to stop
- `force_stop_reason`: Reason for forced stop
- `result`: The final AgentResult

### Text Generation Events
- `data`: Text chunk from the model's output
- `delta`: Raw delta content from the model

### Tool Events
- `current_tool_use`: Information about the current tool being used
  - `toolUseId`: Unique ID for this tool use
  - `name`: Name of the tool
  - `input`: Tool input parameters
- `tool_stream_event`: Information about an event streamed from a tool
  - `tool_use`: The ToolUse for the tool that streamed the event
  - `data`: The data streamed from the tool

## 現在の実装

### 問題点

1. **`model_stream_event`の使用**
   - 現在: `event.get("model_stream_event")`をチェック
   - ドキュメント: `data`と`delta`が直接イベントに含まれる
   - **不一致**: ドキュメントには`model_stream_event`というネストされた構造は記載されていない

2. **`assistant_response`の使用**
   - 現在: `event.get("assistant_response")`をチェック
   - ドキュメント: `result`が最終結果を示す
   - **不一致**: ドキュメントには`assistant_response`というイベントは記載されていない

3. **終了判定**
   - 現在: `type`が`"stream_end"`, `"done"`, `"complete"`, `"finish"`をチェック
   - ドキュメント: `result`イベントが来たら完了と判断すべき
   - **不一致**: `complete`イベントは明示的に記載されていない

4. **テキスト生成イベントの処理**
   - 現在: `model_stream_event.delta`または`model_stream_event.output_text`をチェック
   - ドキュメント: `data`または`delta`が直接イベントに含まれる
   - **不一致**: ネストされた構造ではなく、直接イベントに含まれる

## 修正が必要な箇所

### 1. `_render_model_delta`関数

**現在の実装**:
```python
def _render_model_delta(event: dict, buffer: list[str]) -> bool:
    model_event = event.get("model_stream_event")
    if not isinstance(model_event, dict):
        return False

    delta = model_event.get("delta") or model_event.get("output_text")
```

**修正後**:
```python
def _render_model_delta(event: dict, buffer: list[str]) -> bool:
    # ドキュメントによると、dataとdeltaが直接イベントに含まれる
    data = event.get("data")
    delta = event.get("delta")
    
    text_chunk = data or delta
    if not isinstance(text_chunk, str) or not text_chunk:
        return False

    buffer.append(text_chunk)
    console.print(text_chunk, style=COLORS["agent"], end="")
    return True
```

### 2. `_extract_final_response`関数

**現在の実装**:
```python
def _extract_final_response(event: dict) -> str:
    assistant_event = event.get("assistant_response")
    if isinstance(assistant_event, dict):
        return _stringify_response(assistant_event)
    return ""
```

**修正後**:
```python
def _extract_final_response(event: dict) -> str:
    # ドキュメントによると、resultが最終結果を示す
    result = event.get("result")
    if result:
        return _stringify_response(result)
    return ""
```

### 3. `_stream_agent`関数の終了判定

**現在の実装**:
```python
event_type = event.get("type") or event.get("event_type")
if event_type in ("stream_end", "done", "complete", "finish"):
    break
```

**修正後**:
```python
# resultイベントが来たら完了と判断
if "result" in event:
    # 最終結果を取得して終了
    candidate = _extract_final_response(event)
    if candidate:
        final_response = candidate
    # ループは継続して、全てのイベントを処理する
    # （async forループが自然に終了するまで待つ）
```

## 推奨される修正

1. **テキスト生成イベント**: `data`と`delta`を直接チェック
2. **最終結果**: `result`イベントをチェック
3. **終了判定**: `result`イベントが来たら最終結果を確定（ただし、ループは継続）
4. **ライフサイクルイベント**: 必要に応じて`init_event_loop`、`start_event_loop`、`force_stop`などを処理


