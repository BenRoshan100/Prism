# Prism — Document Intelligence Platform

**Live demo:** https://askprism.vercel.app

Upload any PDF, TXT, CSV, or URL and ask questions. Prism retrieves answers with inline source citations, scores its own retrieval quality, and auto-briefs you on every document you upload.

---

## What It Does

- **Multi-format ingestion** — drag-and-drop files (PDF, TXT, CSV) or paste a URL
- **Auto-briefing** — on every upload, Prism generates a 5-bullet summary and 3 suggested questions
- **Inline citations** — answers include clickable `[1]` `[2]` superscripts that scroll to the source chunk
- **Multi-workspace** — keep documents isolated in separate workspaces; switch without a page reload
- **Web search** — toggle Tavily web search to augment answers beyond your uploaded docs
- **Faithfulness scoring** — every answer gets an LLM-as-Judge score (1–5) rendered as a green/yellow/red badge
- **Conversation memory** — multi-turn chat with the last 10 turns in context
- **Eval suite** — batch Precision@K against 20 ground-truth queries

---

## Retrieval Stack

```
Query
  │
  ├─ HyDE (optional) ──▶ LLM generates hypothetical answer ──▶ used for dense search
  │
  ├─ Dense retrieval ──▶ ChromaDB ANN (Euron text-embedding-3-small)
  └─ Sparse retrieval ─▶ BM25Okapi
          │
          ▼
     RRF fusion (weighted, k=60)
          │
          ▼
  CrossEncoder reranker (ms-marco-MiniLM-L-6-v2)
          │
          ▼
  Top-K chunks → Groq LLM (llama-3.3-70b-versatile) → Answer + citations
```

---

## Architecture

```
┌──────────────┐       ┌──────────────────────────────────────────┐
│  React UI    │       │  FastAPI Backend                         │
│  (Vercel)    │─HTTP─▶│                                          │
└──────────────┘       │  Upload/URL ──▶ Chunk ──▶ Embed          │
                       │                           │              │
                       │               ChromaDB  BM25             │
                       │  (per-workspace collections + indexes)   │
                       │                     │                    │
                       │              HyDE (optional)             │
                       │              RRF fusion                  │
                       │              CrossEncoder rerank         │
                       │                     │                    │
                       │          Groq LLM (llama-3.3-70b)        │
                       │          + Faithfulness scorer           │
                       │          + Briefing generator            │
                       │                                          │
                       │  (Render — Docker, free tier)            │
                       └──────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| **Backend** | FastAPI + Uvicorn |
| **Vector store** | ChromaDB (persistent, on-disk, per-workspace collections) |
| **Embeddings** | Euron API (`text-embedding-3-small`, OpenAI-compatible) |
| **Sparse retrieval** | BM25Okapi (`rank-bm25`) |
| **Reranker** | CrossEncoder `ms-marco-MiniLM-L-6-v2` (via `sentence-transformers`) |
| **LLM** | Groq (`llama-3.3-70b-versatile`) via `langchain-groq` |
| **Web search** | Tavily API |
| **URL ingestion** | httpx + BeautifulSoup4 |
| **Orchestration** | LangChain `ConversationalRetrievalChain` |
| **Memory** | `ConversationBufferWindowMemory` (k=10 turns) |
| **Frontend** | React 19 + Vite + Tailwind CSS v4 |
| **Deployment** | Backend on Render (Docker), Frontend on Vercel |

---

## Repository Structure

```
Prism/
├── server/
│   ├── main.py              # App entrypoint, CORS, lifespan
│   ├── ingest.py            # Load → chunk → embed → store
│   ├── retriever.py         # HybridRetriever: dense + BM25 + RRF + rerank + HyDE
│   ├── chain.py             # QA chain, HyDE, web search path
│   ├── briefing.py          # Auto-briefing on upload (5 bullets + 3 questions)
│   ├── url_loader.py        # httpx + BeautifulSoup URL ingestion
│   ├── bm25_index.py        # Per-workspace BM25 index singletons
│   ├── reranker.py          # CrossEncoder reranking
│   ├── memory.py            # Conversation memory
│   ├── utils.py             # Config loader, logger
│   ├── routes/
│   │   ├── chat.py          # POST /chat
│   │   ├── upload.py        # POST /upload, POST /upload/url, GET/DELETE /documents
│   │   ├── workspaces.py    # GET /workspaces, DELETE /workspaces/{id}
│   │   └── eval.py          # POST /eval
│   └── eval/
│       ├── precision.py     # Precision@K
│       ├── faithfulness.py  # LLM-as-Judge scorer
│       └── ragas_eval.py    # RAGAS metrics runner
│
├── frontend/src/
│   ├── App.jsx
│   ├── api.js
│   └── components/
│       ├── Sidebar.jsx       # Workspace switcher, file upload, briefing card, doc list
│       ├── FileUpload.jsx    # File + URL tab
│       ├── ChatArea.jsx      # Chat input, message thread
│       ├── MessageBubble.jsx # Inline citation rendering
│       └── SourceExpander.jsx
│
├── scripts/
│   ├── run_ingest.py
│   ├── run_eval.py
│   ├── benchmark_chunks.py
│   └── run_ragas_local.py
│
├── tests/
│   ├── test_url_loader.py
│   ├── test_briefing.py
│   └── test_*.py
│
├── data/ground_truth/eval_pairs.json
├── config.yaml
├── Dockerfile
├── render.yaml
└── requirements.txt
```

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 20+
- [Groq API key](https://console.groq.com) — free tier works
- [Euron API key](https://euron.one) — used for embeddings only
- [Tavily API key](https://tavily.com) — optional, for web search

### Backend

```bash
git clone https://github.com/BenRoshan100/Prism.git
cd Prism

