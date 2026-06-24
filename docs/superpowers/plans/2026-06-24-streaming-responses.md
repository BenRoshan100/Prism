# Streaming Responses Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace blocking `POST /api/chat` JSON response with SSE streaming so LLM tokens appear in the UI within ~1s instead of 8–15s.

**Architecture:** Backend adds `stream_query_with_web()` async generator in `chain.py` that calls `llm.astream()`. Route returns `StreamingResponse(text/event-stream)` yielding typed JSON events: `token` per chunk, `done` with sources. Frontend uses `fetch` + `ReadableStream` to parse SSE lines and appends tokens into a pre-placed assistant message.

**Tech Stack:** FastAPI `StreamingResponse`, LangChain `ChatGroq.astream()`, React `useState` functional updates, native `fetch` + `ReadableStream` (axios dropped for streaming call only).

## Global Constraints

- Python 3.11+. FastAPI + LangChain already installed — no new dependencies.
- SSE format: each event is `data: <json>\n\n` (double newline terminator).
- `run_query_with_web()` in `chain.py` must NOT be modified — eval script uses it.
- Memory (`save_context`) must be called after all tokens collected, not mid-stream.
- `gc.collect()` and `log_memory_mb()` calls must be preserved in chat route.
- Frontend: `sendMessage` in `api.js` must remain exported (other callers may use it). Add `streamChat` alongside it.

---

### Task 1: `stream_query_with_web` async generator in chain.py

**Files:**
- Modify: `server/chain.py`
- Test: `tests/test_streaming.py`

**Interfaces:**
- Produces: `stream_query_with_web(retriever, memory, question: str, web_sources: list[dict]) -> AsyncGenerator[dict, None]`
- Yields dicts: `{"type":"token","content":str}`, `{"type":"done","sources":list[dict],"retrieval_method":str}`, `{"type":"error","message":str}`

- [ ] **Step 1: Write failing test**

Create `tests/test_streaming.py`:

```python
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.documents import Document


def make_mock_retriever(docs=None):
    retriever = MagicMock()
    if docs is None:
        docs = [Document(page_content="test content", metadata={"source": "test.pdf", "page": 1})]
    retriever.invoke.return_value = docs
    return retriever


def make_mock_memory(history=None):
    memory = MagicMock()
    memory.load_memory_variables.return_value = {"chat_history": history or []}
    return memory


async def collect_events(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_stream_yields_tokens_then_done():
    from server.chain import stream_query_with_web

    retriever = make_mock_retriever()
    memory = make_mock_memory()

    mock_chunk1 = MagicMock()
    mock_chunk1.content = "Hello "
    mock_chunk2 = MagicMock()
    mock_chunk2.content = "world."

    async def fake_astream(messages):
        for chunk in [mock_chunk1, mock_chunk2]:
            yield chunk

    with patch("server.chain._create_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.astream = fake_astream
        mock_llm_factory.return_value = mock_llm

        events = await collect_events(
            stream_query_with_web(retriever, memory, "test question", [])
        )

    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]

    assert len(token_events) == 2
    assert token_events[0]["content"] == "Hello "
    assert token_events[1]["content"] == "world."
    assert len(done_events) == 1
    assert done_events[0]["retrieval_method"] == "hybrid+rerank+web"
    assert isinstance(done_events[0]["sources"], list)


@pytest.mark.asyncio
async def test_stream_yields_error_on_llm_failure():
    from server.chain import stream_query_with_web

    retriever = make_mock_retriever()
    memory = make_mock_memory()

    async def failing_astream(messages):
        raise RuntimeError("LLM exploded")
        yield  # make it a generator

    with patch("server.chain._create_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.astream = failing_astream
        mock_llm_factory.return_value = mock_llm

        events = await collect_events(
            stream_query_with_web(retriever, memory, "test question", [])
        )

    assert events[0]["type"] == "error"
    assert "LLM exploded" in events[0]["message"]


@pytest.mark.asyncio
async def test_stream_saves_memory_after_tokens():
    from server.chain import stream_query_with_web

    retriever = make_mock_retriever()
    memory = make_mock_memory()

    mock_chunk = MagicMock()
    mock_chunk.content = "answer text"

    async def fake_astream(messages):
        yield mock_chunk

    with patch("server.chain._create_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.astream = fake_astream
        mock_llm_factory.return_value = mock_llm

        await collect_events(
            stream_query_with_web(retriever, memory, "test question", [])
        )

    memory.save_context.assert_called_once_with(
        {"input": "test question"}, {"answer": "answer text"}
    )
```

