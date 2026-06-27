# Metadata Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users click document chips in the sidebar to scope all retrieval to a subset of uploaded docs; no selection = current full-corpus behavior.

**Architecture:** `filter_docs: list[str] | None` flows from frontend sidebar chips → `ChatRequest` → `get_retriever_filtered()` (lightweight new instance reusing cached vectorstore) → ChromaDB `where` clause + BM25 in-memory pre-filter. Backend singleton cache untouched.

**Tech Stack:** Python 3.11, FastAPI, ChromaDB (`langchain_chroma`), `rank_bm25`, React 19, Tailwind CSS v4, `fetch` SSE streaming.

## Global Constraints

- Python 3.11+ only (`list[str] | None` union syntax, `set[str] | None`)
- No new Python dependencies — use existing `rank_bm25`, `langchain_chroma`, FastAPI
- No new npm packages
- All tests run with `pytest tests/ -v` from project root
- Follow existing test pattern: `unittest.mock.patch` for external calls, no live Chroma/Groq/Euron calls in unit tests
- Tailwind CSS v4 — use existing class names (`indigo-600`, `ring-2 ring-indigo-500`, etc.)
- `filter_docs: []` (empty list) treated identically to `null` — no filter applied

---

## File Map

| File | Change |
|------|--------|
| `server/bm25_index.py` | `search()` gets `filter_sources: set[str] \| None`; re-scores against filtered corpus |
| `server/ingest.py` | `load_documents` + `load_documents_from_paths` add `source_type` to metadata |
| `server/url_loader.py` | `load_url` adds `source_type = "url"` to metadata |
| `server/retriever.py` | `filter_docs` field on `HybridRetriever`; wire into dense + sparse; add `get_retriever_filtered()` |
| `server/routes/chat.py` | `filter_docs: list[str] \| None = None` on `ChatRequest`; pick retriever conditionally |
| `frontend/src/App.jsx` | `filterDocs` state; reset on workspace switch; pass to Sidebar + ChatArea |
| `frontend/src/components/Sidebar.jsx` | Doc list items become toggleable chips; accept `filterDocs` + `onFilterChange` props |
| `frontend/src/components/ChatArea.jsx` | Accept `filterDocs` prop; filter badge above input; pass to `streamChat` |
| `frontend/src/api.js` | `streamChat` accepts `filterDocs` param; includes `filter_docs` in request body |
| `tests/test_bm25_filter.py` | New — unit tests for `BM25Index.search` with `filter_sources` |
| `tests/test_source_type.py` | New — unit tests for `source_type` in loaded doc metadata |
| `tests/test_retriever_filter.py` | New — unit tests for `HybridRetriever` with `filter_docs` |

---

## Task 1: BM25 Filter

**Files:**
- Modify: `server/bm25_index.py`
- Create: `tests/test_bm25_filter.py`

**Interfaces:**
- Produces: `BM25Index.search(query: str, k: int = 20, filter_sources: set[str] | None = None) -> list[dict]`
  - When `filter_sources` is not None: scores only chunks whose `doc["source"]` is in `filter_sources`
  - Builds a temporary `BM25Okapi` over the filtered subset (so scores are relative to the filtered corpus, not the full index)
  - Returns `[]` if filtered corpus is empty

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bm25_filter.py`:

```python
import pytest
from server.bm25_index import BM25Index


@pytest.fixture
def index_with_two_docs():
    idx = BM25Index()
    idx.build([
        {"content": "UPI transaction volume grew in 2024", "source": "rbi.pdf", "page": 1, "chunk_index": 0},
        {"content": "NPCI reported record payments last quarter", "source": "npci.pdf", "page": 1, "chunk_index": 0},
        {"content": "UPI merchant limit revised to two lakh rupees", "source": "rbi.pdf", "page": 2, "chunk_index": 1},
    ])
    return idx


def test_search_no_filter_returns_all_sources(index_with_two_docs):
    results = index_with_two_docs.search("UPI transaction", k=10)
    sources = {r["source"] for r in results}
    assert "rbi.pdf" in sources
    assert "npci.pdf" in sources


