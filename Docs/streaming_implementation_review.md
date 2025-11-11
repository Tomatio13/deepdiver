# ストリーミング実装レビュー - Strand Agentsとの比較

## 実行日
2025年1月27日

## 概要
現在のストリーミング出力実装をStrand Agentsの公式ドキュメントと比較し、最適性を評価しました。

## 現在の実装状況

### 1. Async Iterator パターンの使用 ✅

**現在の実装:**
```python
# execution.py:148-172
async def _stream_agent(agent: Any, prompt: str) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # イベントのデバッグ用関数を呼び出す
            # process_event(event)

            # _render_tool_event(event)
            # モデルデルタをレンダリング（リアルタイム表示）
            # _render_model_delta(event, response_buffer)

            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
            
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
```

**評価:** ✅ **基本的に適切**
- `stream_async()`を使用してAsync Iteratorパターンを実装している
- ドキュメントの推奨事項に従っている

**問題点:**
- **ストリーミングイベントの処理がコメントアウトされている**
  - `_render_tool_event(event)` がコメントアウト
  - `_render_model_delta(event, response_buffer)` がコメントアウト
  - これにより、ストリーミング中にリアルタイム表示が行われていない

### 2. イベントタイプの処理 ⚠️

**現在の実装:**
```python
# execution.py:79-101
def _render_model_delta(event: dict, buffer: list[str]) -> bool:
    """Render model delta and return True if content was rendered."""
    # Strands Agentのドキュメントによると、テキストチャンクは 'data' フィールドに直接ある
    # 'delta' も存在するが、'data' が推奨される
    data = event.get("data")
    if isinstance(data, str) and data:
        buffer.append(data)
        console.print(data, style=COLORS["agent"], end="")
        sys.stdout.flush()
        return True
    
    # 後方互換性のため、delta もチェック
    delta = event.get("delta")
    if isinstance(delta, str) and delta:
        buffer.append(delta)
        console.print(delta, style=COLORS["tool"], end="")
        sys.stdout.flush()
        return True
    
    return False
```

**評価:** ✅ **適切**
- `data`と`delta`を直接チェックしている（ドキュメントに準拠）
- `sys.stdout.flush()`でリアルタイム表示を実現

**ドキュメント参照:**
> "Text Generation Events: `data`: Text chunk from the model's output, `delta`: Raw delta content from the model"

### 3. 最終結果の抽出 ✅

**現在の実装:**
```python
# execution.py:104-122
def _extract_final_response(event: dict) -> str:
    """Extract final response from event."""
    # Strands Agentのドキュメントによると、最終結果は 'result' フィールドにある
    result = event.get("result")
    if result is not None:
        # AgentResultオブジェクトの場合、output_textやcontentを取得
        if hasattr(result, "output_text"):
            return str(result.output_text)
        if hasattr(result, "content"):
            return _stringify_response(result.content)
        if isinstance(result, dict):
            return _stringify_response(result)
        return _stringify_response(result)
    
    # 後方互換性のため、assistant_response もチェック
    assistant_event = event.get("assistant_response")
    if isinstance(assistant_event, dict):
        return _stringify_response(assistant_event)
    return ""
```

**評価:** ✅ **適切**
- `result`イベントをチェックしている（ドキュメントに準拠）
- `AgentResult`オブジェクトの処理も適切

**ドキュメント参照:**
> "Lifecycle Events: `result`: The final AgentResult"

### 4. ツールイベントの処理 ✅

**現在の実装:**
```python
# execution.py:63-77
def _render_tool_event(event: dict) -> None:
    if "current_tool_use" in event and event["current_tool_use"].get("name"):
        tool_name = event["current_tool_use"]["name"]
        data=_stringify_response(event["current_tool_use"])
        console.print()
        console.print(f"🔧 Using tool: {tool_name}")
        console.print(
            Panel(
                _stringify_response(data),
                title="Tool Update",
                border_style=COLORS["tool"],
            )
        )
    sys.stdout.flush()
```

**評価:** ✅ **適切**
- `current_tool_use`イベントをチェックしている（ドキュメントに準拠）
- ツール名とデータを適切に表示

**ドキュメント参照:**
> "Tool Events: `current_tool_use`: Information about the current tool being used, including: `toolUseId`, `name`, `input`"

### 5. ライフサイクルイベントの処理 ❌

**現在の実装:**
```python
# execution.py:124-146
def process_event(event):
    """Shared event processor for both async iterators and callback handlers"""
    # Track event loop lifecycle
    if event.get("init_event_loop", False):
        print("🔄 Event loop initialized")
    elif event.get("start_event_loop", False):
        print("▶️ Event loop cycle starting")
    elif "message" in event:
        print(f"📬 New message created: {event['message']['role']}")
    elif event.get("complete", False):
        print("✅ Cycle completed")
    elif event.get("force_stop", False):
        print(f"🛑 Event loop force-stopped: {event.get('force_stop_reason', 'unknown reason')}")
    
    # Track tool usage
    if "current_tool_use" in event and event["current_tool_use"].get("name"):
        tool_name = event["current_tool_use"]["name"]
        print(f"🔧 Using tool: {tool_name}")
    
    # Show text snippets
    if "data" in event:
        data_snippet = event["data"][:20] + ("..." if len(event["data"]) > 20 else "")
        print(f"📟 Text: {data_snippet}")
```

**評価:** ⚠️ **実装されているが使用されていない**
- ライフサイクルイベントの処理は実装されている
- しかし、`_stream_agent()`関数内でコメントアウトされているため、実際には使用されていない