- [ ] **Step 2: Install pytest-asyncio if needed, run test to confirm it fails**

```bash
pip install pytest-asyncio
pytest tests/test_streaming.py -v
```

Expected: `ImportError: cannot import name 'stream_query_with_web'`

- [ ] **Step 3: Add `stream_query_with_web` to `server/chain.py`**

Add after the existing imports at the top of `chain.py`:
```python
from typing import AsyncGenerator
```

Add this function after `run_query_with_web` (before `_get_api_key`):

```python
async def stream_query_with_web(
    retriever, memory, question: str, web_sources: list[dict]
) -> AsyncGenerator[dict, None]:
    """
    Streaming variant of run_query_with_web. Yields token/done/error dicts.
    run_query_with_web is preserved unchanged for eval script compatibility.
    """
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    # RAG retrieval
    rag_docs_lc = retriever.invoke(question)
    rag_docs = []
    for doc in rag_docs_lc:
        rag_docs.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "page": doc.metadata.get("page", None),
            "chunk_index": doc.metadata.get("chunk_index", None),
            "citation_index": doc.metadata.get("citation_index"),
            "similarity_score": doc.metadata.get("similarity_score"),
            "bm25_score": doc.metadata.get("bm25_score"),
            "rrf_score": doc.metadata.get("rrf_score"),
            "rerank_score": doc.metadata.get("rerank_score"),
        })

    # Build combined context string
    rag_ctx = "\n\n".join(
        f"[Doc: {d['source']}]\n{d['content']}" for d in rag_docs
    ) or "No document context."
    if web_sources:
        web_ctx = "\n\n".join(
            f"[Web: {w['title']} | {w['url']}]\n{w['content']}" for w in web_sources
        )
        combined = f"=== Document context ===\n{rag_ctx}\n\n=== Web search results ===\n{web_ctx}"
    else:
        combined = rag_ctx

    config = load_config()
    llm = _create_llm(config.get("llm", {}))

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    history = memory.load_memory_variables({}).get("chat_history", [])
    for msg in history:
        if hasattr(msg, "type"):
            if msg.type == "human":
                messages.append(HumanMessage(content=msg.content))
            else:
                messages.append(AIMessage(content=msg.content))
    messages.append(
        HumanMessage(content=f"Context:\n{combined}\n\nQuestion: {question}\n\nAnswer:")
    )

    full_answer_parts: list[str] = []
    try:
        async for chunk in llm.astream(messages):
            if chunk.content:
                full_answer_parts.append(chunk.content)
                yield {"type": "token", "content": chunk.content}
    except Exception as e:
        yield {"type": "error", "message": str(e)}
        return

    answer = "".join(full_answer_parts)
    memory.save_context({"input": question}, {"answer": answer})
    logger.info(
        "stream_query_with_web | rag=%d web=%d history=%d",
        len(rag_docs), len(web_sources), len(history),
    )

    yield {
        "type": "done",
        "sources": rag_docs,
        "retrieval_method": "hybrid+rerank+web",
    }
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_streaming.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add server/chain.py tests/test_streaming.py
git commit -m "feat: add stream_query_with_web async generator to chain.py"
```

---

### Task 2: StreamingResponse in routes/chat.py

**Files:**
- Modify: `server/routes/chat.py`

**Interfaces:**
- Consumes: `stream_query_with_web(retriever, memory, question, web_sources)` from Task 1
- `POST /api/chat` now returns `text/event-stream` instead of JSON. Frontend must use `fetch` not axios.

- [ ] **Step 1: Replace the chat route**

Full replacement of `server/routes/chat.py`:

