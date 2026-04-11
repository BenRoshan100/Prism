# FinRAG — Fintech Research Agent with Self-Scoring Retrieval

**Live demo:** https://fin-rag-git-main-benroshan100s-projects.vercel.app/

A conversational RAG system for fintech documents (RBI circulars, NPCI reports, earnings transcripts) that **scores its own retrieval quality** per query. Most RAG apps ship without telling you when retrieval is silently failing. FinRAG surfaces that signal.

---

## Why This Exists

Fintech analysts spend hours manually reading policy circulars, earnings calls, and regulator reports to answer domain questions. Existing RAG systems retrieve context and generate plausible answers — but give you no signal on whether the retrieval actually worked. When embeddings drift, when chunk boundaries split critical context, or when the top-K misses the right passage, the LLM still produces a confident-sounding answer. It fails silently.

FinRAG adds an **eval layer on top of the chat interface**:
- **Faithfulness score** (LLM-as-Judge) on every answer — green/yellow/red badge inline
- **Precision@K** against a ground-truth set of fintech queries
- **Retrieval health dashboard** — traffic light based on rolling faithfulness

If retrieval degrades, you see it before the user does.

---

## What It Does

- Upload PDFs, TXTs, or CSVs via drag-and-drop
- Ask multi-turn questions with conversation memory (last 10 turns)
- Get answers with **inline source citations** (filename, page, similarity score)
- See a **faithfulness badge** on every answer (1-5 scale, green/yellow/red)
- Run **batch Precision@K** against 20 pre-built fintech eval queries
- Watch a **retrieval health indicator** that turns red when quality drops

---

## Architecture

```
┌──────────────┐       ┌─────────────────────────────────────┐
│  React UI    │       │  FastAPI Backend                    │
│  (Vercel)    │─HTTP─▶│  ┌───────────────────────────────┐  │
└──────────────┘       │  │  Upload → Chunk → Embed       │  │
                       │  │  (Euron API embeddings)       │  │
                       │  └──────────────┬────────────────┘  │
                       │                 ▼                   │
                       │  ┌───────────────────────────────┐  │
                       │  │  ChromaDB (on-disk vectors)   │  │
                       │  └──────────────┬────────────────┘  │
                       │                 ▼                   │
                       │  ┌───────────────────────────────┐  │
                       │  │  Retrieve top-K + score       │  │
                       │  │  ConversationalRetrievalChain │  │
                       │  │  LLM: Euron (gpt-4.1-mini)    │  │
                       │  └──────────────┬────────────────┘  │
                       │                 ▼                   │
                       │  ┌───────────────────────────────┐  │
                       │  │  Faithfulness scorer          │  │
                       │  │  (LLM-as-Judge, 1-5)          │  │
                       │  └───────────────────────────────┘  │
                       │  (Render — Docker, free tier)       │
                       └─────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| **Backend** | FastAPI + Uvicorn |
| **Vector store** | ChromaDB (persistent, on-disk) |
| **Embeddings** | Euron API (`text-embedding-3-small`) — API-based to fit Render free tier |
| **LLM** | Euron API (`gpt-4.1-mini`) via OpenAI-compatible SDK |
| **Orchestration** | LangChain `ConversationalRetrievalChain` |
| **Memory** | `ConversationBufferWindowMemory` (k=10 turns) |
| **Frontend** | React 19 + Vite + Tailwind CSS v4 |
| **Deployment** | Backend on Render (Docker), Frontend on Vercel |

---

## Key Features (The Eval Layer)

### 1. Faithfulness Scoring
Every answer is passed back to the LLM with an eval prompt that scores 1-5 how well the answer is grounded in the retrieved chunks. The frontend renders a colored badge inline:
- 🟢 **Faithful** (4-5/5)
- 🟡 **Moderate** (3/5)
- 🔴 **Low** (1-2/5)

### 2. Precision@K Benchmarking
20 ground-truth query/source pairs covering UPI, banking, lending, and RBI policy. The Eval Dashboard runs them all and reports mean Precision@5 plus per-query breakdown.

### 3. Chunk Size Benchmarking
`scripts/benchmark_chunks.py` wipes the index and re-ingests at different chunk sizes (200/300/500/750/1000), runs Precision@K at each, and produces a PNG chart showing which chunk size works best for your corpus.

### 4. Retrieval Health Dashboard
Traffic-light indicator based on rolling faithfulness scores. Red = retrieval is degrading, yellow = mixed, green = healthy.

---

## Repository Structure

```
finrag/
├── server/              # FastAPI backend
│   ├── main.py          # App entrypoint, CORS, lifespan
│   ├── routes/          # chat.py, eval.py, upload.py
│   ├── ingest.py        # Load → chunk → embed → store (idempotent)
│   ├── retriever.py     # Query ChromaDB, return top-K + scores
│   ├── chain.py         # ConversationalRetrievalChain assembly
│   ├── memory.py        # Conversation memory management
│   ├── eval/
│   │   ├── precision.py     # Precision@K computation
│   │   └── faithfulness.py  # LLM-as-Judge scorer
│   └── utils.py
│
├── frontend/            # React 19 + Vite + Tailwind
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       └── components/  # ChatTab, EvalDashboard, MessageBubble, SourceExpander
│
├── scripts/
│   ├── run_ingest.py         # CLI: ingest documents
│   ├── run_eval.py           # CLI: batch Precision@K
│   └── benchmark_chunks.py   # CLI: benchmark across chunk sizes
│
├── data/ground_truth/
│   └── eval_pairs.json       # 20 query/source pairs for Precision@K
│
├── sample_data/              # Sample fintech documents
├── config.yaml               # Chunking, retrieval, eval params
├── Dockerfile                # Backend-only (frontend deploys to Vercel)
├── render.yaml               # Render Blueprint
└── requirements.txt
```

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 20+
- A Euron API key (https://euron.one) — free tier works

### Backend

```bash
# Clone
git clone https://github.com/BenRoshan100/fin-rag.git
cd fin-rag

