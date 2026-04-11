# FinRAG — Fintech Research Agent with Persistent Memory
## Product Requirements Document (PRD) for Claude Code

**Version:** 1.1
**Author:** Ben Roshan D
**Date:** April 2026
**Status:** Built & deploying

---

## 1. Project Overview

### 1.1 Problem Statement
Fintech professionals and analysts spend hours manually reading RBI circulars, earnings call transcripts, and NPCI reports to answer domain questions. Existing RAG systems retrieve context but provide no signal on whether retrieval is actually working — they fail silently.

### 1.2 Solution
FinRAG is a production-grade conversational research agent that:
- Ingests fintech documents (PDFs, text) into a persistent vector store
- Answers multi-turn questions with conversation memory
- Evaluates its own retrieval quality (Precision@K, Faithfulness score) per query
- Surfaces eval metrics in a dedicated dashboard tab

### 1.3 What Makes It Different
Most RAG portfolios ship without retrieval evaluation. FinRAG adds a self-scoring eval layer — Precision@K and LLM-as-Judge faithfulness scoring — so retrieval degradation is visible before users notice it.

### 1.4 Target Audience (for README framing)
- Fintech analysts querying RBI policy, UPI stats, earnings data
- DS/AI interviewers evaluating production RAG architecture understanding

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Vector store | ChromaDB (persistent, local) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (free, no API cost) |
| LLM | Euron API (`gpt-4.1-mini`) via `openai` SDK (base_url: `https://api.euron.one/api/v1/euri`) |
| Memory | LangChain `ConversationBufferWindowMemory` (k=10 turns) |
| Orchestration | LangChain `ConversationalRetrievalChain` |
| Document loading | `pypdf`, `langchain_community.document_loaders` (PDF, TXT, CSV) |
| Chunking | `RecursiveCharacterTextSplitter` |
| Eval | Custom Python module — no external eval library |
| Backend API | FastAPI + Uvicorn |
| Frontend | React 19 (Vite + Tailwind CSS v4) |
| Deployment | Backend on Render (Docker), Frontend on Vercel. Repo: https://github.com/BenRoshan100/fin-rag.git |
| Config | `.env` for API keys, `config.yaml` for chunking/retrieval params |

---

## 3. Directory Structure

```
finrag/
├── data/
│   ├── raw/                        # Drop PDFs here
│   │   ├── rbi_annual_report_2024.pdf
│   │   ├── npci_upi_report_2024.pdf
│   │   └── bajaj_finance_q3_2024_transcript.txt
│   └── ground_truth/
│       └── eval_pairs.json         # 20 query/relevant-chunk pairs for Precision@K
│
├── server/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entrypoint
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── chat.py                 # POST /api/chat, DELETE /api/chat/memory
│   │   └── eval.py                 # GET /api/eval/session, POST /api/eval/precision
│   ├── ingest.py                   # Document loading, chunking, embedding, ChromaDB storage
│   ├── retriever.py                # Query ChromaDB, return top-K chunks with metadata
│   ├── memory.py                   # ConversationBufferMemory setup and management
│   ├── chain.py                    # LangChain QA chain combining retriever + memory + LLM
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── precision.py            # Precision@K computation against ground truth
│   │   └── faithfulness.py         # LLM-as-Judge faithfulness scorer
│   └── utils.py                    # Logging, config loader, token counter
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx                # React entrypoint
│       ├── App.jsx                 # Root component with tab navigation
│       ├── api.js                  # Axios client for FastAPI backend
│       ├── components/
│       │   ├── ChatTab.jsx         # Chat interface
│       │   ├── EvalDashboard.jsx   # Eval metrics dashboard
│       │   ├── MessageBubble.jsx   # Chat message component
│       │   └── SourceExpander.jsx  # Source chunk expander component
│       └── index.css               # Tailwind imports
│
├── scripts/
│   ├── run_ingest.py               # CLI: python scripts/run_ingest.py --data-dir data/raw
│   └── run_eval.py                 # CLI: python scripts/run_eval.py --queries data/ground_truth/eval_pairs.json
│
├── tests/
│   ├── test_ingest.py
│   ├── test_retriever.py
│   ├── test_chain.py
│   └── test_eval.py
│
├── requirements.txt                # Python backend dependencies
├── .env.example
├── config.yaml
├── Dockerfile
├── .gitignore
│
└── chroma_db/                      # Auto-created by ChromaDB, gitignored
```