```python
import gc
import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.chain import stream_query_with_web, condense_question
from server.memory import clear_memory
from server.utils import setup_logger, log_memory_mb

logger = setup_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    web_search: bool = True


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    workspace: str = Query("default"),
):
    chain = request.app.state.chain
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        from server.retriever import get_retriever as _get_retriever
        retriever = _get_retriever(workspace)

    eval_log = request.app.state.eval_log
    memory = request.app.state.memory

    async def generate():
        if chain is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No documents uploaded yet. Please upload documents first.'})}\n\n"
            return

        log_memory_mb(logger, "chat-start")
        logger.info("QUERY | workspace=%s | %s", workspace, body.question[:100])

        web_sources = []
        try:
            from server.web_search import search_web
            search_query = condense_question(body.question, memory)
            web_sources = search_web(search_query)
        except Exception as e:
            logger.warning("Web search failed: %s", e)

        full_answer_parts: list[str] = []

        try:
            async for event in stream_query_with_web(retriever, memory, body.question, web_sources):
                if event["type"] == "token":
                    full_answer_parts.append(event["content"])
                    yield f"data: {json.dumps(event)}\n\n"

                elif event["type"] == "done":
                    all_sources = event["sources"] + web_sources
                    for i, src in enumerate(all_sources):
                        if not src.get("citation_index"):
                            src["citation_index"] = i + 1
                    done_payload = {
                        "type": "done",
                        "sources": all_sources,
                        "retrieval_method": event["retrieval_method"],
                    }
                    yield f"data: {json.dumps(done_payload)}\n\n"
                    eval_log.append({
                        "query": body.question,
                        "answer": "".join(full_answer_parts),
                        "contexts": [s["content"] for s in all_sources],
                    })
                    logger.info(
                        "RESPONSE | workspace=%s | rag=%d | web=%d",
                        workspace, len(event["sources"]), len(web_sources),
                    )

                elif event["type"] == "error":
                    yield f"data: {json.dumps(event)}\n\n"
                    return

        except Exception as e:
            logger.error("Streaming chat error: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            gc.collect()
            log_memory_mb(logger, "chat-end")

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/chat/memory")
async def clear_chat_memory(request: Request):
    """Clear conversation memory for a new conversation."""
    memory = request.app.state.memory
    clear_memory(memory)
    return {"status": "cleared"}
```

- [ ] **Step 2: Smoke-test the backend manually**

Start the backend:
```bash
cd server
uvicorn main:app --reload --port 8000
```

In a separate terminal (after uploading docs via the frontend), run:
```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is UPI?"}' \
  --no-buffer
```

Expected: Stream of `data: {"type":"token",...}` lines appearing one by one, ending with `data: {"type":"done",...}`.

- [ ] **Step 3: Commit**

```bash
git add server/routes/chat.py
git commit -m "feat: stream POST /api/chat via SSE StreamingResponse"
```

---

### Task 3: `streamChat` in api.js

**Files:**
- Modify: `frontend/src/api.js`

**Interfaces:**
- Produces: `streamChat(question: string, workspaceId: string, callbacks: {onToken, onDone, onError}): Promise<void>`
  - `onToken(content: string): void`
  - `onDone(event: {type:"done", sources: Array, retrieval_method: string}): void`
  - `onError(message: string): void`
- `sendMessage` export preserved (kept for backward compat, not removed).

- [ ] **Step 1: Add `streamChat` to `frontend/src/api.js`**

Add after the existing `sendMessage` function (do NOT remove `sendMessage`):