def test_search_filter_restricts_to_source(index_with_two_docs):
    results = index_with_two_docs.search("UPI transaction", k=10, filter_sources={"rbi.pdf"})
    assert all(r["source"] == "rbi.pdf" for r in results)
    assert len(results) == 2  # two rbi.pdf chunks scored > 0


def test_search_filter_empty_set_returns_empty(index_with_two_docs):
    results = index_with_two_docs.search("UPI", k=10, filter_sources=set())
    assert results == []


def test_search_filter_nonexistent_source_returns_empty(index_with_two_docs):
    results = index_with_two_docs.search("UPI", k=10, filter_sources={"missing.pdf"})
    assert results == []


def test_search_filter_multiple_sources(index_with_two_docs):
    results = index_with_two_docs.search("UPI", k=10, filter_sources={"rbi.pdf", "npci.pdf"})
    sources = {r["source"] for r in results}
    assert "rbi.pdf" in sources
    assert "npci.pdf" in sources


def test_search_unbuilt_index_returns_empty():
    idx = BM25Index()
    results = idx.search("anything", k=5, filter_sources={"rbi.pdf"})
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_bm25_filter.py -v
```

Expected: FAIL — `search()` does not accept `filter_sources` keyword argument.

- [ ] **Step 3: Implement the filter in `server/bm25_index.py`**

Replace the entire `search` method (lines 21–33):

```python
def search(self, query: str, k: int = 20, filter_sources: set[str] | None = None) -> list[dict]:
    if self._bm25 is None:
        return []
    corpus = self._corpus
    if filter_sources is not None:
        corpus = [d for d in corpus if d["source"] in filter_sources]
    if not corpus:
        return []
    tokenized_corpus = [doc["content"].lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)
    top_k_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    results = []
    for idx in top_k_idx:
        if scores[idx] > 0:
            doc = dict(corpus[idx])
            doc["bm25_score"] = round(float(scores[idx]), 4)
            results.append(doc)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_bm25_filter.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Verify existing BM25 tests still pass**

```
pytest tests/ -v -k "bm25 or retriever"
```

Expected: all pass (no regressions — `filter_sources` defaults to `None`, existing call sites unchanged).

- [ ] **Step 6: Commit**

```bash
git add server/bm25_index.py tests/test_bm25_filter.py
git commit -m "feat: add filter_sources param to BM25Index.search"
```

---

## Task 2: source_type Metadata at Ingest

**Files:**
- Modify: `server/ingest.py`
- Modify: `server/url_loader.py`
- Create: `tests/test_source_type.py`

**Interfaces:**
- Produces: all loaded `Document` objects carry `doc.metadata["source_type"]`
  - PDF → `"pdf"`, TXT → `"txt"`, CSV → `"csv"`, URL → `"url"`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_source_type.py`:

```python
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from server.ingest import load_documents_from_paths
from server.url_loader import load_url


def test_pdf_gets_source_type_pdf(tmp_path):
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_doc = Document(page_content="Report content", metadata={"source": "report.pdf", "page": 0})
    with patch("server.ingest.PyPDFLoader") as MockLoader:
        MockLoader.return_value.load.return_value = [mock_doc]
        docs = load_documents_from_paths([str(pdf)])
    assert docs[0].metadata["source_type"] == "pdf"


def test_txt_gets_source_type_txt(tmp_path):
    txt = tmp_path / "notes.txt"
    txt.write_text("Some text content")
    docs = load_documents_from_paths([str(txt)])
    assert docs[0].metadata["source_type"] == "txt"


