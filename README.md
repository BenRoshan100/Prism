---
title: Prism
emoji: 💎
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Prism — Document Intelligence with Self-Scoring Retrieval

**Live demo:** https://askprism.vercel.app

Load any documents or URLs → Prism becomes an instant expert on that corpus. Ask multi-turn questions, get cited answers, and see retrieval quality scored on every response. Most RAG apps fail silently when retrieval breaks. Prism surfaces that signal.

---

## Why This Exists

Knowledge workers — analysts, researchers, lawyers, ops teams — spend hours manually reading documents to answer domain questions. Existing RAG systems retrieve context and generate plausible answers but give no signal on whether retrieval actually worked. When embeddings drift, when chunk boundaries split critical context, or when top-K misses the right passage, the LLM still produces a confident-sounding answer. It fails silently.

Prism adds an **eval layer on top of the chat interface**:
- **Faithfulness score** (LLM-as-Judge) on every answer — inline badge per message
- **RAGAS benchmark** (4 metrics: faithfulness, answer_relevancy, context_precision, context_recall) — pre-computed, shown on Eval tab
- **Retrieval health dashboard** — rolling faithfulness traffic light

If retrieval degrades, you see it before the user does.

---

## What It Does

- Upload PDFs, TXTs, or CSVs via drag-and-drop; ingest URLs directly
- Ask multi-turn questions with conversation memory (last 10 turns)
- Get answers with **inline source citations** (filename, page, similarity score, BM25 score, rerank score)
- See a **faithfulness badge** on every answer (1–5 scale, colour-coded)
- Switch between **isolated workspaces** — each workspace has its own document set
- View **RAGAS benchmark scores** and per-turn faithfulness log on the Eval tab

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  React 19 + Vite + Tailwind (Vercel)                     │
│  Workspace switcher | Chat | Eval | Upload               │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTP
┌────────────────────────▼─────────────────────────────────┐
│  FastAPI Backend (HF Spaces — Docker, 16GB)              │
│                                                          │
│  Upload / URL ingest                                     │
│  → ParentDocumentRetriever (child 200-char / parent 800) │
│  → Euron API embeddings (text-embedding-3-small)         │
│  → ChromaDB collection per workspace                     │
│  → BM25 index per workspace                              │
│                                                          │
│  Query                                                   │
│  → HybridRetriever (BM25 0.3 + dense 0.7 → RRF)         │
│  → CrossEncoder rerank top-10 → top-5 (TinyBERT ~17MB)  │
│  → ConversationalRetrievalChain                          │
│  → Groq llama-3.3-70b-versatile                          │
│  → LLM-as-Judge faithfulness score (1–5)                 │
│                                                          │
│  Web search path: Tavily advanced → condense → synthesise│
│  Observability: LangSmith traces all LLM + retrieval     │
└──────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| **Backend** | FastAPI + Uvicorn |
| **Vector store** | ChromaDB (persistent, per-workspace collection) |
| **Sparse retrieval** | rank_bm25 (BM25Okapi) |
| **Hybrid fusion** | Weighted RRF (dense 0.7 + sparse 0.3) |
| **Reranker** | cross-encoder/ms-marco-TinyBERT-L-2-v2 (~17MB) |
| **Embeddings** | Euron API `text-embedding-3-small` — API-based (avoids local model RAM cost) |
| **LLM** | Groq `llama-3.3-70b-versatile` via `langchain-groq` |
| **Orchestration** | LangChain `ConversationalRetrievalChain` |
| **Memory** | `ConversationBufferWindowMemory` (k=10 turns) |
| **Web search** | Tavily (advanced depth, 800-char truncation) |
| **Eval** | RAGAS (pre-computed JSON) + LLM-as-Judge per turn |
| **Observability** | LangSmith |
| **Frontend** | React 19 + Vite + Tailwind CSS v4 |
| **Deployment** | HF Spaces Docker (backend, 16GB RAM) + Vercel (frontend) |

---

## Eval Layer

### Per-turn Faithfulness
Every answer is scored 1–5 by an LLM judge against the retrieved chunks. Frontend renders a colour badge inline:
- **Green** — Faithful (4–5 / 5)
- **Yellow** — Moderate (3 / 5)
- **Red** — Low (1–2 / 5)

### RAGAS Benchmark
Four metrics evaluated against a 20-pair ground-truth set, run locally via `scripts/run_ragas_local.py` and committed as a static JSON. Dashboard reads from the file — no live eval latency.

| Metric | Score |
|--------|-------|
| faithfulness | 1.0 |
| answer_relevancy | 0.90 |
| context_precision | TBD |
| context_recall | TBD |

> Note: faithfulness 1.0 is directional — eval queries are matched to the demo corpus. Run on held-out queries for honest numbers.