---

## 4. Module Specifications

### 4.1 `server/ingest.py`

**Purpose:** Load documents from `data/raw/`, chunk them, embed them, store in ChromaDB.

**Functions to implement:**

```python
def load_documents(data_dir: str) -> list[Document]:
    """
    Load all PDFs and .txt files from data_dir.
    Use PyPDFLoader for PDFs, TextLoader for .txt.
    Return list of LangChain Document objects with metadata:
    - source: filename
    - page: page number (PDFs only)
    """

def chunk_documents(documents: list[Document], chunk_size: int = 500, chunk_overlap: int = 50) -> list[Document]:
    """
    Split documents using RecursiveCharacterTextSplitter.
    chunk_size and chunk_overlap from config.yaml.
    Preserve metadata from parent document.
    Add chunk_index to metadata.
    """

def embed_and_store(chunks: list[Document], collection_name: str = "finrag") -> Chroma:
    """
    Embed chunks using HuggingFaceEmbeddings (all-MiniLM-L6-v2).
    Store in ChromaDB at ./chroma_db.
    If collection already exists, skip re-embedding (idempotent).
    Return Chroma retriever object.
    """

def run_ingestion_pipeline(data_dir: str) -> Chroma:
    """
    Orchestrates: load → chunk → embed → store.
    Print progress: N docs loaded, N chunks created, stored in ChromaDB.
    """
```

**Important:** Ingestion must be idempotent. Running twice should not duplicate chunks. Use document hash as ChromaDB document ID.

---

### 4.2 `server/retriever.py`

**Purpose:** Query ChromaDB and return top-K chunks with similarity scores and metadata.

```python
def get_retriever(collection_name: str = "finrag", k: int = 5) -> VectorStoreRetriever:
    """
    Load existing ChromaDB collection.
    Return LangChain retriever with k=5 (from config.yaml).
    """

def retrieve_with_scores(query: str, k: int = 5) -> list[dict]:
    """
    Return list of dicts:
    [
      {
        "content": "chunk text...",
        "source": "rbi_annual_report_2024.pdf",
        "page": 12,
        "chunk_index": 34,
        "similarity_score": 0.87
      },
      ...
    ]
    """
```

---

### 4.3 `server/memory.py`

**Purpose:** Manage conversation memory across turns.

```python
def create_memory(memory_key: str = "chat_history", max_token_limit: int = 2000) -> ConversationBufferMemory:
    """
    Create LangChain ConversationBufferMemory.
    memory_key = "chat_history"
    return_messages = True
    max_token_limit = 2000 (truncate oldest messages when exceeded)
    """

def get_memory_as_string(memory: ConversationBufferMemory) -> str:
    """
    Return conversation history as formatted string for display in UI.
    """

def clear_memory(memory: ConversationBufferMemory) -> None:
    """
    Clear all messages. Called on "New Conversation" button.
    """
```

---

### 4.4 `server/chain.py`

**Purpose:** Assemble the full RAG + memory chain. Core of the application.

```python
def build_qa_chain(retriever, memory) -> ConversationalRetrievalChain:
    """
    Build LangChain ConversationalRetrievalChain:
    - LLM: Euron API (gpt-4.1-mini) via ChatOpenAI with base_url="https://api.euron.one/api/v1/euri"
    - Retriever: from retriever.py
    - Memory: from memory.py
    - return_source_documents: True
    - verbose: False
    
    System prompt to inject:
    "You are FinRAG, a fintech research assistant. Answer questions using 
    only the provided context. If the answer is not in the context, say 
    'I could not find this in the loaded documents.' Do not hallucinate. 
    Be concise and cite your source document."
    """

def run_query(chain, question: str) -> dict:
    """
    Run chain on question.
    Return:
    {
      "answer": "...",
      "source_documents": [...],
      "question": "..."
    }
    """
```

---

### 4.5 `server/eval/precision.py`

**Purpose:** Compute Precision@K against a ground truth set.

**Ground truth format (`data/ground_truth/eval_pairs.json`):**
```json
[
  {
    "query": "What was India's UPI transaction volume in FY24?",
    "relevant_sources": ["npci_upi_report_2024.pdf"],
    "relevant_chunk_keywords": ["billion transactions", "FY2024", "NPCI"]
  },
  ...
]
```

