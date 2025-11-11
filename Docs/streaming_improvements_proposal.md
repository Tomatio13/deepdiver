# ストリーミング実装改善提案

## 1. ストリーミングイベントの処理を有効化（最優先）

### 現在の問題

ストリーミングイベントの処理がコメントアウトされているため、リアルタイム表示が行われていません。

### 改善案

```python
# execution.py の改善版

async def _stream_agent(agent: Any, prompt: str) -> str | None:
    """Stream agent response and render events in real-time."""
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
        # 注意: resultイベントのoutput_textにはストリーミングされた全テキストが含まれるため、
        # 通常はfinal_responseを使用する
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        # エラー時はステータス表示をクリアしてからメッセージを表示
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
        return await _invoke_agent(agent, prompt)
```

## 2. ライフサイクルイベントの処理を追加

### 改善案

```python
# execution.py に追加

def _render_lifecycle_event(event: dict, debug_mode: bool = False) -> None:
    """Render lifecycle events (for debugging)."""
    if not debug_mode:
        return
    
    # Track event loop lifecycle
    if event.get("init_event_loop", False):
        console.print("[dim]🔄 Event loop initialized[/dim]")
    elif event.get("start_event_loop", False):
        console.print("[dim]▶️ Event loop cycle starting[/dim]")
    elif "message" in event:
        role = event["message"].get("role", "unknown")
        console.print(f"[dim]📬 New message created: {role}[/dim]")
    elif event.get("complete", False):
        console.print("[dim]✅ Cycle completed[/dim]")
    elif event.get("force_stop", False):
        reason = event.get("force_stop_reason", "unknown reason")
        console.print(f"[yellow]🛑 Event loop force-stopped: {reason}[/yellow]")
        sys.stdout.flush()

async def _stream_agent(agent: Any, prompt: str, debug_mode: bool = False) -> str | None:
    """Stream agent response and render events in real-time."""
    response_buffer: list[str] = []
    final_response = ""
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # ライフサイクルイベントの表示（デバッグモードのみ）
            _render_lifecycle_event(event, debug_mode)

            # ツールイベントの表示
            _render_tool_event(event)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            _render_model_delta(event, response_buffer)

            # 最終結果の取得
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
            
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
        return await _invoke_agent(agent, prompt)
```

## 3. ツールストリーミングイベントの処理を追加

### 改善案

```python
# execution.py に追加

def _render_tool_stream_event(event: dict) -> None:
    """Render tool streaming event."""
    tool_stream_event = event.get("tool_stream_event")
    if not tool_stream_event:
        return
    
    tool_use = tool_stream_event.get("tool_use", {})
    tool_name = tool_use.get("name", "unknown")
    data = tool_stream_event.get("data")
    
    if data:
        # ツールからのストリーミングデータを表示
        console.print(
            f"[dim]🔧 Tool '{tool_name}' streaming: {data}[/dim]",
            end=""
        )
        sys.stdout.flush()

async def _stream_agent(agent: Any, prompt: str, debug_mode: bool = False) -> str | None:
    """Stream agent response and render events in real-time."""
    response_buffer: list[str] = []
    final_response = ""
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # ライフサイクルイベントの表示（デバッグモードのみ）
            _render_lifecycle_event(event, debug_mode)

            # ツールイベントの表示
            _render_tool_event(event)
            
            # ツールストリーミングイベントの表示
            _render_tool_stream_event(event)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            _render_model_delta(event, response_buffer)

            # 最終結果の取得
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
            
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
        return await _invoke_agent(agent, prompt)
```

## 4. エラーハンドリングの改善

### 改善案

```python
# execution.py の改善版

async def _stream_agent(agent: Any, prompt: str, debug_mode: bool = False) -> str | None:
    """Stream agent response and render events in real-time."""
    response_buffer: list[str] = []
    final_response = ""
    force_stopped = False
    
    try:
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # 強制停止イベントのチェック
            if event.get("force_stop", False):
                force_stopped = True
                reason = event.get("force_stop_reason", "unknown reason")
                console.print(
                    f"\n[yellow]⚠️ Stream force-stopped: {reason}[/yellow]"
                )
                # 強制停止後も既存のデータを返す

            # ライフサイクルイベントの表示（デバッグモードのみ）
            _render_lifecycle_event(event, debug_mode)

            # ツールイベントの表示
            _render_tool_event(event)
            
            # ツールストリーミングイベントの表示
            _render_tool_stream_event(event)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            _render_model_delta(event, response_buffer)

            # 最終結果の取得
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
            
        # 強制停止された場合でも、取得できたデータを返す
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except KeyboardInterrupt:
        # Ctrl+Cで中断された場合
        console.print("\n[yellow]Stream interrupted by user[/yellow]")
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        # エラー時はステータス表示をクリアしてからメッセージを表示
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
        return await _invoke_agent(agent, prompt)
```

## 5. タイムアウト処理の追加（オプション）

### 改善案