### Precision@K
Batch Precision@K against 20 pre-built eval queries via `scripts/run_eval.py`.

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 20+
- [Groq API key](https://console.groq.com) — free tier works
- [Euron API key](https://euron.one) — used for embeddings only

### Backend

```bash
git clone https://github.com/BenRoshan100/Prism.git
cd Prism

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp .env.example .env
# Fill in GROQ_API_KEY and EURON_API_KEY

python scripts/run_ingest.py --data-dir sample_data
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

### Run RAGAS eval locally

```bash
python scripts/run_ragas_local.py --n 10
# Writes frontend/src/data/ragas_benchmark.json
```

---

## Deployment

| Service | Platform | Notes |
|---|---|---|
| Backend | HF Spaces (Docker) | 16GB RAM free tier. Runs as UID 1000. Port 7860. |
| Frontend | Vercel | Free tier, auto-deploys from `main` branch. |

### Backend on HF Spaces
1. huggingface.co → New Space → Docker → link this GitHub repo
2. Space Settings → Repository Secrets → add `GROQ_API_KEY`, `EURON_API_KEY`, `TAVILY_API_KEY`
3. Space auto-builds from `main` on push

### Frontend on Vercel
1. Vercel → Import repo → Root Directory: `frontend`
2. Set env var: `VITE_API_URL=https://<your-hf-username>-prism.hf.space/api`
3. Deploy

---

## Repository Structure

```
prism/
├── server/
│   ├── main.py              # FastAPI app, lifespan startup
│   ├── ingest.py            # Load → ParentDocumentRetriever → embed → store
│   ├── retriever.py         # HybridRetriever: dense + BM25 + RRF + reranker (cached per workspace)
│   ├── bm25_index.py        # BM25 singleton
│   ├── reranker.py          # CrossEncoder singleton (TinyBERT-L-2-v2)
│   ├── chain.py             # ConversationalRetrievalChain + web query path
│   ├── web_search.py        # Tavily search with content truncation
│   ├── url_loader.py        # URL ingestion with size guard
│   ├── memory.py            # ConversationBufferWindowMemory
│   ├── utils.py             # Config, logger, token counter
│   └── routes/
│       ├── chat.py          # POST /api/chat, DELETE /api/chat/memory
│       ├── upload.py        # POST /api/upload
│       ├── eval.py          # GET /api/eval/session, POST /api/eval/precision
│       └── workspaces.py    # Workspace CRUD
│
├── frontend/src/
│   ├── App.jsx              # Workspace switcher + tab nav
│   ├── api.js               # Axios client
│   └── components/
│       ├── Sidebar.jsx      # Workspace list + doc list
│       ├── ChatArea.jsx     # Chat UI (remounts on workspace switch)
│       ├── MessageBubble.jsx # Answer + faithfulness badge + web sources
│       ├── EvalPanel.jsx    # RAGAS scorecard + session log
│       └── FileUpload.jsx   # Drag-and-drop upload
│
├── scripts/
│   ├── run_ingest.py        # CLI ingestion
│   ├── run_eval.py          # CLI Precision@K
│   └── run_ragas_local.py   # Local RAGAS eval → writes ragas_benchmark.json
│
├── data/ground_truth/
│   └── eval_pairs.json      # 20 query/chunk pairs with ground_truth answers
│
├── sample_data/             # Demo documents
├── config.yaml              # All tunable params
├── Dockerfile
└── requirements.txt
```

---

## Design Decisions Worth Noting

- **Singleton retriever cache per workspace** — without cache, every request rebuilt the Chroma instance (full embedding reload). Cache invalidated after ingest.
- **CPU-only torch in Dockerfile** — sentence-transformers pulls CUDA torch (~2GB) by default. Pre-installing CPU torch keeps the image lean.
- **HF Spaces UID 1000** — HF runs Docker containers as user 1000. Reranker weights baked under `HF_HOME=/app/.cache/huggingface` as user 1000 at build time; `HF_HUB_OFFLINE=1` set after download to block runtime Hub calls.
- **RAGAS pre-computed locally** — `nest_asyncio` cannot patch `uvloop` (uvicorn's event loop on Linux). Live RAGAS eval always 500s. Run locally, commit JSON, Vercel reads file.
- **TinyBERT-L-2-v2 reranker** — same ranking quality as MiniLM-L-6-v2 at demo corpus scale; ~17MB vs ~85MB.
- **Web search bypasses chain** — `ConversationalRetrievalChain` condensation step strips prepended Tavily context before LLM sees it. Web path uses direct LLM call with chat history.
- **Idempotent ingestion** — chunk IDs are `md5(source + page + text)`. Re-ingesting same doc does not duplicate chunks.

---

## Author

**Ben Roshan D** — [github.com/BenRoshan100](https://github.com/BenRoshan100)

Built as a portfolio project demonstrating production RAG with a full evaluation layer. The retrieval scoring and RAGAS integration are the differentiators — most RAG portfolios skip eval entirely.
