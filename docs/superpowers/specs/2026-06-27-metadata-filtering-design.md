# Metadata Filtering — Design Spec
**Date:** 2026-06-27  
**Status:** Approved  
**Scope:** Prism — Stage 17

---

## Problem

Within a workspace, all uploaded documents are searched together. A user with 10 docs spanning 5 years cannot scope a query to a specific doc or subset. All retrieval is corpus-wide.

## Goal

Let users select specific documents in the sidebar to scope retrieval. Clicking a doc chip restricts dense + sparse retrieval to only that doc's chunks. Zero selection = current behavior (all docs searched).

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Metadata fields | `source_type` added at ingest; filter on existing `source` field | `source` already stored per chunk; `source_type` useful for citation display |
| Filter fields exposed | `doc_name` (= `source`) only | Simplest; highest value per user action |
| Filter UX | Sidebar doc chips (toggle) | Already shows doc list; natural extension |
| Retriever strategy | New lightweight instance per filtered request, reusing cached vectorstore | Thread-safe; vectorstore (heavy) stays cached; retriever (cheap) created fresh |

---

## Architecture

### Ingest changes (`ingest.py`)

Add `source_type` to all chunk metadata at load time:

```python
SOURCE_TYPE_MAP = {".pdf": "pdf", ".txt": "txt", ".csv": "csv"}
doc.metadata["source_type"] = SOURCE_TYPE_MAP.get(file_path.suffix.lower(), "file")
```

For URL ingestion (`url_loader.py`): set `source_type = "url"` on loaded docs.

`doc_name` = `source` (filename) — already stored. No new field.

### BM25 changes (`bm25_index.py`)

Add `filter_sources: set[str] | None = None` to `BM25Index.search()`:

```python
def search(self, query: str, k: int = 20, filter_sources: set[str] | None = None) -> list[dict]:
    corpus = self._corpus
    if filter_sources:
        corpus = [d for d in corpus if d["source"] in filter_sources]
    if not corpus:
        return []
    tokenized = [doc["content"].lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)
    scores = bm25.get_scores(query.lower().split())
    ...
```

Note: when filter reduces corpus, BM25 must be re-scored against the filtered subset (not the full index), so scores stay relative. Build a temporary `BM25Okapi` over the filtered corpus.

### Retriever changes (`retriever.py`)

1. Add field to `HybridRetriever`:
```python
filter_docs: list[str] | None = None
```

2. Wire into `_dense_retrieve`:
```python
filter_arg = {"source": {"$in": self.filter_docs}} if self.filter_docs else None
results = self.vectorstore.similarity_search_with_relevance_scores(query, k=k, filter=filter_arg)
```

3. Wire into `_get_relevant_documents` (BM25 call):
```python
filter_sources = set(self.filter_docs) if self.filter_docs else None
s_results = get_index(self.workspace_id).search(q, k=self.retrieve_k, filter_sources=filter_sources)
```

4. New helper function (does NOT replace or invalidate the singleton cache):
```python
def get_retriever_filtered(workspace_id: str, filter_docs: list[str]) -> HybridRetriever:
    """One-off retriever with doc filter. Reuses cached vectorstore."""
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

### Chat route changes (`routes/chat.py`)

```python
class ChatRequest(BaseModel):
    question: str
    filter_docs: list[str] | None = None

# in handler, before stream:
retriever = (
    get_retriever_filtered(workspace, body.filter_docs)
    if body.filter_docs
    else get_retriever(workspace)
)
```

Log filter state: `logger.info("QUERY | workspace=%s | filter=%s | %s", workspace, body.filter_docs, body.question[:80])`

### Frontend changes

**`Sidebar.jsx`** — doc list items become toggleable chips:
- Selected: indigo ring + solid background
- Unselected (when others selected): dimmed opacity
- No selection: all neutral (current look)
- "Clear" × button appears when ≥1 selected

**`App.jsx`** — `filterDocs: string[]` state, reset on workspace switch:
```jsx
const [filterDocs, setFilterDocs] = useState([])
// reset on workspace change
useEffect(() => setFilterDocs([]), [activeWorkspace])
```

**`ChatArea.jsx`** — filter indicator above input + pass `filterDocs` to API call:
```jsx
// badge when filter active
{filterDocs.length > 0 && (
  <div>Scoped to: {filterDocs.join(", ")} <button onClick={() => setFilterDocs([])}>×</button></div>
)}
```

**`api.js`** — include `filter_docs` in chat request body:
```js
filter_docs: filterDocs.length ? filterDocs : null
```

---

## Data flow

```
User clicks doc chip in sidebar
  → filterDocs state updated in App.jsx
  → passed to ChatArea as prop
  → badge shown above input
User sends message
  → api.js sends { question, filter_docs: ["rbi_2024.pdf"] }
  → routes/chat.py: filter_docs present → get_retriever_filtered(workspace, filter_docs)
  → HybridRetriever._dense_retrieve: ChromaDB where={"source": {"$in": ["rbi_2024.pdf"]}}
  → BM25Index.search: corpus pre-filtered to rbi_2024.pdf chunks → re-scored
  → RRF fusion → rerank → stream answer
```

---

## Error handling

| Case | Behavior |
|------|----------|
| Filter doc not in workspace | ChromaDB returns 0 results → stream returns "no relevant documents" (existing handler) |
| All selected docs deleted mid-session | Same as above |
| BM25 not built (cold start) | `search()` returns `[]` — unchanged |
| Workspace switch | `filterDocs` reset to `[]` via `useEffect` on `activeWorkspace` change |
| `filter_docs: []` sent | Backend treats as `None` — guard: `body.filter_docs if body.filter_docs else None` |
| Single doc with 2 chunks, retrieve_k=10 | ChromaDB returns ≤2, reranker handles gracefully |

---

## Out of scope

- Year filtering (auto-extracted at ingest but not exposed as filter)
- source_type filtering
- Saved filter presets
- Filter persistence across sessions

---

## Files changed

| File | Change |
|------|--------|
| `server/ingest.py` | Add `source_type` to chunk metadata in both loaders |
| `server/url_loader.py` | Add `source_type = "url"` to loaded doc metadata |
| `server/bm25_index.py` | `search()` gets `filter_sources` param; re-score against filtered corpus |
| `server/retriever.py` | `filter_docs` field on `HybridRetriever`; wire into dense + sparse; `get_retriever_filtered()` |
| `server/routes/chat.py` | `filter_docs` on `ChatRequest`; conditional retriever selection |
| `frontend/src/App.jsx` | `filterDocs` state + reset on workspace switch |
| `frontend/src/components/Sidebar.jsx` | Doc chips toggleable; emit `onFilterChange` |
| `frontend/src/components/ChatArea.jsx` | Filter badge above input; pass `filterDocs` to API |
| `frontend/src/api.js` | Include `filter_docs` in chat request body |