```python
def compute_precision_at_k(query: str, retrieved_chunks: list[dict], ground_truth: dict, k: int = 5) -> float:
    """
    Precision@K = (relevant chunks in top-K) / K
    
    A chunk is "relevant" if:
    - Its source matches ground_truth["relevant_sources"], OR
    - Its content contains any keyword from ground_truth["relevant_chunk_keywords"]
    
    Return float between 0 and 1.
    """

def run_batch_precision_eval(eval_pairs_path: str, k: int = 5) -> dict:
    """
    Run precision@K for all queries in eval_pairs.json.
    Return:
    {
      "mean_precision_at_k": 0.74,
      "per_query_results": [
        {"query": "...", "precision_at_k": 0.8, "retrieved_sources": [...]},
        ...
      ]
    }
    """
```

---

### 4.6 `server/eval/faithfulness.py`

**Purpose:** Score whether the generated answer is faithful to the retrieved context using LLM-as-Judge.

```python
FAITHFULNESS_PROMPT = """
You are an evaluation judge. Given a context and an answer, score how faithful 
the answer is to the context on a scale of 1-5.

1 = Answer contradicts or ignores the context entirely
2 = Answer uses context minimally, adds significant unsupported claims  
3 = Answer mostly uses context with minor unsupported additions
4 = Answer is well-grounded in context with trivial additions only
5 = Answer is entirely and accurately derived from the context

Context:
{context}

Answer:
{answer}

Respond ONLY with valid JSON: {{"score": <int>, "reason": "<one sentence>"}}
"""

def score_faithfulness(answer: str, source_chunks: list[dict]) -> dict:
    """
    Call Euron API (gpt-4.1-mini) with FAITHFULNESS_PROMPT.
    Parse JSON response.
    Return:
    {
      "score": 4,
      "reason": "Answer accurately summarizes the retrieved UPI statistics.",
      "raw_response": "..."
    }
    Handle JSON parse errors gracefully — return score: -1 on failure.
    """
```

---

### 4.7 `server/utils.py`

```python
def load_config(config_path: str = "config.yaml") -> dict:
    """Load config.yaml and return as dict."""

def count_tokens(text: str) -> int:
    """Approximate token count: len(text.split()) * 1.3"""

def setup_logger(name: str) -> logging.Logger:
    """Return configured logger with timestamp format."""
```

---

### 4.8 `config.yaml`

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
  model: "gpt-5.3-instant"
  base_url: "https://api.euron.one/api/v1/euri"
  max_tokens: 1000
  temperature: 0.1

eval:
  ground_truth_path: "data/ground_truth/eval_pairs.json"
  precision_k: 5
```

---

## 5. FastAPI Backend + React Frontend

### 5.1 `server/main.py` — FastAPI Application

**Entry point.** Initializes FastAPI app, CORS middleware, and includes route modules.

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.routes import chat, eval

app = FastAPI(title="FinRAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(eval.router, prefix="/api")

# On startup: initialize chain, memory, retriever as app state
@app.on_event("startup")
def startup():
    app.state.memory = create_memory()
    retriever = get_retriever()
    app.state.chain = build_qa_chain(retriever, app.state.memory)
    app.state.eval_log = []
```

---

### 5.2 `server/routes/chat.py` — Chat API

```python
# POST /api/chat
# Request:  { "question": "What was UPI volume in FY24?" }
# Response: {
#   "answer": "...",
#   "sources": [{ "content", "source", "page", "chunk_index", "similarity_score" }],
#   "faithfulness": { "score": 4, "reason": "..." }
# }

# DELETE /api/chat/memory
# Clears conversation memory. Returns { "status": "cleared" }
```

---

### 5.3 `server/routes/eval.py` — Eval API

```python
# GET /api/eval/session
# Returns the session eval log: list of { query, answer, faithfulness_score, reason }

# POST /api/eval/precision
# Runs batch Precision@K eval against ground truth.
# Response: {
#   "mean_precision_at_k": 0.74,
#   "per_query_results": [{ "query", "precision_at_k", "retrieved_sources" }]
# }
```

---

### 5.4 React Frontend (`frontend/`)

**Built with:** Vite + React + Tailwind CSS

**Two-tab layout via tab navigation in `App.jsx`:**