python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

pip install -r requirements.txt

cp .env.example .env
# Fill in GROQ_API_KEY, EURON_API_KEY, and optionally TAVILY_API_KEY

uvicorn server.main:app --reload
# Backend at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Frontend at http://localhost:5173
```

---

## Configuration

[`config.yaml`](config.yaml) controls all retrieval parameters:

```yaml
chunking:
  chunk_size: 500
  chunk_overlap: 50

retrieval:
  collection_name: "prism"
  dense_weight: 0.7
  sparse_weight: 0.3
  retrieve_k: 10
  rerank_k: 5
  hyde_enabled: false       # set true to enable HyDE query expansion

memory:
  max_token_limit: 2000

llm:
  model: "llama-3.3-70b-versatile"
  max_tokens: 1000
  temperature: 0.1

eval:
  ground_truth_path: "data/ground_truth/eval_pairs.json"
  precision_k: 5
```

**HyDE** (`hyde_enabled: true`) — before searching ChromaDB, Prism asks the LLM to generate a hypothetical 2-sentence answer and embeds that instead of the raw query. This closes the query-document embedding gap for short or vague queries. BM25 and the reranker still use the original query.

---

## Eval Suite

```bash
# Batch Precision@K against 20 ground-truth queries
python scripts/run_eval.py

# Benchmark chunk sizes (200/300/500/750/1000) and plot results
python scripts/benchmark_chunks.py --data-dir sample_data

# Full RAGAS eval (faithfulness, answer_relevancy, context_precision, context_recall)
python scripts/run_ragas_local.py
```

---

## Deployment

| Service | Platform | Notes |
|---|---|---|
| Backend | Render (Docker) | Free tier, 512MB RAM. API-based embeddings keep memory ~150MB. |
| Frontend | Vercel | Free tier, auto-deploys from `main`. |

**Backend on Render:** connect repo, set `GROQ_API_KEY`, `EURON_API_KEY`, `TAVILY_API_KEY`.

**Frontend on Vercel:** set `VITE_API_URL=https://prism.onrender.com/api`.

CORS is configured with a regex matching all `*.vercel.app` origins so preview deployments work automatically.

---

## Design Decisions

- **Hybrid retrieval over pure dense** — BM25 catches exact-match queries (ticker symbols, regulation names) that dense retrieval misses. RRF fusion combines both without a tuned interpolation weight.
- **CrossEncoder reranker as final gate** — bi-encoder similarity scores are noisy at the margin. A CrossEncoder re-scores the top-K with full query-document attention, consistently improving final precision.
- **HyDE for vague queries** — short queries have low information density in embedding space. A hypothetical answer lands closer to real answer chunks. Toggle in config, ~200ms overhead per query.
- **Per-workspace ChromaDB collections** — workspace isolation is just a collection name; no new infrastructure needed. BM25 indexes are kept in a dict keyed by workspace ID.
- **API embeddings over local model** — local `sentence-transformers` loads ~400MB into RAM and crashes Render's free tier on startup. Euron API drops backend memory to ~150MB.
- **Briefing as non-critical path** — briefing generation runs after ingest and returns `null` on failure. Upload never blocks on a failed LLM call.
- **Idempotent ingestion** — chunk IDs are `md5(source + page + text)`. Re-running ingestion never duplicates chunks.

---

## Author

**Ben Roshan D** — [github.com/BenRoshan100](https://github.com/BenRoshan100)