def test_csv_gets_source_type_csv(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("col1,col2\nval1,val2")
    docs = load_documents_from_paths([str(csv)])
    assert docs[0].metadata["source_type"] == "csv"


def test_url_gets_source_type_url():
    mock_resp = MagicMock()
    mock_resp.headers = {"content-type": "text/html"}
    mock_resp.content = b"<p>Hello world</p>" * 10
    mock_resp.text = "<p>Hello world</p>" * 10
    with patch("server.url_loader.httpx.get", return_value=mock_resp):
        docs = load_url("https://example.com")
    assert docs[0].metadata["source_type"] == "url"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_source_type.py -v
```

Expected: FAIL — `source_type` key not in metadata.

- [ ] **Step 3: Add `source_type` to `server/ingest.py`**

In `load_documents_from_paths`, after each `doc.metadata["source"] = file_path.name` line, add the `source_type` assignment. There are 3 file type branches:

```python
# PDF branch (after line: doc.metadata["source"] = file_path.name)
doc.metadata["source_type"] = "pdf"

# TXT branch (after line: doc.metadata["source"] = file_path.name)
doc.metadata["source_type"] = "txt"

# CSV branch (after line: doc.metadata["source"] = file_path.name)
doc.metadata["source_type"] = "csv"
```

Apply the same additions to `load_documents` (the directory-scan version) — same three branches, same pattern.

The full updated PDF block in `load_documents_from_paths` looks like:

```python
if file_path.suffix.lower() == ".pdf":
    try:
        loader = PyPDFLoader(str(file_path))
        docs = loader.load()
    except Exception as e:
        if "not been decrypted" in str(e).lower() or "FileNotDecryptedError" in type(e).__name__:
            raise ValueError(
                f"'{file_path.name}' is password-protected. "
                "Remove the password and re-upload."
            ) from e
        raise
    for doc in docs:
        doc.metadata["source"] = file_path.name
        doc.metadata["source_type"] = "pdf"
    documents.extend(docs)
elif file_path.suffix.lower() == ".txt":
    loader = TextLoader(str(file_path), encoding="utf-8")
    docs = loader.load()
    for doc in docs:
        doc.metadata["source"] = file_path.name
        doc.metadata["source_type"] = "txt"
    documents.extend(docs)
elif file_path.suffix.lower() == ".csv":
    loader = CSVLoader(str(file_path), encoding="utf-8")
    docs = loader.load()
    for doc in docs:
        doc.metadata["source"] = file_path.name
        doc.metadata["source_type"] = "csv"
    documents.extend(docs)
```

Apply the same pattern to `load_documents` (identical structure, same three branches).

- [ ] **Step 4: Add `source_type` to `server/url_loader.py`**

In `load_url`, in the returned `Document` metadata dict (line ~56), add `source_type`:

```python
return [
    Document(
        page_content=full_text,
        metadata={
            "source": url,
            "source_type": "url",
            "type": "web",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
    )
]
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_source_type.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Run existing ingest tests to check no regressions**

```
pytest tests/test_ingest.py tests/test_url_loader.py -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add server/ingest.py server/url_loader.py tests/test_source_type.py
git commit -m "feat: add source_type metadata to all ingested chunks"
```

---

## Task 3: Retriever Filter

**Files:**
- Modify: `server/retriever.py`
- Create: `tests/test_retriever_filter.py`

**Interfaces:**
- Consumes:
  - `BM25Index.search(query, k, filter_sources=set[str] | None)` from Task 1
- Produces:
  - `HybridRetriever.filter_docs: list[str] | None = None` field
  - `get_retriever_filtered(workspace_id: str, filter_docs: list[str]) -> HybridRetriever`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_retriever_filter.py`:

```python
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from server.retriever import HybridRetriever, get_retriever_filtered


def _make_retriever(filter_docs=None):
    mock_vs = MagicMock()
    mock_vs.similarity_search_with_relevance_scores.return_value = [
        (Document(page_content="UPI grew in 2024", metadata={"source": "rbi.pdf", "page": 1, "chunk_index": 0}), 0.85),
        (Document(page_content="NPCI payments record", metadata={"source": "npci.pdf", "page": 1, "chunk_index": 0}), 0.72),
    ]
    return HybridRetriever(
        vectorstore=mock_vs,
        dense_weight=0.7,
        sparse_weight=0.3,
        retrieve_k=10,
        rerank_k=5,
        workspace_id="test",
        use_hyde=False,
        use_multi_query=False,
        filter_docs=filter_docs,
    )


def test_filter_docs_field_defaults_to_none():
    retriever = _make_retriever()
    assert retriever.filter_docs is None


def test_filter_docs_field_set():
    retriever = _make_retriever(filter_docs=["rbi.pdf"])
    assert retriever.filter_docs == ["rbi.pdf"]


def test_dense_retrieve_passes_filter_to_chroma():
    retriever = _make_retriever(filter_docs=["rbi.pdf"])
    retriever._dense_retrieve("UPI", k=5)
    call_kwargs = retriever.vectorstore.similarity_search_with_relevance_scores.call_args
    assert call_kwargs.kwargs.get("filter") == {"source": {"$in": ["rbi.pdf"]}}


def test_dense_retrieve_no_filter_when_none():
    retriever = _make_retriever(filter_docs=None)
    retriever._dense_retrieve("UPI", k=5)
    call_kwargs = retriever.vectorstore.similarity_search_with_relevance_scores.call_args
    assert call_kwargs.kwargs.get("filter") is None


def test_get_retriever_filtered_returns_retriever_with_filter():
    mock_vs = MagicMock()
    with patch("server.retriever.get_vectorstore", return_value=mock_vs), \
         patch("server.retriever.load_config", return_value={
             "retrieval": {"dense_weight": 0.7, "sparse_weight": 0.3,
                           "retrieve_k": 10, "rerank_k": 5,
                           "hyde_enabled": False, "multi_query_enabled": False}
         }):
        r = get_retriever_filtered("default", ["rbi.pdf"])
    assert r.filter_docs == ["rbi.pdf"]
    assert r.vectorstore is mock_vs


def test_get_retriever_filtered_does_not_modify_singleton_cache():
    from server.retriever import _retriever_cache
    initial_keys = set(_retriever_cache.keys())
    mock_vs = MagicMock()
    with patch("server.retriever.get_vectorstore", return_value=mock_vs), \
         patch("server.retriever.load_config", return_value={
             "retrieval": {"dense_weight": 0.7, "sparse_weight": 0.3,
                           "retrieve_k": 10, "rerank_k": 5,
                           "hyde_enabled": False, "multi_query_enabled": False}
         }):
        get_retriever_filtered("workspace-filtered", ["doc.pdf"])
    assert "workspace-filtered" not in _retriever_cache
    assert set(_retriever_cache.keys()) == initial_keys
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_retriever_filter.py -v
```

Expected: FAIL — `HybridRetriever` has no `filter_docs` field; `get_retriever_filtered` does not exist.

- [ ] **Step 3: Add `filter_docs` field to `HybridRetriever` in `server/retriever.py`**

In the `HybridRetriever` class body, after `use_multi_query: bool = False`, add:

```python
filter_docs: list[str] | None = None
```

- [ ] **Step 4: Wire filter into `_dense_retrieve`**

Replace the `_dense_retrieve` method body:

```python
def _dense_retrieve(self, query: str, k: int) -> list[dict]:
    filter_arg = {"source": {"$in": self.filter_docs}} if self.filter_docs else None
    results = self.vectorstore.similarity_search_with_relevance_scores(
        query, k=k, filter=filter_arg
    )
    output = []
    for doc, score in results:
        output.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "page": doc.metadata.get("page"),
            "chunk_index": doc.metadata.get("chunk_index"),
            "similarity_score": round(float(score), 4),
        })
    return output
