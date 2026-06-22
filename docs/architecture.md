# Architecture — Prism

## Problem
Fintech analysts spend hours manually reading RBI circulars, NPCI reports, and earnings transcripts. Standard dense-only RAG fails silently and misses exact keyword matches in regulatory text (section numbers, policy codes).

## Architecture overview
Query → hybrid retrieval (ChromaDB dense + BM25 sparse) → weighted RRF fusion → cross-encoder rerank (top-10 → top-5) → LLM answer → LangSmith trace. ParentDocumentRetriever stores 200-char child chunks for retrieval but returns 800-char parent chunks to LLM. Multi-workspace: each workspace has its own ChromaDB collection; vectorstore + retriever cached per workspace to prevent OOM on repeated queries. Eval runs offline via `scripts/run_eval_versioned.py`; results served by a separate `eval-dashboard/` static site.

## Component breakdown

| Component | Technology | Purpose |
|-----------|------------|---------|
| Vector store | ChromaDB (persistent) | Dense embedding storage and retrieval |
| Sparse retrieval | rank_bm25 (BM25Okapi) | Keyword-match retrieval for regulatory text |
| Hybrid fusion | Weighted RRF (dense 0.7 + sparse 0.3) | Merge dense + sparse result lists |
| Reranker | cross-encoder/ms-marco-TinyBERT-L-2-v2 | Re-score top-10 → return top-5 (~17MB; chosen over MiniLM-L-6-v2 ~85MB for lower memory footprint) |
| Embeddings | Euron API (text-embedding-3-small) | API-based; Groq has no embeddings endpoint. |
| LLM | Groq (llama-3.3-70b-versatile) via langchain-groq | Fast open-weight inference; OpenAI-compatible |
| Chunking | LangChain ParentDocumentRetriever | Child 200-char indexed, parent 800-char sent to LLM |
| Memory | ConversationBufferWindowMemory (k=10) | Last 10 conversation turns |
| Chain | ConversationalRetrievalChain | LangChain orchestration |
| Workspace | ChromaDB collection per workspace | Isolated document sets; switcher in frontend sidebar |
| Retriever cache | Module-level dict keyed by workspace | Singleton vectorstore+retriever per workspace; invalidate on ingest |
| Eval | Separate `eval-dashboard/` Vite+React static site | Reads versioned JSON run files; metrics: answer_correctness, answer_relevancy, context_recall, precision@5, latency p50/p95/p99 |
| Eval script | `scripts/run_eval_versioned.py` | Runs offline against 50-pair ground truth; writes versioned JSON + updates index.json |
| Eval ground truth | `data/ground_truth/eval_pairs.json` (50 pairs) | Multi-hop, comparative, negative, numeric, edge-case questions with reference answers |
| Observability | LangSmith | Traces all LLM + retrieval calls via LANGCHAIN_TRACING_V2=true |
| Document parsing | LlamaParse (primary), pypdf (fallback) | PDF extraction |
| Backend | FastAPI + Uvicorn | REST API |
| Frontend | React 19 + Vite + Tailwind CSS v4 | Chat / Upload tabs |
| Deployment | HF Spaces (Docker backend, 16GB RAM) + Vercel (frontend) + Vercel (eval-dashboard) | Production |

## Data flow

### Ingestion
1. `run_ingest.py` or `POST /api/upload` → load PDFs/TXT/CSV
2. `ParentDocumentRetriever`: split into 800-char parent + 200-char child chunks
3. Embed child chunks via Euron API (text-embedding-3-small) → store in ChromaDB
4. Store parent chunks in `InMemoryStore`
5. Build BM25 index over child chunk corpus

### Query
1. `POST /api/chat` receives question
2. `dense_retrieve`: ChromaDB top-10 by cosine similarity (workspace-specific collection)
3. `sparse_retrieve`: BM25 top-10 by keyword score
4. `reciprocal_rank_fusion`: merge → deduplicate → RRF score
5. `Reranker.rerank`: cross-encoder score → return top-5 parent chunks
6. `ConversationalRetrievalChain`: LLM answers with context + memory
7. Response includes: answer, sources (with scores), retrieval_method

## Key design decisions
- **API embeddings over local**: Euron API embeddings ~0MB RAM; Groq has no embeddings endpoint so Euron is retained for embeddings.
- **ParentDocumentRetriever**: small chunks improve retrieval precision; large parent chunks improve answer faithfulness
- **Cross-encoder reranker**: bi-encoder (ChromaDB) is fast but approximate; cross-encoder is slower but more accurate on top-20 pool
- **BM25 weight 0.3**: regulatory text has exact keyword matches (section numbers); sparse retrieval catches what dense misses
- **RAGAS benchmark pre-computed locally**: `nest_asyncio` cannot patch `uvloop` (used by uvicorn on Linux), making live RAGAS eval impossible on prod. Run `scripts/run_ragas_local.py` locally, commit JSON results, Vercel builds dashboard from file.
- **TinyBERT-L-2-v2 reranker**: MiniLM-L-6-v2 (~85MB) vs TinyBERT-L-2-v2 (~17MB) — same ranking quality at demo corpus scale with lower memory footprint.
- **Singleton vectorstore/retriever cache**: each workspace caches its Chroma vectorstore + HybridRetriever in a module-level dict. Without cache, every chat request created a new Chroma instance (full embedding reload). Cache is invalidated after ingest.
- **Multi-workspace isolation**: each workspace maps to one ChromaDB collection. Frontend workspace switcher passes `workspace_id` on every request; backend resolves the correct collection before retrieval.
- **URL size guard**: `url_loader.py` enforces a max content size before embedding URL content, preventing memory spikes from large external pages.
- **Eval dashboard separate site**: eval runs offline, results versioned as JSON. Separates eval tooling from user-facing app; no live eval endpoint on prod backend. Per-message faithfulness badge removed from UI — moved to dedicated dashboard.
- **answer_correctness over faithfulness**: faithfulness (LLM judge vs retrieved chunks) is circular — inflates when eval pairs are corpus-aligned. answer_correctness (LLM judge vs ground_truth reference) is an independent signal.
- **HF Spaces Docker (UID 1000)**: model weights baked into image under `HF_HOME=/app/.cache/huggingface` as user 1000 at build time; `HF_HUB_OFFLINE=1` set after download to block runtime network calls.

## Known limitations
- InMemoryStore for parent chunks: does not survive server restart (re-ingest required)
- BM25 index rebuilt in memory on each startup (not persisted to disk)
- HF Spaces free tier: ephemeral filesystem — chroma_db lost on cold start (re-upload required)
- Euron embedding API sequential: ~5s/chunk — 30 chunks = ~150s blocking upload

## Future improvements
- Persist BM25 index to disk (pickle)
- Move Euron embedding to background task (return 202, poll for ready)
- Streaming responses from LLM
