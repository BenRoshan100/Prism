# Streaming Responses — Design Spec
**Date:** 2026-06-24
**Status:** Approved

---

## Problem

`POST /api/chat` blocks 8–15s before returning a full JSON response. Users see a blank spinner. Streaming tokens as they arrive reduces perceived latency to ~1s first token.

---

## Approach

SSE (Server-Sent Events) over `POST /api/chat`. Backend returns `StreamingResponse(text/event-stream)`. Frontend uses `fetch` + `ReadableStream` (not `EventSource` — EventSource doesn't support POST bodies).

Answer tokens stream first. Sources + metadata arrive in a final `done` event after answer completes.

---

## SSE Event Format

```
data: {"type":"token","content":"The "}

data: {"type":"token","content":"answer is..."}

data: {"type":"done","sources":[...],"retrieval_method":"hybrid+rerank+web"}

data: {"type":"error","message":"LLM call failed"}
```

---

## Data Flow

```
POST /api/chat
  │
  ├─ condense_question()     ← sync, ~200ms, existing fn
  ├─ search_web()            ← sync, ~300ms, existing fn
  ├─ retriever.invoke()      ← sync, ~100ms, inside stream_query_with_web
  │
  └─ stream_query_with_web() ← async generator
       │
       ├─ llm.astream(messages) → yield token events
       ├─ collect full answer
       ├─ memory.save_context()
       ├─ eval_log.append()
       └─ yield done event with sources
```

---

## Backend Changes

### `server/chain.py`
Add `stream_query_with_web()` as an async generator alongside existing `run_query_with_web()`.

```python
async def stream_query_with_web(
    retriever, memory, question: str, web_sources: list[dict]
) -> AsyncGenerator[dict, None]:
    # 1. RAG retrieval (same as run_query_with_web)
    # 2. Build messages (same as run_query_with_web)
    # 3. async for chunk in llm.astream(messages): yield {"type":"token","content":chunk.content}
    # 4. After loop: memory.save_context(), yield {"type":"done","sources":rag_docs}
```

- `run_query_with_web` kept unchanged (used by eval script).
- Memory saved after full answer assembled (not mid-stream).
- On exception: yield `{"type":"error","message":str(e)}`.

### `server/routes/chat.py`
Replace `return {...}` with `StreamingResponse`.

```python
async def generate():
    # condense + search (sync, before streaming starts)
    # call stream_query_with_web
    # for each event: yield f"data: {json.dumps(event)}\n\n"
    # on done event: augment with web_sources, retrieval_method, citation_index

return StreamingResponse(generate(), media_type="text/event-stream")
```

- No-docs case: yield error event instead of raising `HTTPException` (HTTPException inside a StreamingResponse generator is swallowed).
- `gc.collect()` + `log_memory_mb()` calls moved to after generator completes (inside `generate()` finally block).

---

## Frontend Changes

### `frontend/src/api.js`
Add `streamChat(question, workspace, {onToken, onDone, onError})` function.

```javascript
async function streamChat(question, workspace, { onToken, onDone, onError }) {
  const response = await fetch(`${API_BASE}/api/chat?workspace=${workspace}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const event = JSON.parse(line.slice(6));
      if (event.type === 'token') onToken(event.content);
      else if (event.type === 'done') onDone(event);
      else if (event.type === 'error') onError(event.message);
    }
  }
}
```

Old `sendMessage` function removed or replaced.

### `frontend/src/components/ChatArea.jsx`
On submit:
1. Add user message to state immediately.
2. Add empty assistant message with `loading: true`.
3. Call `streamChat()`:
   - `onToken`: append content to that message via `setMessages`.
   - `onDone`: set sources, retrieval_method, loading=false.
   - `onError`: set error text, loading=false.

```javascript
const msgId = crypto.randomUUID();
setMessages(prev => [...prev, 
  { role: 'user', content: question },
  { id: msgId, role: 'assistant', content: '', sources: [], loading: true }
]);

await streamChat(question, workspace, {
  onToken: (t) => setMessages(prev => prev.map(m =>
    m.id === msgId ? { ...m, content: m.content + t } : m
  )),
  onDone: (evt) => setMessages(prev => prev.map(m =>
    m.id === msgId ? { ...m, sources: evt.sources, retrieval_method: evt.retrieval_method, loading: false } : m
  )),
  onError: (msg) => setMessages(prev => prev.map(m =>
    m.id === msgId ? { ...m, content: msg || 'Error generating response.', loading: false } : m
  )),
});
```

---

## Files Changed

| File | Change |
|------|--------|
| `server/chain.py` | Add `stream_query_with_web()` async generator |
| `server/routes/chat.py` | Return `StreamingResponse`, move gc/log to finally block |
| `frontend/src/api.js` | Add `streamChat()`, remove old `sendMessage` |
| `frontend/src/components/ChatArea.jsx` | Stream tokens into message state |

---

## Edge Cases

| Case | Handling |
|------|----------|
| No documents uploaded | Yield error event (HTTPException can't be raised inside StreamingResponse generator) |
| LLM error mid-stream | try/except in generator → yield error event, partial answer shown |
| User navigates away | Reader cancelled, generator stops, memory not saved (acceptable) |
| Empty token chunks | `if not chunk.content: continue` guard in stream loop |

---

## What Stays Unchanged

- `run_query_with_web()` in chain.py — kept for eval script compatibility
- `condense_question()` — unchanged, called sync before streaming
- Memory architecture — `save_context()` still called, just deferred to post-stream
- Source scoring (similarity, BM25, RRF, rerank) — unchanged, arrives in `done` event
- `DELETE /api/chat/memory` — unchanged