```

- [ ] **Step 5: Wire filter into `_get_relevant_documents` (BM25 call)**

In `_get_relevant_documents`, the line that calls BM25:

```python
s_results = get_index(self.workspace_id).search(q, k=self.retrieve_k)
```

Replace with:

```python
filter_sources = set(self.filter_docs) if self.filter_docs else None
s_results = get_index(self.workspace_id).search(
    q, k=self.retrieve_k, filter_sources=filter_sources
)
```

- [ ] **Step 6: Add `get_retriever_filtered` helper function**

After the existing `get_retriever` function, add:

```python
def get_retriever_filtered(workspace_id: str, filter_docs: list[str]) -> HybridRetriever:
    """One-off retriever with doc filter applied. Reuses cached vectorstore; does NOT cache itself."""
    config = load_config()
    retrieval_cfg = config.get("retrieval", {})
    return HybridRetriever(
        vectorstore=get_vectorstore(workspace_id),
        dense_weight=retrieval_cfg.get("dense_weight", 0.7),
        sparse_weight=retrieval_cfg.get("sparse_weight", 0.3),
        retrieve_k=retrieval_cfg.get("retrieve_k", 10),
        rerank_k=retrieval_cfg.get("rerank_k", 5),
        workspace_id=workspace_id,
        use_hyde=retrieval_cfg.get("hyde_enabled", False),
        use_multi_query=retrieval_cfg.get("multi_query_enabled", False),
        filter_docs=filter_docs,
    )
