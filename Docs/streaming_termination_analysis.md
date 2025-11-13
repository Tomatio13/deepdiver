# ストリーミング終了判定の分析

## 現在の実装

### `_stream_agent`関数の終了判定

```python
async def _stream_agent(agent: Any, prompt: str) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            _render_tool_event(event)
            _render_model_delta(event, response_buffer)

            candidate = _extract_final_response(event)
            if candidate:
                final_response = candidate

        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
```

### 終了判定の方法

**現在の方法**:
- `async for`ループが自然に終了する（`StopAsyncIteration`が発生する）ことで終了判定
- `assistant_response`イベントが来た時点で`final_response`に保存するが、ループは継続
- ループ終了後、`final_response`があればそれを使用、なければ`response_buffer`を使用

## 問題点

### 1. 明示的な終了判定がない
- `assistant_response`イベントが来た時点で早期終了していない
- ループが自然に終了するまで待つため、不要なイベント処理が続く可能性がある

### 2. 終了イベントの検出が不十分
- ストリーミングの完了を示す明示的なイベントをチェックしていない
- エラーやタイムアウトなどの異常終了を検出していない

### 3. 最終応答の優先順位
- `final_response`と`response_buffer`のどちらを使うかの判定が単純
- `assistant_response`イベントが来た後も`response_buffer`に追加される可能性がある

## 改善提案

### 1. 明示的な終了判定の追加

```python
async def _stream_agent(agent: Any, prompt: str) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    stream_completed = False
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # 終了イベントのチェック
            if event.get("stream_end") or event.get("done"):
                stream_completed = True
                break

            _render_tool_event(event)
            _render_model_delta(event, response_buffer)

            candidate = _extract_final_response(event)
            if candidate:
                final_response = candidate
                # assistant_responseが来たら早期終了を検討
                # （ただし、ツールストリーミングが続く可能性があるため、慎重に）

        # ストリーミングが正常に完了したかチェック
        if not stream_completed:
            # ループが自然に終了した場合も正常終了とみなす
            pass

        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:
        # エラーハンドリング
        ...
```

### 2. イベントタイプの明示的なチェック

```python
async def _stream_agent(agent: Any, prompt: str) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            event_type = event.get("type") or event.get("event_type")
            
            # 終了イベントのチェック
            if event_type in ("stream_end", "done", "complete", "finish"):
                break
            
            # ツールストリーミングイベント
            if "tool_stream_event" in event:
                _render_tool_event(event)
            
            # モデルストリーミングイベント
            if "model_stream_event" in event:
                _render_model_delta(event, response_buffer)
            
            # 最終応答イベント
            if "assistant_response" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate

        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:
        ...
```

### 3. タイムアウト処理の追加

```python
import asyncio

async def _stream_agent(agent: Any, prompt: str, timeout: float = 300.0) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    
    try:
        async with asyncio.timeout(timeout):
            async for event in agent.stream_async(prompt):
                # イベント処理
                ...
    except asyncio.TimeoutError:
        console.print(f"\n[yellow]Streaming timeout after {timeout}s[/yellow]")
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:
        ...
```

### 4. より堅牢な終了判定

```python
async def _stream_agent(agent: Any, prompt: str) -> str | None:
    response_buffer: list[str] = []
    final_response = ""
    last_event_time = asyncio.get_event_loop().time()
    idle_timeout = 30.0  # 30秒間イベントが来なければタイムアウト
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            last_event_time = asyncio.get_event_loop().time()
            
            _render_tool_event(event)
            _render_model_delta(event, response_buffer)

            candidate = _extract_final_response(event)
            if candidate:
                final_response = candidate
                # assistant_responseが来た後、一定時間待って終了
                # （ツールストリーミングが続く可能性があるため）

        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:
        ...
```

## 推奨される改善

1. **明示的な終了イベントのチェック**: ストリーミングの完了を示すイベントを明示的にチェック
2. **早期終了の検討**: `assistant_response`イベントが来た後、適切なタイミングで早期終了
3. **タイムアウト処理**: ストリーミングが長時間続く場合のタイムアウト処理
4. **イベントタイプの明示的な処理**: イベントタイプに基づいた処理の分岐

## 実装上の注意点

- `assistant_response`イベントが来ても、ツールストリーミングが続く可能性がある
- 早期終了する場合は、ツールストリーミングの完了を待つ必要がある
- タイムアウト処理を追加する場合は、ユーザー体験を損なわないように注意


