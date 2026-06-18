# Prism — Project Evolution

> End-to-end record of what was broken at each stage, what was built to fix it, and what is planned next.
> Updated as the project evolves. Last updated: 2026-06-18.

---

## Table of Contents

1. [Stage 0 — v1 Baseline](#stage-0--v1-baseline)
2. [Stage 1 — v2 Hybrid Retrieval Architecture](#stage-1--v2-hybrid-retrieval-architecture-2026-05-17)
3. [Stage 2 — Chain Scores + RAGAS Endpoint](#stage-2--chain-scores--ragas-endpoint-2026-05-23)
4. [Stage 3 — Groq Migration + Web Search](#stage-3--groq-migration--web-search-fixes-2026-05-24)
5. [Stage 4 — OOM Hell on Render](#stage-4--oom-hell-on-render-2026-05-24-four-sub-issues)
6. [Stage 5 — TinyBERT + RAGAS Removal + Benchmark JSON](#stage-5--tinybert--ragas-removal--benchmark-json-2026-05-30)
7. [Stage 6 — Multi-Workspace](#stage-6--multi-workspace-2026-06-early)
8. [Stage 7 — Singleton Cache + URL Guard](#stage-7--singleton-cache--url-guard-2026-06-14)
9. [Stage 8 — Eval Dashboard + Rigorous Metrics](#stage-8--eval-dashboard--rigorous-metrics-2026-06-17)
10. [Current State Snapshot](#current-state-snapshot)
10. [Roadmap — Retrieval & Answer Quality](#roadmap--retrieval--answer-quality)
11. [Roadmap — New Features](#roadmap--new-features)

---

## Stage 0 — v1 Baseline

### What existed
- Dense-only ChromaDB vector retrieval
- Single global document collection
- Basic chat with ConversationalRetrievalChain
- No evaluation framework
- No web search
- No logging

### What was wrong

| Problem | Impact |
|---------|--------|
| Dense-only retrieval | Misses exact keyword matches — regulatory text has section numbers, policy codes, specific terms that semantic search fails on |
| No evaluation | No way to measure if answers were correct or grounded |
| No web search | Static corpus only — cannot answer questions about current stock prices, recent news |
| Single collection | No topic isolation — all documents mixed in one retrieval pool |
| No logging | Impossible to debug production failures |

**This was the starting point. No fixes yet.**

---

## Stage 1 — v2 Hybrid Retrieval Architecture (2026-05-17)

### What was wrong before building
- `retriever.py` was dense-only ChromaDB — v2 was documented but not implemented
- `ragas_eval.py` missing entirely; RAGAS eval endpoint not wired
- No BM25, no reranker, no score visibility

### What we built

| File | What changed |
|------|-------------|
| `server/bm25_index.py` | BM25Okapi singleton; module-level (not `app.state`) so importable anywhere; rebuilt on startup + after upload |
| `server/reranker.py` | CrossEncoder singleton; pre-loaded at startup to avoid cold-start latency on first query |
| `server/retriever.py` | Full rewrite as `HybridRetriever(BaseRetriever)` — RRF fusion of dense (weight 0.7) + sparse (weight 0.3) |
| `server/main.py` | BM25 build + reranker load wired into lifespan startup |
| `server/routes/upload.py` | BM25 rebuild triggered after each upload |

### Key design decisions

- **`HybridRetriever` as `BaseRetriever` subclass** — `ConversationalRetrievalChain` expects a `BaseRetriever`; subclassing means `chain.py` needs zero changes
- **BM25 as module-level singleton** — avoids threading state through lifespan → constructor; `get_index()` importable anywhere
- **Reranker pre-loaded at startup** — ~0.5s load from disk cache; better to pay at startup than add latency to first user query
- **MiniLM-L-6-v2** chosen as reranker (~85MB) — best ranking quality available at the time

### What was still missing
- Chain score extraction (similarity/BM25/RRF/rerank not returned in API response)
- RAGAS eval endpoint
- Groq LLM (still on Euron)

---

## Stage 2 — Chain Scores + RAGAS Endpoint (2026-05-23)

### What was wrong
- API response had no retrieval scores — no way to show per-source similarity/BM25/RRF/rerank scores
- RAGAS eval endpoint not wired; `ragas_eval.py` missing
- `data/ground_truth/eval_pairs.json` had only keyword hints, no `ground_truth` answers → `context_precision` and `context_recall` always returned null

### What we built

| File | What changed |
|------|-------------|
| `server/chain.py` | Score extraction — similarity/bm25/rrf/rerank scores passed through to API response per source |
| `server/routes/chat.py` | Added `retrieval_method` field; stores contexts in `eval_log` for downstream RAGAS eval |
| `server/config.yaml` | Hybrid retrieval params: `dense_weight`, `sparse_weight`, `retrieve_k`, `rerank_k` |
| `requirements.txt` | Added `rank_bm25`, `sentence-transformers`, `ragas`, `datasets` |
| `server/eval/ragas_eval.py` | RAGAS faithfulness + answer_relevancy via `LangchainLLMWrapper` |
| `server/routes/eval.py` | `POST /api/eval/ragas` endpoint wired |
| `server/main.py` | `/health` endpoint added |

### What was still broken
- RAGAS not installed in venv (added to requirements.txt; installs at Docker build only)
- `eval_pairs.json` still had no ground_truth → 2 of 4 RAGAS metrics null
- LLM still on Euron gpt-4.1-mini

---

## Stage 3 — Groq Migration + Web Search Fixes (2026-05-24)

### What was wrong

| Problem | Root cause |
|---------|-----------|
| LLM on Euron (gpt-4.1-mini) | Closed model, slower, weaker interview story vs open-weight |
| Web search silently broken | `tavily-python` in requirements.txt but never pip-installed |
| Tavily returned shallow results | `search_depth="basic"` — not enough content from financial sites |
| Web context never reached LLM | `ConversationalRetrievalChain`'s condensation step rewrote the question and stripped prepended Tavily context before LLM ever saw it |
| Follow-up web queries returned garbage | Raw follow-up ("Is the price level good?") sent to Tavily with no chat history context |
| No request logging | Production failures undebuggable |

### What we built

| Component | Change |
|-----------|--------|
| LLM | Migrated Euron → Groq `llama-3.3-70b-versatile` via `langchain-groq`. Euron kept for embeddings (Groq has no embeddings endpoint) |
| `server/chain.py` | `run_query_with_web()` — bypasses chain condensation; direct LLM call with RAG + Tavily context + memory |
| `server/chain.py` | `condense_question()` — rewrites follow-up queries using chat history before Tavily search |
| Tavily | `search_depth="advanced"`, `max_results=3` (2× credits but richer content) |
| `server/main.py` | Request logging middleware — logs `METHOD /path STATUS Xms` per request |
| `server/utils.py` | Centralised logging — root logger + `logs/finrag.log` (5MB×3 rotation), noisy libs silenced |
| `frontend/.../MessageBubble.jsx` | `WebSourcesList` component — Tavily URLs as clickable green pill links |
| `.env.example` | Fixed — real keys had been committed; replaced with placeholders |

### Key discoveries
- `ConversationalRetrievalChain` condensation = silent context killer for web queries. Only fix: bypass the chain entirely for web path.
- Memory's `output_key="answer"` — `save_context` must use `{"answer": answer}` not `{"output": answer}` or KeyError.

---

## Stage 4 — OOM Hell on Render (2026-05-24, four sub-issues)

Render free tier: 512MB RAM. This stage was four separate OOM root causes discovered in sequence.

---

### 4a — CUDA torch OOM (startup crash)

**Problem:** `sentence-transformers` pulled CUDA torch (~2GB) by default. OOM before uvicorn bound to port → Render showed "No open ports detected" timeout. Zero server stdout — invisible failure.

**Diagnosis clue:** Build log showed `cuda-toolkit-13.0.2`, `nvidia-cublas` being installed. Port scan timeout = uvicorn crash at import time (not lifespan — lifespan runs *after* port bind).

**Fix:**
```dockerfile
# Install CPU-only torch BEFORE requirements.txt
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install -r requirements.txt

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
```

---

### 4b — ragas startup ImportError

**Problem:** `ragas 0.4.3` imports `langchain_community.chat_models.vertexai` at package `__init__` level. That module was removed in `langchain-community 0.4.x`. Crash propagated: `eval.py` → `ragas_eval.py` → `ragas.__init__` → ImportError before uvicorn bound port.

**Fix:** All ragas imports moved inside `run_ragas_eval()` function body (lazy import).

---

### 4c — CrossEncoder OOM during chat

**Problem:** `CrossEncoder.predict(20 pairs)` = BERT forward pass on 20 pairs → ~200–400MB spike on top of base ~250MB → OOM on first web query.

**Fix:**
- `config.yaml`: `retrieve_k: 20 → 10`
- `reranker.py`: `model.predict(pairs, batch_size=4)` — limits how many pairs processed at once

---

### 4d — Web search OOM (post-GC headroom)

**Problem:** After first query, Python retained chain/LLM objects at ~490MB. Web query added ~9KB Tavily content + `condense_question` LLM call + `run_query_with_web` LLM call → OOM.

**Fix:**
- Tavily content truncated to 800 chars per result (was up to ~3000)
- `max_results`: 3 → 2
- `gc.collect()` after each chat request in `routes/chat.py`

---

## Stage 5 — TinyBERT + RAGAS Removal + Benchmark JSON (2026-05-30)

### What was wrong

| Problem | Root cause |
|---------|-----------|
| MiniLM-L-6-v2 (~85MB) still OOMing on web queries | Too close to 512MB ceiling even after GC |
| Live RAGAS eval always 500 on Render | `nest_asyncio.apply()` (called at ragas import time) cannot patch `uvloop` — the event loop uvicorn uses on Linux. `ValueError: Can't patch loop of type uvloop.Loop`. Permanently unfixable without replacing uvicorn's event loop. |
| Groq 70B exhausted 100k daily tokens in one RAGAS run | RAGAS makes ~10 LLM calls per sample for statement decomposition. 10 samples × 10 calls = 100k tokens gone. |
| context_precision and context_recall always null | `eval_pairs.json` had no `ground_truth` answers — only keyword hints |

### What we built

| Component | Change |
|-----------|--------|
| `server/reranker.py` | Switched to `cross-encoder/ms-marco-TinyBERT-L-2-v2` (~17MB vs 85MB). Saves 68MB permanently. |
| `server/routes/eval.py` | Removed `POST /api/eval/ragas` endpoint |
| `requirements.txt` | Removed `ragas` |
| `scripts/run_ragas_local.py` | Local RAGAS runner: ingest corpus → generate answers → run eval → write JSON. Uses `llama-3.1-8b-instant` as judge (500k TPD vs 70B's 100k TPD) |
| `frontend/src/data/ragas_benchmark.json` | Static scores — Vercel builds dashboard from file |
| `frontend/.../EvalPanel.jsx` | Replaced live run button with static benchmark panel |
| `data/ground_truth/eval_pairs.json` | Added `ground_truth` field to all 20 pairs → unlocked `context_precision` + `context_recall` |
| UI | i-button tooltips on faithfulness badge + all 4 RAGAS metric cards |

### Real scores committed
```
faithfulness:      1.0   (note: likely inflated — see below)
answer_relevancy:  0.90
context_precision: TBD   (pending fresh run)
context_recall:    TBD   (pending fresh run)
```

### Key discoveries
- `results["metric_name"]` returns `None` in ragas 0.2.x — must use `results.to_pandas()["metric_name"].mean()`
- TinyBERT loads with harmless `UNEXPECTED key bert.embeddings.position_ids` warning
- **Faithfulness 1.0 is likely inflated** — eval queries were designed alongside the corpus, and 8B judge is lenient. Scores are directional, not absolute. Run on held-out queries for honest numbers.

---

## Stage 5.5 — Rebranding: FinRAG → Prism (2026-06-13)

### What changed
The project was originally named **FinRAG** — a fintech-specific RAG demo. As the architecture matured (multi-workspace, URL ingestion, domain-agnostic retrieval), it became clear the tool was no longer fintech-specific. Any corpus — legal, HR, medical, research — could be loaded and queried.

**Decision:** Rebrand to **Prism**. Name reflects the core idea: feed any document set in, get clear structured answers out. One engine, any domain.

| Before | After |
|--------|-------|
| FinRAG | Prism |
| Fintech-specific framing | Domain-agnostic positioning |
| `finrag-v2.onrender.com` | `prism.onrender.com` |
| README pitched at fintech analysts | README pitched at any knowledge-worker |

### What stayed the same
All retrieval architecture, eval framework, and deployment stack unchanged. Rebrand is naming and framing only — the engine is identical.

### What was wrong with the old name
- "FinRAG" implied fintech-only → narrowed the demo audience
- Interviewers at non-fintech MNCs (Adobe, Atlassian, Intuit) would dismiss it as domain-locked
- The actual retrieval engine is domain-agnostic — the name should match

---

## Stage 6 — Multi-Workspace (2026-06 early)

### What was wrong
- Single ChromaDB collection — no isolation between document sets
- Switching topics meant re-ingesting and overwriting previous docs
- `list_collections()` broke on chromadb ≥0.5.4 (returns `list[str]`, not `list[Collection]`)
- Non-web chat path used stale global chain's `source_documents` instead of workspace-specific retriever → wrong docs shown after workspace switch

### What we built

| File | Change |
|------|--------|
| `server/routes/workspaces.py` | Workspace CRUD — one ChromaDB collection per workspace |
| `server/routes/chat.py` | Always resolves workspace-specific retriever before branching on `web_search` |
| `server/routes/workspaces.py` | `list_collections()` normalised with `isinstance` check — works on chromadb ≥0.5.4 (`list[str]`) and <0.5 (`list[Collection]`) |
| `frontend/src/components/Sidebar.jsx` | Workspace switcher UI; per-workspace doc list |
| `frontend/src/App.jsx`, `api.js`, `ChatArea.jsx`, `FileUpload.jsx` | `workspace_id` passed on all requests |

### Key discovery
- Non-web path was relying on stale global chain's `source_documents` rather than workspace-specific retriever. After switching workspaces, the wrong collection's docs were being cited.

---

## Stage 7 — Singleton Cache + URL Guard (2026-06-14) ← Current

### What was wrong
- Every `POST /api/chat` called `get_or_create_collection()` + built a new `HybridRetriever` = full embedding reload per request → OOM after 2–3 queries in the same workspace
- React component state (message list) persisted across workspace switch — showed previous workspace's chat history
- External URL ingestion had no size guard → large pages (news articles, regulatory filings) caused OOM during embed

### What we built

| File | Change |
|------|--------|
| `server/retriever.py` | Module-level `Dict[workspace_id, (vectorstore, retriever)]` cache. Cache invalidated after ingest. `routes/chat.py` reuses cached retriever. |
| `server/routes/chat.py` | Eliminated double retrieval on non-web path; fixed stray print statement |
| `server/url_loader.py` | Max content size guard before embedding external URL content |
| `frontend/src/App.jsx` | `key={workspaceId}` on `<ChatArea>` → remounts component on workspace switch → clears stale messages and state |

### Commits
```
529675f  fix: singleton vectorstore/retriever cache to prevent OOM on repeated queries
6c9f809  fix: URL size guard for OOM prevention, eliminate double retrieval in chat
521a27a  fix: remount ChatArea on workspace switch to clear stale messages
```

### Additional fix (2026-06-16) — HyDE (Hypothetical Document Embeddings)

**What:** Before dense ChromaDB search, LLM generates a hypothetical 2-sentence answer. That answer (not raw query) is embedded for ANN search. BM25 + reranker still use original query.

| File | Change |
|------|--------|
| `server/retriever.py` | `_hyde_expand()` method; `use_hyde: bool` field on `HybridRetriever`; dense path uses expanded query when enabled |
| `config.yaml` | `retrieval.hyde_enabled: false` — toggle without code change |

**Why off by default:** Adds one Groq call per query (~200ms). Enable to measure RAGAS context_recall lift, then decide.

**Commit:** `8945b43`

---

### Additional fix (2026-06-17) — Mandatory web search

**Problem:** Web search was opt-in toggle. Users querying corpus-only got hallucinated answers from irrelevant documents (e.g., Singapore visa question grounded in random passport-mentioning corpus doc, faithfulness 4/5).

**Fix:**

| File | Change |
|------|--------|
| `frontend/src/components/ChatArea.jsx` | Removed toggle button; `const webSearch = true` hardcoded; placeholder always says "docs + web" |
| `server/routes/chat.py` | `web_search: bool = True` as default in `ChatRequest` |

Every query now hits Tavily + RAG corpus. `run_query_with_web` always called with both rag_docs + web_sources.

---

## Stage 8 — Eval Dashboard + Rigorous Metrics (2026-06-17)

### What was wrong
- faithfulness 1.0 and context_precision 1.0 artificially inflated — eval pairs designed alongside corpus, 8B judge lenient. Meaningless scores.
- Per-message faithfulness badge cluttered user UI. Users don't care about LLM judge scores.
- 10 samples — not statistically meaningful.
- Single flat JSON, no versioning — no way to track metric evolution across architecture changes.

### What we built

| Component | Change |
|-----------|--------|
| `eval-dashboard/` | Separate Vite + React static site (own Vercel project). Reads versioned JSON run files. |
| `eval-dashboard/src/components/` | MetricCard (score + delta vs prev), EvolutionChart (Recharts line chart across versions), RunTable (per-query expandable rows with answer vs ground_truth), LatencyStats (p50/p95 bars) |
| `eval-dashboard/public/data/index.json` | Run registry — list of all versioned eval runs |
| `scripts/run_eval_versioned.py` | New eval script. Args: `--version`, `--tag`, `--n`. Computes answer_correctness (LLM judge vs ground_truth), answer_relevancy + context_recall (RAGAS), precision@5, latency p50/p95/p99. Writes versioned JSON + updates index. |
| `data/ground_truth/eval_pairs.json` | Expanded 20 → 50 pairs. Added multi-hop, comparative, negative, numeric, and edge-case questions. |
| `frontend/src/components/MessageBubble.jsx` | Removed FaithfulnessBadge component and rendering block. |
| `server/routes/chat.py` | Removed `score_faithfulness()` call. One fewer Groq API call per query → faster responses. |

### Metrics before vs after

| Metric | Before | After |
|--------|--------|-------|
| faithfulness | 1.0 (inflated) | Removed from prod path |
| context_precision | 1.0 (inflated) | Replaced by answer_correctness (LLM judge vs ground_truth) |
| answer_relevancy | 0.88 | Kept (RAGAS) |
| context_recall | 0.83 | Kept (RAGAS) |
| precision@5 | tracked separately | Now in main eval dashboard |
| latency p50/p95 | not tracked | Now tracked per eval run |
| sample_count | 10 | 50 (5× improvement) |

---

## Current State Snapshot

```
Retrieval:    Hybrid BM25 (0.3) + ChromaDB dense (0.7) → RRF → TinyBERT rerank top-10→5
LLM:          Groq llama-3.3-70b-versatile
Embeddings:   Euron API text-embedding-3-small
Chunking:     ParentDocumentRetriever (child 200-char indexed, parent 800-char to LLM)
Memory:       ConversationBufferWindowMemory k=10
Web search:   Tavily advanced, 800-char truncation, max 2 results — MANDATORY (always on)
HyDE:         Implemented, toggled via config.yaml hyde_enabled (default: false)
Eval:         Separate eval-dashboard/ static site → https://askprism-eval.vercel.app/
              Metrics: answer_correctness, answer_relevancy, context_recall, precision@5, latency
              Script: scripts/run_eval_versioned.py --version v1.1.0 --tag "Indigo" --n 50
              50 eval pairs; v1.0.0 "Violet": correctness=0.82, relevancy=0.62, recall=0.51, P@5=0.89, p50=2029ms
              Versioning: v1.0.0 / v1.1.0 (feature) / v1.0.1 (fix) / v2.0.0 (major arch change)
              No per-message faithfulness badge in user UI
Workspaces:   Per-workspace ChromaDB collection, singleton retriever cache
Infra:        Render (backend) + https://askprism.vercel.app/ (frontend) + https://askprism-eval.vercel.app/ (eval)
Observability: LangSmith traces all LLM + retrieval calls (optional, env var)
```

---

## Roadmap — Retrieval & Answer Quality

### Phase 1 — Quick wins (no infra change, measurable RAGAS lift)

#### ~~HyDE (Hypothetical Document Embeddings)~~ ✅ Done (Stage 7, commit 8945b43)
- Implemented in `server/retriever.py`. Toggle: `config.yaml hyde_enabled` (default: false).
- Enable + re-run eval to measure context_recall lift vs v2.0 baseline (0.70).

#### Multi-Query Retrieval ← Next
- **Problem:** Single phrasing has blind spots. `"UPI volume FY24"` misses `"transactions processed in financial year 2023-24"`.
- **How:** LLM generates 3 phrasings of the query → retrieve for each → pool all candidates → deduplicate by chunk ID → RRF merge → rerank.
- **Why it works:** Wider candidate pool before reranker = higher recall. Reranker then picks best 5 from 30 instead of 10.
- **Effort:** ~30 lines. 3× retrieval calls + 1 LLM call. Parallelise with `asyncio.gather` to limit latency hit.
- **Expected lift:** RAGAS context_recall measurably improves on multi-phrasing queries.

---

### Phase 2 — Ingest pipeline (requires re-ingest of all docs)

#### Contextual Retrieval
- **Problem:** Chunks lose context when split. `"The limit was revised to ₹2 lakh"` has no idea which circular, which date, which payment type.
- **How:** At ingest time, for each chunk, call LLM: *"Here is the document [full doc]. Here is a chunk [chunk]. Write 2–3 sentences situating this chunk."* Prepend that context to the chunk before embedding.
- **Result:** `"RBI Master Circular 2024 on UPI limits. The limit was revised to ₹2 lakh..."` → richer vector.
- **Effort:** Medium. Modifies `ingest.py` child chunk creation. One Groq 8B call per chunk at ingest time (not query time — zero query latency hit).
- **Expected lift:** Anthropic's benchmark: ~49% reduction in retrieval failures. RAGAS context_precision measurably improves.

#### Semantic Chunking
- **Problem:** Fixed 200-char splits cut mid-sentence, mid-table, mid-list. Embedding a truncated sentence returns a weak vector.
- **How:** Replace `RecursiveCharacterTextSplitter` with LangChain's `SemanticChunker` — splits at sentence boundaries where cosine similarity between adjacent sentences drops below a threshold (topic shift).
- **Effort:** Medium. Config change in `ingest.py` + re-ingest. Tune `breakpoint_threshold_type`.
- **Expected lift:** Fewer nonsensical chunks in top-5. Most noticeable on regulatory PDFs with section headers and numbered lists.

---

### Phase 3 — UX + trust

#### Streaming Responses
- **Problem:** User submits question → 8–15s wait → full answer appears. On Render free vCPU this feels broken.
- **How:** Backend: `chain.astream_events()` → `StreamingResponse` yielding SSE tokens. Frontend: `EventSource` or `fetch` + `ReadableStream` — append tokens as they arrive. Faithfulness scoring runs as background task after full answer assembled.
- **Effort:** High — both backend and frontend change. `ConversationalRetrievalChain` supports `astream_events()` in LangChain ≥0.2.
- **Impact:** Perceived latency drops from 10s to ~1s. Single biggest UX improvement.

#### Citation Highlighting
- **Problem:** Sources listed but user can't see *exactly* which passage was cited.
- **How:** Show source chunks highlighted inside a PDF viewer pane (react-pdf + highlight overlay). Map chunk text → page number → bounding box.
- **Impact:** Strongest trust signal for a RAG demo. Interviewers ask "how do you know the answer is grounded?" — show them.

---

### Phase 4 — Differentiation

#### Metadata Filtering
- **Problem:** Multi-workspace isolates by collection, but within a workspace (10 docs across 5 years) no way to scope retrieval to `year=2024` or `doc_type=rbi_circular`.
- **How:** Tag chunks with `{source_type, year, doc_name}` at ingest. Pass optional `filter` param in `/api/chat` request. ChromaDB `where` clause on dense retrieval; BM25 pre-filters corpus to matching chunk IDs.
- **Impact:** Precision boost on time-scoped or source-scoped queries.

#### Document Comparison Mode
- **Problem:** No way to ask "What changed between RBI circular 2023 and 2024?"
- **How:** Frontend sends two doc IDs + comparison query. Backend retrieves relevant chunks from each collection separately, synthesises a structured diff answer.
- **Impact:** Killer fintech feature. Unique demo moment. Differentiates from generic RAG.

#### Agentic Mode (LangGraph)
- **Problem:** Single-shot RAG cannot handle multi-step reasoning: retrieve → compute → web search → synthesise.
- **How:** Replace `ConversationalRetrievalChain` with a LangGraph graph. Nodes: retriever, web_search, calculator, synthesiser. LLM decides which tool to call.
- **Impact:** Separates Prism from basic RAG — becomes a research agent. Strongest interview story.

---

## Roadmap Priority Matrix

```
HIGH impact × LOW effort  → Build first
  HyDE
  Multi-query retrieval
  Metadata filtering

HIGH impact × MEDIUM effort → Build second
  Contextual retrieval (+ re-ingest)
  Semantic chunking (+ re-ingest)
  Streaming responses

HIGH impact × HIGH effort → Build last
  Citation highlighting
  Document comparison
  Agentic mode (LangGraph)
```

---

## Interview Story Arc

```
v1  → Dense-only retrieval. No eval. No baseline.
v2  → Hybrid BM25+dense, cross-encoder rerank. Measured with RAGAS.
     → faithfulness=1.0, answer_relevancy=0.90 on 20-pair eval set.
+HyDE+MQ → RAGAS context_recall +X%. Concrete metric improvement.
+Contextual → RAGAS context_precision +Y%. Ingest-time LLM augmentation.
+Agentic  → Multi-step reasoning. Not RAG anymore — research agent.
```

Each step has a metric. That is the complete RAG engineering narrative for MNC DS interviews.