```

- [ ] **Step 7: Run tests to verify they pass**

```
pytest tests/test_retriever_filter.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 8: Run full test suite to check no regressions**

```
pytest tests/ -v
```

Expected: all existing tests pass.

- [ ] **Step 9: Commit**

```bash
git add server/retriever.py tests/test_retriever_filter.py
git commit -m "feat: add filter_docs to HybridRetriever and get_retriever_filtered helper"
```

---

## Task 4: Chat Route Filter

**Files:**
- Modify: `server/routes/chat.py`

**Interfaces:**
- Consumes: `get_retriever_filtered(workspace_id: str, filter_docs: list[str]) -> HybridRetriever` from Task 3
- Produces: `POST /api/chat` accepts `{ "question": "...", "filter_docs": ["rbi.pdf"] }` or `{ "question": "..." }` (filter_docs optional, defaults to null)

- [ ] **Step 1: Add import and update `ChatRequest`**

In `server/routes/chat.py`, update `ChatRequest`:

```python
class ChatRequest(BaseModel):
    question: str
    filter_docs: list[str] | None = None
```

- [ ] **Step 2: Add conditional retriever selection in handler**

In the `chat` handler, replace the retriever resolution block (currently lines 28–31):

```python
chain = request.app.state.chain
retriever = getattr(request.app.state, "retriever", None)
if retriever is None:
    from server.retriever import get_retriever as _get_retriever
    retriever = _get_retriever(workspace)
```

Replace with:

```python
from server.retriever import get_retriever as _get_retriever, get_retriever_filtered

chain = request.app.state.chain
active_filter = body.filter_docs if body.filter_docs else None

if active_filter:
    retriever = get_retriever_filtered(workspace, active_filter)
else:
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        retriever = _get_retriever(workspace)
```

- [ ] **Step 3: Update log line to include filter state**

Find the existing log line:

```python
logger.info("QUERY | workspace=%s | %s", workspace, body.question[:100])
```

Replace with:

```python
logger.info(
    "QUERY | workspace=%s | filter=%s | %s",
    workspace, active_filter, body.question[:100]
)
```

- [ ] **Step 4: Manual smoke test**

Start the server:
```
uvicorn server.main:app --reload --port 8000
```

Send unfiltered request — verify it works as before:
```bash
curl -X POST http://localhost:8000/api/chat?workspace=default \
  -H "Content-Type: application/json" \
  -d '{"question": "What is UPI?"}' \
  --no-buffer
```
Expected: SSE stream of token events, then `done` event.

Send filtered request (replace `rbi.pdf` with an actual uploaded doc name):
```bash
curl -X POST http://localhost:8000/api/chat?workspace=default \
  -H "Content-Type: application/json" \
  -d '{"question": "What is UPI?", "filter_docs": ["rbi.pdf"]}' \
  --no-buffer
```
Expected: SSE stream — sources in `done` event all have `source == "rbi.pdf"`.

Send with empty list — verify treated as no filter:
```bash
curl -X POST http://localhost:8000/api/chat?workspace=default \
  -H "Content-Type: application/json" \
  -d '{"question": "What is UPI?", "filter_docs": []}' \
  --no-buffer
```
Expected: same as unfiltered (all sources).

- [ ] **Step 5: Commit**

```bash
git add server/routes/chat.py
git commit -m "feat: chat route accepts filter_docs for scoped retrieval"
```

---