# Python deps
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# Env var
echo EURON_API_KEY=your_key_here > .env

# Ingest sample documents
python scripts/run_ingest.py --data-dir sample_data

# Start backend
uvicorn server.main:app --reload
# Backend now at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Frontend at http://localhost:5173
```

Open http://localhost:5173 and ask a question.

---

## Running the Eval Suite

### Batch Precision@K
```bash
python scripts/run_eval.py
```
Runs all 20 ground-truth queries and prints mean Precision@5 plus per-query scores. Saves results to `eval_results_<timestamp>.json`.

### Chunk size benchmark
```bash
python scripts/benchmark_chunks.py --data-dir sample_data
```
Re-ingests at chunk sizes 200/300/500/750/1000, runs Precision@K at each, and saves a comparison chart as `benchmark_precision_<timestamp>.png`. Use this to pick the optimal chunk size for your documents.

---

## Deployment

The app is split across two free-tier platforms:

| Service | Platform | Notes |
|---|---|---|
| Backend | Render (Docker) | Free tier, 512MB RAM. API-based embeddings keep it within the limit. |
| Frontend | Vercel | Free tier, auto-deploys from `main` branch. |

### Backend on Render
1. Push to GitHub
2. Render → New Web Service → connect repo (runtime: Docker)
3. Set env var: `EURON_API_KEY`
4. Deploy

### Frontend on Vercel
1. Vercel → Import repo
2. Root Directory: `frontend`
3. Framework: Vite (auto-detected)
4. Set env var: `VITE_API_URL=https://<your-backend>.onrender.com/api`
5. Deploy

CORS is configured with a regex that accepts all `*.vercel.app` origins, so preview deployments work automatically.

### Why API-based embeddings?
The original design used `sentence-transformers/all-MiniLM-L6-v2` for local embeddings. That loads a ~400MB PyTorch model into RAM, which **crashes Render's 512MB free tier on startup**. Swapping to API-based embeddings (Euron's OpenAI-compatible endpoint) drops backend memory to ~150MB and keeps everything free.

---

## Configuration

Edit [`config.yaml`](config.yaml):

```yaml
chunking:
  chunk_size: 500
  chunk_overlap: 50

retrieval:
  k: 5
  collection_name: "finrag"

memory:
  max_token_limit: 2000

llm:
  model: "gpt-4.1-mini"
  base_url: "https://api.euron.one/api/v1/euri"
  max_tokens: 1000
  temperature: 0.1

eval:
  ground_truth_path: "data/ground_truth/eval_pairs.json"
  precision_k: 5
```

---

## Design Decisions Worth Noting

- **Idempotent ingestion** — documents get hashed to deterministic IDs. Re-running ingestion doesn't duplicate chunks.
- **Content-hash chunk IDs** — `md5(source + page + text)` means the same chunk always gets the same ID, even across re-runs.
- **CORS regex over exact match** — Vercel generates a unique preview URL per deploy. A regex match on `*.vercel.app` handles all of them without needing to update env vars.
- **Lifespan events over startup events** — FastAPI's modern lifespan context manager initializes the chain once at boot and attaches it to `app.state`.
- **API embeddings over local** — traded a local model for an API call. Makes each upload slightly slower, but the backend fits in free-tier RAM.

---

## Author

**Ben Roshan D** — [github.com/BenRoshan100](https://github.com/BenRoshan100)

Built as a portfolio project demonstrating production RAG with observability. The eval layer is the differentiator — most RAG portfolios skip it.