**Chat Tab (`ChatTab.jsx`):**
- Sidebar: loaded documents list, chunk count, "New Conversation" button, eval summary (last 5)
- Main panel: chat message history, input box at bottom
- Each assistant message: collapsible source expander showing source filename, page, similarity score, chunk preview (first 200 chars)
- Faithfulness badge inline after each answer: green (4-5/5), yellow (3/5), red (1-2/5)
- "New Conversation" calls `DELETE /api/chat/memory` and clears local message state

**Eval Dashboard (`EvalDashboard.jsx`):**
- Section 1 — Session eval log table (fetched from `GET /api/eval/session`)
- Section 2 — "Run Precision@K Eval" button → calls `POST /api/eval/precision` → shows mean score + per-query breakdown table + bar chart
- Section 3 — Retrieval health traffic light: green if both > 0.7, yellow if either 0.5-0.7, red if either < 0.5

---

## 6. Ground Truth Setup (`data/ground_truth/eval_pairs.json`)

Create 20 eval pairs covering the 3 loaded documents. Sample structure — Claude Code should generate all 20:

```json
[
  {
    "query": "What was the total UPI transaction volume in FY2024?",
    "relevant_sources": ["npci_upi_report_2024.pdf"],
    "relevant_chunk_keywords": ["billion", "FY2024", "transaction volume", "NPCI"]
  },
  {
    "query": "What is RBI's stance on digital lending regulations?",
    "relevant_sources": ["rbi_annual_report_2024.pdf"],
    "relevant_chunk_keywords": ["digital lending", "NBFC", "regulation", "guidelines"]
  },
  {
    "query": "What were Bajaj Finance's AUM figures in Q3 FY24?",
    "relevant_sources": ["bajaj_finance_q3_2024_transcript.txt"],
    "relevant_chunk_keywords": ["AUM", "assets under management", "Q3", "crore"]
  }
]
```

**Note for Claude Code:** Generate 20 realistic fintech eval pairs in this format. Do not make up specific numbers — use keyword-based matching only.

---

## 7. CLI Scripts

### `scripts/run_ingest.py`
```
Usage: python scripts/run_ingest.py --data-dir data/raw [--reset]
--reset: wipe ChromaDB and re-ingest from scratch
Output: 
  Loading documents from data/raw...
  Loaded 3 documents (127 pages total)
  Chunking... 847 chunks created
  Embedding and storing in ChromaDB... done
  Collection 'finrag': 847 chunks ready
```

### `scripts/run_eval.py`
```
Usage: python scripts/run_eval.py --queries data/ground_truth/eval_pairs.json [--k 5]
Output:
  Running Precision@5 eval on 20 queries...
  Mean Precision@5: 0.74
  Results saved to: eval_results_<timestamp>.json
```

---

## 8. Tests

### `tests/test_ingest.py`
- Test `chunk_documents` returns chunks with correct metadata
- Test `embed_and_store` is idempotent (run twice, chunk count stays same)

### `tests/test_retriever.py`
- Test `retrieve_with_scores` returns exactly K results
- Test each result has required keys: content, source, similarity_score

### `tests/test_chain.py`
- Test `run_query` returns dict with keys: answer, source_documents, question
- Test answer is non-empty string

### `tests/test_eval.py`
- Test `compute_precision_at_k` returns float between 0 and 1
- Test `score_faithfulness` returns dict with score key
- Test faithfulness handles JSON parse error (returns score: -1)

---

## 9. `requirements.txt` (Python backend)

```
openai>=1.0.0
langchain>=0.1.0
langchain-openai>=0.1.0
langchain-community>=0.0.20
langchain-chroma>=0.1.0
langchain-huggingface>=0.1.0
langchain-text-splitters>=0.1.0
langchain-classic>=0.1.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
pypdf>=3.0.0
fastapi>=0.110.0
uvicorn>=0.27.0
python-multipart>=0.0.6
pyyaml>=6.0
python-dotenv>=1.0.0
pytest>=7.0.0
```

---

## 10. Environment Variables

### Backend (`.env` locally, or Render dashboard in prod)
```
EURON_API_KEY=your_key_here
FRONTEND_URL=https://your-app.vercel.app   # production only — for CORS
```

### Frontend (`.env` locally, or Vercel dashboard in prod)
```
VITE_API_URL=https://your-backend.onrender.com/api
```
When unset, the frontend falls back to `/api` (used in local dev via Vite proxy).