## Task 5: Frontend Filter UI

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/components/ChatArea.jsx`

**Interfaces:**
- Consumes: `POST /api/chat` body now accepts `filter_docs: string[] | null` (Task 4)
- Produces: sidebar doc chips are toggleable; filter badge shows above chat input; filtered queries sent to backend

- [ ] **Step 1: Update `streamChat` in `frontend/src/api.js`**

`streamChat` currently has signature: `streamChat(question, workspaceId, { onToken, onDone, onError })`

Add `filterDocs` param and include in request body:

```js
export async function streamChat(question, workspaceId = "default", { onToken, onDone, onError }, filterDocs = null) {
  let response;
  try {
    response = await fetch(
      `${API_BASE}/chat?workspace=${encodeURIComponent(workspaceId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          filter_docs: filterDocs && filterDocs.length > 0 ? filterDocs : null,
        }),
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
      buffer = lines.pop() ?? "";
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

- [ ] **Step 2: Add `filterDocs` state to `frontend/src/App.jsx`**

Add `filterDocs` state and reset it on workspace switch. Full updated `App.jsx`:

```jsx
import { useState, useEffect, useCallback } from "react";
import { getDocuments, clearMemory, getWorkspaces } from "./api";
import Sidebar from "./components/Sidebar";
import ChatArea from "./components/ChatArea";
import { MAINTENANCE_MODE, MAINTENANCE_MESSAGE } from "./config";

function App() {
  const [documents, setDocuments] = useState([]);
  const [evalLog, setEvalLog] = useState([]);
  const [briefing, setBriefing] = useState(null);
  const [suggestedQuestion, setSuggestedQuestion] = useState("");
  const [currentWorkspace, setCurrentWorkspace] = useState("default");
  const [workspaces, setWorkspaces] = useState(["default"]);
  const [filterDocs, setFilterDocs] = useState([]);

  useEffect(() => {
    getDocuments(currentWorkspace).then((d) => setDocuments(d.documents || []));
    getWorkspaces().then((d) => setWorkspaces(d.workspaces || ["default"]));
  }, [currentWorkspace]);

  // Reset filter when workspace changes
  useEffect(() => {
    setFilterDocs([]);
  }, [currentWorkspace]);

  async function handleNewConversation() {
    await clearMemory();
    setEvalLog([]);
    setBriefing(null);
    setSuggestedQuestion("");
    window.location.reload();
  }

  async function handleWorkspaceChange(ws) {
    setCurrentWorkspace(ws);
    setBriefing(null);
    setSuggestedQuestion("");
    setEvalLog([]);
  }

  const handleSuggestedQuestionUsed = useCallback(() => setSuggestedQuestion(""), []);

  function handleFilterChange(docName) {
    setFilterDocs((prev) =>
      prev.includes(docName) ? prev.filter((d) => d !== docName) : [...prev, docName]
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {MAINTENANCE_MODE && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-center gap-2 text-xs text-amber-800">
          <svg className="w-3.5 h-3.5 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <span><strong>Under maintenance</strong> — {MAINTENANCE_MESSAGE}</span>
        </div>
      )}

      <header className="bg-white px-6 py-4 shrink-0 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-1 h-8 bg-indigo-600 rounded-full" />
          <div>
            <h1 className="text-lg font-semibold text-gray-900 leading-tight">Prism</h1>
            <p className="text-xs text-gray-400">Document Intelligence</p>
          </div>
        </div>
      </header>

      <main className="flex-1 flex">
        <Sidebar
          documents={documents}
          setDocuments={setDocuments}
          onNewConversation={handleNewConversation}
          evalLog={evalLog}
          onBriefing={setBriefing}
          briefing={briefing}
          onSuggestedQuestion={setSuggestedQuestion}
          currentWorkspace={currentWorkspace}
          workspaces={workspaces}
          onWorkspaceChange={handleWorkspaceChange}
          onWorkspacesUpdate={setWorkspaces}
          filterDocs={filterDocs}
          onFilterChange={handleFilterChange}
          onFilterClear={() => setFilterDocs([])}
        />
        <ChatArea
          key={currentWorkspace}
          onEvalEntry={(entry) => setEvalLog((prev) => [...prev, entry])}
          hasDocuments={documents.length > 0}
          suggestedQuestion={suggestedQuestion}
          onSuggestedQuestionUsed={handleSuggestedQuestionUsed}
          currentWorkspace={currentWorkspace}
          filterDocs={filterDocs}
          onFilterClear={() => setFilterDocs([])}
        />
      </main>
    </div>
  );
}

export default App;
```

- [ ] **Step 3: Update `frontend/src/components/Sidebar.jsx` — doc chips**

Update the `Sidebar` component to accept `filterDocs`, `onFilterChange`, `onFilterClear` props and render doc list items as toggleable chips.

Replace the `Sidebar` function signature:

```jsx
export default function Sidebar({
  documents,
  setDocuments,
  onNewConversation,
  evalLog,
  onBriefing,
  briefing,
  onSuggestedQuestion,
  currentWorkspace,
  workspaces,
  onWorkspaceChange,
  onWorkspacesUpdate,
  filterDocs = [],
  onFilterChange,
  onFilterClear,
}) {
```

Replace the `/* Uploaded Documents */` section (the `<div className="bg-gray-50/80 rounded-xl p-3.5">` block containing the doc list) with:

```jsx
{/* Uploaded Documents */}
<div className="bg-gray-50/80 rounded-xl p-3.5">
  <div className="flex items-center justify-between mb-2.5">
    <h3 className="text-xs font-semibold text-indigo-500 uppercase tracking-wider">
      Documents ({documents.length})
    </h3>
    {filterDocs.length > 0 && (
      <button
        type="button"
        onClick={onFilterClear}
        className="text-xs text-indigo-400 hover:text-indigo-600 transition-colors"
      >
        Clear filter
      </button>
    )}
  </div>
  {documents.length === 0 ? (
    <p className="text-sm text-gray-400">No documents yet</p>
  ) : (
    <ul className="space-y-1.5">
      {documents.map((doc, i) => {
        const isSelected = filterDocs.includes(doc.name);
        const isFiltering = filterDocs.length > 0;
        return (
          <li
            key={i}
            className={`flex items-center justify-between text-sm bg-white rounded-lg px-3 py-2 shadow-xs transition-all cursor-pointer ${
              isSelected
                ? "ring-2 ring-indigo-500 bg-indigo-50"
                : isFiltering
                ? "opacity-50"
                : "hover:ring-1 hover:ring-indigo-300"
            }`}
            onClick={() => onFilterChange(doc.name)}
            title={isSelected ? "Click to remove filter" : "Click to filter to this doc"}
          >
            <span className={`truncate flex-1 min-w-0 ${isSelected ? "text-indigo-700 font-medium" : "text-gray-700"}`}>
              {doc.name}
            </span>
            <span className="text-indigo-400 shrink-0 ml-2 text-xs font-medium">
              {doc.chunk_count}
            </span>
            <button
              onClick={(e) => { e.stopPropagation(); handleDelete(doc.name); }}
              disabled={deletingDoc === doc.name}
              title="Remove document"
              className="ml-2 shrink-0 text-gray-300 hover:text-red-500 transition-colors disabled:opacity-40"
            >
              {deletingDoc === doc.name ? (
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zm-1 6a1 1 0 112 0v5a1 1 0 11-2 0V8zm4 0a1 1 0 112 0v5a1 1 0 11-2 0V8z" clipRule="evenodd"/>
                </svg>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  )}
</div>
```

- [ ] **Step 4: Update `frontend/src/components/ChatArea.jsx` — filter badge + pass to API**

Update `ChatArea` props and `handleSend` to accept and use `filterDocs`:

```jsx
import { useState, useEffect, useRef } from "react";
import { streamChat } from "../api";
import MessageBubble from "./MessageBubble";

export default function ChatArea({
  onEvalEntry,
  hasDocuments,
  suggestedQuestion,
  onSuggestedQuestionUsed,
  currentWorkspace = "default",
  filterDocs = [],
  onFilterClear,
}) {
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

    try {
      await streamChat(
        question,
        currentWorkspace,
        {
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
        },
        filterDocs.length > 0 ? filterDocs : null
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex flex-col bg-gray-50">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <svg className="w-16 h-16 text-indigo-200 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1"
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
            <p className="text-lg font-medium text-gray-500 mb-1">
              {hasDocuments ? "Ask a question about your documents" : "Upload documents to get started"}
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

      {/* Filter badge */}
      {filterDocs.length > 0 && (
        <div className="px-4 pt-2 max-w-4xl mx-auto w-full">
          <div className="flex items-center gap-2 text-xs text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-1.5">
            <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z" />
            </svg>
            <span className="truncate flex-1">
              Scoped to: {filterDocs.join(", ")}
            </span>
            <button
              type="button"
              onClick={onFilterClear}
              className="shrink-0 text-indigo-400 hover:text-indigo-600 transition-colors font-medium"
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSend} className="p-4 bg-white border-t border-gray-100">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              filterDocs.length > 0
                ? `Searching ${filterDocs.length} selected doc${filterDocs.length > 1 ? "s" : ""}...`
                : hasDocuments
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

- [ ] **Step 5: Run frontend dev server and test manually**

```
cd frontend && npm run dev
```

Open `http://localhost:5173`. With at least 2 docs uploaded:

1. **No filter:** Doc chips are neutral. Send a question — sources in CitationPopover show docs from any file. ✓
2. **Select one doc:** Click a doc chip — it highlights (indigo ring, `bg-indigo-50`), others dim. Filter badge appears above input. Send question — sources only from that file. ✓
3. **Select multiple docs:** Click a second doc — both highlighted. Filter badge shows both names. Sources from either file only. ✓
4. **Clear via badge ×:** Click × in filter badge — chips reset to neutral, badge disappears. ✓
5. **Clear via "Clear filter":** Click "Clear filter" button in sidebar header — same result. ✓
6. **Workspace switch:** Switch workspace — filter resets automatically. ✓
7. **Select doc then delete it:** Delete a selected doc — filter list still contains its name; next query returns 0 sources from corpus (graceful empty, existing handler). ✓

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/App.jsx frontend/src/components/Sidebar.jsx frontend/src/components/ChatArea.jsx
git commit -m "feat: sidebar doc filter chips scope retrieval to selected documents"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `source_type` added at ingest | Task 2 |
| `source_type = "url"` for URL ingestion | Task 2 |
| Filter on `source` (doc_name) only | Task 3 + 4 |
| BM25 pre-filter on source | Task 1 |
| ChromaDB `where` clause | Task 3 |
| `get_retriever_filtered()` — reuses cached vectorstore | Task 3 |
| `filter_docs: list[str] | None` on `ChatRequest` | Task 4 |
| Sidebar doc chips toggleable | Task 5 |
| `filterDocs` state reset on workspace switch | Task 5 (App.jsx `useEffect`) |
| Filter badge above chat input | Task 5 (ChatArea) |
| Clear filter button in sidebar + badge | Task 5 |
| `filter_docs: []` treated as no filter | Task 4 (`body.filter_docs if body.filter_docs else None`) + api.js |
| Workspace switch resets filter | Task 5 |
| Empty filter → 0 results → graceful empty answer | Existing `stream_query_with_web` handler, no change needed |

All spec requirements covered.

**Placeholder scan:** None found. All steps contain concrete code.

**Type consistency check:**
- `filter_sources: set[str] | None` — used consistently in Task 1 (BM25) and Task 3 (retriever)
- `filter_docs: list[str] | None` — consistent across Task 3 (retriever field), Task 4 (ChatRequest), Task 5 (frontend state)
- `get_retriever_filtered(workspace_id: str, filter_docs: list[str])` — defined Task 3, consumed Task 4 ✓
- `onFilterChange`, `onFilterClear` — defined Task 5 App.jsx, passed to Sidebar + ChatArea ✓
- `streamChat(question, workspaceId, callbacks, filterDocs)` — updated in Task 5 api.js, called in ChatArea ✓