```python
# execution.py の改善版（タイムアウト対応）

import asyncio

async def _stream_agent(
    agent: Any, 
    prompt: str, 
    debug_mode: bool = False,
    timeout: float | None = None
) -> str | None:
    """Stream agent response and render events in real-time.
    
    Args:
        agent: Strands Agent instance
        prompt: User prompt
        debug_mode: Enable debug output for lifecycle events
        timeout: Timeout in seconds (None for no timeout)
    """
    response_buffer: list[str] = []
    final_response = ""
    force_stopped = False
    
    async def _stream():
        nonlocal final_response, force_stopped
        
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # 強制停止イベントのチェック
            if event.get("force_stop", False):
                force_stopped = True
                reason = event.get("force_stop_reason", "unknown reason")
                console.print(
                    f"\n[yellow]⚠️ Stream force-stopped: {reason}[/yellow]"
                )

            # ライフサイクルイベントの表示（デバッグモードのみ）
            _render_lifecycle_event(event, debug_mode)

            # ツールイベントの表示
            _render_tool_event(event)
            
            # ツールストリーミングイベントの表示
            _render_tool_stream_event(event)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            _render_model_delta(event, response_buffer)

            # 最終結果の取得
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
    
    try:
        if timeout is not None:
            async with asyncio.timeout(timeout):
                await _stream()
        else:
            await _stream()
            
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except asyncio.TimeoutError:
        console.print(
            f"\n[yellow]Stream timeout after {timeout}s[/yellow]"
        )
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except KeyboardInterrupt:
        console.print("\n[yellow]Stream interrupted by user[/yellow]")
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
        return await _invoke_agent(agent, prompt)
```

## 6. 完全な改善版の実装

### 完全な改善版

```python
# execution.py の完全な改善版

async def _stream_agent(
    agent: Any, 
    prompt: str, 
    debug_mode: bool = False,
    timeout: float | None = None
) -> str | None:
    """Stream agent response and render events in real-time.
    
    This function implements the async iterator pattern for streaming agent events,
    following Strands Agents best practices.
    
    Args:
        agent: Strands Agent instance
        prompt: User prompt
        debug_mode: Enable debug output for lifecycle events
        timeout: Timeout in seconds (None for no timeout)
    
    Returns:
        Final response text, or None if no response was generated
    """
    response_buffer: list[str] = []
    final_response = ""
    force_stopped = False
    
    async def _process_stream():
        nonlocal final_response, force_stopped
        
        async for event in agent.stream_async(prompt):
            if not isinstance(event, dict):
                continue

            # 強制停止イベントのチェック
            if event.get("force_stop", False):
                force_stopped = True
                reason = event.get("force_stop_reason", "unknown reason")
                console.print(
                    f"\n[yellow]⚠️ Stream force-stopped: {reason}[/yellow]"
                )

            # ライフサイクルイベントの表示（デバッグモードのみ）
            _render_lifecycle_event(event, debug_mode)

            # ツールイベントの表示
            _render_tool_event(event)
            
            # ツールストリーミングイベントの表示
            _render_tool_stream_event(event)
            
            # モデルデルタをレンダリング（リアルタイム表示）
            _render_model_delta(event, response_buffer)

            # 最終結果の取得
            # 注意: resultイベントは複数回発生する可能性があるため、
            # 最新のものを保持する
            if "result" in event:
                candidate = _extract_final_response(event)
                if candidate:
                    final_response = candidate
    
    try:
        if timeout is not None:
            async with asyncio.timeout(timeout):
                await _process_stream()
        else:
            await _process_stream()
            
        # 最終結果があればそれを使用、なければバッファから構築
        # 注意: resultイベントのoutput_textにはストリーミングされた全テキストが含まれるため、
        # 通常はfinal_responseを使用する
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
            
    except asyncio.TimeoutError:
        console.print(
            f"\n[yellow]Stream timeout after {timeout}s[/yellow]"
        )
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except KeyboardInterrupt:
        console.print("\n[yellow]Stream interrupted by user[/yellow]")
        combined = final_response or "".join(response_buffer)
        return combined.strip() or None
    except Exception as exc:  # noqa: BLE001 - fall back to non-streaming
        console.print(
            f"\n[yellow]Streaming unavailable, falling back to blocking call ({exc}).[/yellow]"
        )
        return await _invoke_agent(agent, prompt)
```

## 実装の優先順位

1. **最優先**: ストリーミングイベントの処理を有効化
   - `_render_tool_event()`と`_render_model_delta()`のコメントアウトを解除
   - これにより、リアルタイム表示機能が復元される

2. **高**: エラーハンドリングの改善
   - `force_stop`イベントの処理
   - `KeyboardInterrupt`の処理

3. **中**: ライフサイクルイベントの処理
   - デバッグモードでの表示

4. **中**: ツールストリーミングイベントの処理
   - `tool_stream_event`の処理を追加

5. **低**: タイムアウト処理の追加
   - 長時間実行されるストリーミングのタイムアウト処理

## 注意事項

1. **`result`イベントの処理**
   - `result`イベントには最終的な`AgentResult`が含まれる
   - `AgentResult.output_text`にはストリーミングされた全テキストが含まれる
   - 通常は`final_response`を使用するが、`response_buffer`もフォールバックとして保持

2. **ストリーミングの終了**
   - `async for`ループは自然に終了する（`StopAsyncIteration`が発生）
   - 明示的な終了イベントは存在しない
   - `result`イベントが来ても、ループは継続する（後続のイベントがある可能性があるため）

3. **パフォーマンス**
   - `sys.stdout.flush()`を呼び出すことで、リアルタイム表示を実現
   - ただし、過度な`flush()`呼び出しはパフォーマンスに影響する可能性がある