---

## 11. `Dockerfile` (backend-only)

The frontend is deployed separately on Vercel, so the Dockerfile only builds the Python backend.

```dockerfile
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/
COPY config.yaml .
COPY data/ground_truth/ data/ground_truth/

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `render.yaml` (Render Blueprint)
```yaml
services:
  - type: web
    name: finrag
    runtime: docker
    plan: free
    envVars:
      - key: EURON_API_KEY
        sync: false
```

### Deployment flow
1. Push repo to GitHub
2. **Render** → New Web Service → connect repo → set `EURON_API_KEY` env var → deploy
3. **Vercel** → Import repo → Root Directory: `frontend` → set `VITE_API_URL` to the Render URL → deploy
4. Back on Render → set `FRONTEND_URL` to the Vercel URL (for CORS)

**Note on Render free tier:** 512MB RAM is insufficient for `sentence-transformers` (loads a ~400MB PyTorch model). Either upgrade to the Standard plan (2GB RAM, $25/mo) or swap to API-based embeddings via Euron.

---

## 12. README Structure (write after ship)

```markdown
# FinRAG — Fintech Research Agent with Persistent Memory

## Problem
[2 paragraphs — fintech analysts manually reading PDFs]

## What makes it different
[The eval layer — most RAG ships without retrieval quality signals]

## Architecture diagram
[ASCII or image]

## Demo GIF
[Screen recording of chat + eval dashboard]

## Eval results
| Metric | Score |
|---|---|
| Mean Precision@5 | 0.XX |
| Mean Faithfulness | X.X/5 |

## How to run locally
[5 steps]