**ドキュメント参照:**
> "Lifecycle Events: `init_event_loop`, `start_event_loop`, `message`, `force_stop`, `force_stop_reason`, `result`"

### 6. エラーハンドリング ✅

**現在の実装:**
```python
# execution.py:174-179
except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
    # エラー時はステータス表示をクリアしてからメッセージを表示
    console.print(
        f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
    )
    return await _invoke_agent(agent, prompt)
```

**評価:** ✅ **適切**
- ストリーミングが失敗した場合、非ストリーミング呼び出しにフォールバック
- ユーザーに警告を表示

### 7. 終了判定 ⚠️

**現在の実装:**
```python
# execution.py:154-172
async for event in agent.stream_async(prompt):
    if not isinstance(event, dict):
        continue
    
    if "result" in event:
        candidate = _extract_final_response(event)
        if candidate:
            final_response = candidate

combined = final_response or "".join(response_buffer)
return combined.strip() or None
```

**評価:** ⚠️ **改善の余地あり**

**問題点:**
1. **明示的な終了判定がない**: `async for`ループが自然に終了するまで待つ
2. **`response_buffer`が使用されていない**: `_render_model_delta()`がコメントアウトされているため、`response_buffer`にデータが追加されない
3. **最終結果の優先順位**: `final_response`があればそれを使用、なければ`response_buffer`を使用するが、`response_buffer`が空の可能性がある

**ドキュメント参照:**
> "The `result` event contains the final AgentResult. The async iterator will naturally terminate after all events are processed."

### 8. ストリーミング出力の表示 ❌

**現在の実装:**
```python
# execution.py:205-208
if hasattr(agent, "stream_async"):
    response_text = await _stream_agent(agent, final_input)
    # ストリーミング中に既に内容が表示されているため、改行のみ追加
    console.print()
```

**評価:** ❌ **問題あり**

**問題点:**
- `_stream_agent()`内で`_render_model_delta()`がコメントアウトされているため、ストリーミング中にリアルタイム表示が行われていない
- 最終結果のみが返されるが、ストリーミング中のテキストチャンクは表示されない
- ユーザーはストリーミングの進行状況を確認できない

## 主な問題点

### 1. ストリーミングイベントの処理がコメントアウトされている ⚠️⚠️⚠️

**現在の状態:**
```python
# イベントのデバッグ用関数を呼び出す
# process_event(event)

# _render_tool_event(event)
# モデルデルタをレンダリング（リアルタイム表示）
# _render_model_delta(event, response_buffer)
```

**影響:**
- ストリーミング中にリアルタイム表示が行われない
- ツール使用の表示が行われない
- ユーザーはストリーミングの進行状況を確認できない

**推奨修正:**
```python
async def _stream_agent(agent: Any, prompt: str) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # ツールイベントの表示
            _render_tool_event(event)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            _render_model_delta(event, response_buffer)

            # 最終結果の取得
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
            
        # 最終結果があればそれを使用、なければバッファから構築
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
```

### 2. ライフサイクルイベントの処理が使用されていない ⚠️

**推奨改善:**
- デバッグモードや詳細表示モードでライフサイクルイベントを表示
- エラー検出のため`force_stop`イベントをチェック

### 3. ツールストリーミングイベントの処理が未実装 ⚠️

**ドキュメント参照:**
> "Tool Events: `tool_stream_event`: Information about an event streamed from a tool"

**推奨実装:**
```python
def _render_tool_stream_event(event: dict) -> None:
    """Render tool streaming event."""
    tool_stream_event = event.get("tool_stream_event")
    if tool_stream_event:
        tool_use = tool_stream_event.get("tool_use", {})
        tool_name = tool_use.get("name", "unknown")
        data = tool_stream_event.get("data")
        
        if data:
            console.print(f"[dim]Tool '{tool_name}' streaming: {data}[/dim]")
            sys.stdout.flush()
```

## 改善推奨事項

### 優先度: 高

1. **ストリーミングイベントの処理を有効化**
   - `_render_tool_event()`と`_render_model_delta()`のコメントアウトを解除
   - リアルタイム表示を復元

2. **`response_buffer`の使用を修正**
   - `_render_model_delta()`が有効になれば、`response_buffer`にデータが追加される
   - 最終結果の優先順位を明確化

### 優先度: 中

3. **ライフサイクルイベントの処理**
   - デバッグモードでライフサイクルイベントを表示
   - `force_stop`イベントをチェックしてエラーを検出

4. **ツールストリーミングイベントの処理**
   - `tool_stream_event`の処理を追加
   - ツールからのストリーミングデータを表示

### 優先度: 低

5. **タイムアウト処理の追加**
   - 長時間実行されるストリーミングのタイムアウト処理

6. **進捗表示の改善**
   - ストリーミングの進捗を視覚的に表示

## 結論

現在の実装は、Strand Agentsのドキュメントに概ね準拠していますが、**ストリーミングイベントの処理がコメントアウトされているため、実際にはストリーミング機能が動作していません**。

主な問題点:
- ✅ Async Iteratorパターンの使用は適切
- ✅ イベントタイプの処理は適切に実装されている
- ❌ **ストリーミングイベントの処理がコメントアウトされている（最重要）**
- ⚠️ ライフサイクルイベントの処理が使用されていない
- ⚠️ ツールストリーミングイベントの処理が未実装

**最優先の改善:**
ストリーミングイベントの処理を有効化することで、リアルタイム表示機能を復元する必要があります。

## 参考資料

- [Strand Agents Streaming Overview](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/overview/index.md)
- [Async Iterators Documentation](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/async-iterators/index.md)
- [Callback Handlers Documentation](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/streaming/callback-handlers/index.md)