```javascript
const API_BASE = import.meta.env.VITE_API_URL || "/api";

export async function streamChat(question, workspaceId = "default", { onToken, onDone, onError }) {
  let response;
  try {
    response = await fetch(
      `${API_BASE}/chat?workspace=${encodeURIComponent(workspaceId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      }
    );
  } catch (err) {
    onError(err.message || "Network error");
    return;
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    onError(text || `HTTP ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? ""; // keep incomplete line
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.type === "token") onToken(event.content);
          else if (event.type === "done") onDone(event);
          else if (event.type === "error") onError(event.message ?? "Unknown error");
        } catch {
          // malformed SSE line — skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

- [ ] **Step 2: Verify file looks correct**

```bash
head -70 frontend/src/api.js
```

Expected: Both `sendMessage` and `streamChat` exported. `API_BASE` const present.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat: add streamChat SSE client to api.js"
```

---

### Task 4: Streaming UI in ChatArea.jsx + MessageBubble.jsx

**Files:**
- Modify: `frontend/src/components/ChatArea.jsx`
- Modify: `frontend/src/components/MessageBubble.jsx`

**Interfaces:**
- Consumes: `streamChat(question, workspaceId, {onToken, onDone, onError})` from Task 3
- Message shape: `{id?: string, role: "user"|"assistant", content: string, sources?: Array, retrieval_method?: string, loading?: boolean}`

- [ ] **Step 1: Update `MessageBubble.jsx` to show streaming cursor**

Add a blinking cursor when `message.loading === true`. Replace the existing `<p>` block for assistant messages:

```jsx
export default function MessageBubble({ message }) {
  const isUser = message.role === "user";

  function handleCitationClick(idx) {
    const el = document.getElementById(`source-${idx}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-2xl px-5 py-3.5 ${
          isUser
            ? "bg-indigo-600 text-white"
            : "bg-white text-gray-800 shadow-sm"
        }`}
      >
        <p className="text-sm whitespace-pre-wrap leading-relaxed">
          {isUser ? (
            message.content
          ) : message.loading && !message.content ? (
            <span className="inline-flex items-center gap-1 text-indigo-400">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" />
            </span>
          ) : (
            <>
              <CitedText text={message.content} onCitationClick={handleCitationClick} />
              {message.loading && (
                <span className="inline-block w-0.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-middle" />
              )}
            </>
          )}
        </p>

        {!isUser && !message.loading && message.sources && (
          <WebSourcesList sources={message.sources} />
        )}

        {!isUser && !message.loading && message.sources && (
          <SourceExpander sources={message.sources} />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Replace `ChatArea.jsx` with streaming version**

Full replacement of `frontend/src/components/ChatArea.jsx`:

```jsx
import { useState, useEffect, useRef } from "react";
import { streamChat } from "../api";
import MessageBubble from "./MessageBubble";

export default function ChatArea({ onEvalEntry, hasDocuments, suggestedQuestion, onSuggestedQuestionUsed, currentWorkspace = "default" }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (suggestedQuestion) {
      setInput(suggestedQuestion);
      onSuggestedQuestionUsed?.();
    }
  }, [suggestedQuestion, onSuggestedQuestionUsed]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim() || loading || !hasDocuments) return;

    const question = input.trim();
    setInput("");
    const msgId = crypto.randomUUID();
    const tokenBuffer = [];

    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { id: msgId, role: "assistant", content: "", sources: [], loading: true },
    ]);
    setLoading(true);

    await streamChat(question, currentWorkspace, {
      onToken: (token) => {
        tokenBuffer.push(token);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId ? { ...m, content: m.content + token } : m
          )
        );
      },
      onDone: (event) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? {
                  ...m,
                  sources: event.sources ?? [],
                  retrieval_method: event.retrieval_method,
                  loading: false,
                }
              : m
          )
        );
        onEvalEntry?.({ query: question, answer: tokenBuffer.join("") });
      },
      onError: (message) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? { ...m, content: `Error: ${message}`, loading: false }
              : m
          )
        );
      },
    });

    setLoading(false);
  }

  return (
    <div className="flex-1 flex flex-col bg-gray-50">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <svg
              className="w-16 h-16 text-indigo-200 mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1"
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <p className="text-lg font-medium text-gray-500 mb-1">
              {hasDocuments
                ? "Ask a question about your documents"
                : "Upload documents to get started"}
            </p>
            <p className="text-sm text-gray-400">
              {hasDocuments
                ? "Prism will find answers and cite sources"
                : "Drop PDF, TXT, CSV files or paste a URL in the sidebar"}
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={msg.id ?? i} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="p-4 bg-white border-t border-gray-100">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              hasDocuments
                ? "Ask anything — searching docs + web..."
                : "Upload documents first to start chatting"
            }
            className="flex-1 px-4 py-3 border border-gray-200 rounded-xl text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400 transition-shadow"
            disabled={loading || !hasDocuments}
          />
          <button
            type="submit"
            disabled={loading || !input.trim() || !hasDocuments}
            className="px-6 py-3 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:bg-indigo-200 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            {loading ? "..." : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Start dev server and manually test**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. Upload a document. Ask a question. Verify:
- Bouncing dots appear immediately while condense+search runs (~500ms)
- Tokens start appearing in the bubble
- Blinking cursor shows at end of partial answer
- Sources section appears after answer completes
- Input re-enables after done

- [ ] **Step 4: Test error path**

Stop the backend (`Ctrl+C` on uvicorn). Submit a question. Verify:
- Bouncing dots appear briefly
- Error message appears inline in the assistant bubble: `Error: Network error` or similar
- Input re-enables, user can retry

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatArea.jsx frontend/src/components/MessageBubble.jsx
git commit -m "feat: stream tokens into chat UI via SSE"
```

---

### Task 5: Final integration commit

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests one final time**

```bash
pytest tests/test_streaming.py tests/test_ingest.py -v
```

Expected: All tests PASS.

- [ ] **Step 2: Verify curl smoke test still works**

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is UPI?"}' \
  --no-buffer
```

Expected: Token stream followed by done event with sources.

- [ ] **Step 3: Update evolution.md**

Append to `docs/evolution.md` under Current State Snapshot:

```
Streaming: POST /api/chat returns SSE stream. token events per LLM chunk, done event with
           sources + retrieval_method. Frontend streams tokens into pre-placed assistant
           bubble. Bouncing dots while condense+search runs, blinking cursor during generation.
```

- [ ] **Step 4: Final commit**

```bash
git add docs/evolution.md
git commit -m "docs: update evolution.md with streaming responses (Stage 14)"
```