## Tech stack
[Table]
```

---

## 13. Build Order — Phased Implementation

### Phase 1: Project Setup & Configuration
> **Goal:** Scaffold the project (backend + frontend), set up config, and install dependencies.

- [ ] 1.1 Scaffold full directory structure with empty files (server/, frontend/, scripts/, tests/, data/)
- [ ] 1.2 Write `requirements.txt` (Python backend deps)
- [ ] 1.3 Initialize React frontend with Vite + Tailwind CSS (`frontend/`)
- [ ] 1.4 Implement `config.yaml` and `.env.example`
- [ ] 1.5 Implement `server/utils.py` (config loader, logger, token counter)
- [ ] 1.6 Set up `.gitignore` (chroma_db/, .env, __pycache__, node_modules/, dist/, etc.)

**Milestone:** `pip install -r requirements.txt` succeeds, `cd frontend && npm install` succeeds, config loads without error.

---

### Phase 2: Ingestion & Retrieval Pipeline
> **Goal:** Build the core data pipeline — load documents, chunk, embed, store, and retrieve.

- [ ] 2.1 Implement `server/ingest.py` — all 4 functions (load, chunk, embed, orchestrate)
- [ ] 2.2 Implement `server/retriever.py` — both functions (get_retriever, retrieve_with_scores)
- [ ] 2.3 Implement `scripts/run_ingest.py` (CLI for ingestion)
- [ ] 2.4 Add sample documents to `data/raw/`
- [ ] 2.5 Verify: `python scripts/run_ingest.py --data-dir data/raw` processes documents and reports chunk count

**Milestone:** Documents are ingested into ChromaDB, retrieval returns top-K chunks with scores.

---

### Phase 3: Memory & RAG Chain
> **Goal:** Wire up conversation memory and the full RAG chain with Claude.

- [ ] 3.1 Implement `server/memory.py` — all 3 functions (create, get_as_string, clear)
- [ ] 3.2 Implement `server/chain.py` — both functions (build_qa_chain, run_query)
- [ ] 3.3 Verify: chain answers a fintech question from CLI and returns source documents

**Milestone:** End-to-end RAG pipeline works — query → retrieve → generate answer with sources.

---

### Phase 4: Evaluation Layer
> **Goal:** Add self-scoring retrieval eval — Precision@K and faithfulness.

- [ ] 4.1 Generate `data/ground_truth/eval_pairs.json` — 20 query/relevant-chunk pairs
- [ ] 4.2 Implement `server/eval/precision.py` — both functions (compute_precision_at_k, run_batch)
- [ ] 4.3 Implement `server/eval/faithfulness.py` — LLM-as-Judge scorer
- [ ] 4.4 Implement `scripts/run_eval.py` (CLI for batch eval)
- [ ] 4.5 Verify: `python scripts/run_eval.py` outputs mean Precision@5 and per-query scores

**Milestone:** Eval pipeline produces Precision@K and faithfulness scores for all ground truth queries.

---

### Phase 5a: FastAPI Backend API
> **Goal:** Build the REST API that serves the RAG chain and eval endpoints.

- [ ] 5a.1 Implement `server/main.py` (FastAPI app, CORS, startup event, static file serving)
- [ ] 5a.2 Implement `server/routes/chat.py` (POST /api/chat, DELETE /api/chat/memory)
- [ ] 5a.3 Implement `server/routes/eval.py` (GET /api/eval/session, POST /api/eval/precision)
- [ ] 5a.4 Verify: `uvicorn server.main:app` starts and API endpoints respond correctly

**Milestone:** All API endpoints work — chat returns answers with sources + faithfulness, eval returns scores.

---

### Phase 5b: React Frontend
> **Goal:** Build the React UI — Chat + Eval Dashboard tabs.

- [ ] 5b.1 Implement `frontend/src/api.js` (Axios client for backend)
- [ ] 5b.2 Implement `frontend/src/App.jsx` (tab navigation between Chat and Eval)
- [ ] 5b.3 Implement `frontend/src/components/ChatTab.jsx` (chat UI, sidebar, message input)
- [ ] 5b.4 Implement `frontend/src/components/MessageBubble.jsx` and `SourceExpander.jsx`
- [ ] 5b.5 Implement `frontend/src/components/EvalDashboard.jsx` (session log, batch Precision@K, retrieval health)
- [ ] 5b.6 Verify: `npm run dev` launches frontend, chat works end-to-end with backend

**Milestone:** Full UI is functional — chat with sources, inline faithfulness badges, eval dashboard with bar chart.

---

### Phase 6: Testing
> **Goal:** Write and pass all unit tests.

- [ ] 6.1 Implement `tests/test_ingest.py` (chunking metadata, idempotency)
- [ ] 6.2 Implement `tests/test_retriever.py` (K results, required keys)
- [ ] 6.3 Implement `tests/test_chain.py` (response structure, non-empty answer)
- [ ] 6.4 Implement `tests/test_eval.py` (precision range, faithfulness structure, error handling)
- [ ] 6.5 Verify: `pytest` passes all tests

**Milestone:** All 4 test files pass with `pytest`.

---

### Phase 7: Deployment & Polish
> **Goal:** Containerize, deploy, and finalize the project.

- [x] 7.1 Write backend `Dockerfile` (Python-only; frontend deploys to Vercel)
- [x] 7.2 Write `render.yaml` blueprint
- [x] 7.3 Add `VITE_API_URL` env support in `frontend/src/api.js`
- [x] 7.4 Configure CORS with `FRONTEND_URL` env var in `server/main.py`
- [x] 7.5 Push to GitHub (https://github.com/BenRoshan100/fin-rag.git)
- [ ] 7.6 Deploy backend to Render (blocked: free tier OOM — need Standard plan or API embeddings)
- [ ] 7.7 Deploy frontend to Vercel
- [ ] 7.8 Verify live URLs are accessible and functional
- [ ] 7.9 Write `README.md` (problem, architecture, demo GIF, eval results, setup steps)

**Milestone:** Backend live on Render, frontend live on Vercel, README complete, project portfolio-ready.

---

## 14. Acceptance Criteria

- [ ] `run_ingest.py` processes 3 documents and confirms chunk count in terminal
- [ ] Chat tab answers a fintech question and shows source chunks in expander
- [ ] Follow-up question uses prior context (memory working)
- [ ] Each answer shows faithfulness badge (🟢/🟡/🔴)
- [ ] Eval dashboard batch run shows Precision@5 score and bar chart
- [ ] Ingestion is idempotent — running twice does not duplicate chunks
- [ ] All 4 test files pass with `pytest`
- [ ] Backend deploys to Render via Dockerfile (GitHub repo connected)
- [ ] Frontend deploys to Vercel with `VITE_API_URL` pointing to Render backend
- [ ] Live URLs accessible and functional

---

*PRD v1.1 — FinRAG. Updated to reflect actual implementation and split deployment (Render + Vercel).*