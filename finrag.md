# FinRAG — Fintech Research Agent with Persistent Memory
## Product Requirements Document (PRD) for Claude Code

**Version:** 1.0  
**Author:** Ben Roshan D  
**Date:** April 2026  
**Status:** Ready for scaffolding

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
| LLM | Euron API (`gpt-5.3-instant`) via `openai` SDK (base_url: `https://api.euron.one/api/v1/euri`) |
| Memory | LangChain `ConversationBufferMemory` |
| Orchestration | LangChain `RetrievalQA` + custom chain |
| Document loading | `pypdf`, `langchain.document_loaders` |
| Chunking | `RecursiveCharacterTextSplitter` |
| Eval | Custom Python module — no external eval library |
| UI | Streamlit (multi-tab: Chat + Eval Dashboard) |
| Deployment | Render (Dockerfile included, GitHub repo: https://github.com/BenRoshan100/fin-rag.git) |
| Config | `.env` for API keys, `config.yaml` for chunking/retrieval params |

---

## 3. Directory Structure

```
finrag/
├── README.md
├── requirements.txt
├── .env.example
├── config.yaml
├── Dockerfile
├── .gitignore
│
├── data/
│   ├── raw/                        # Drop PDFs here
│   │   ├── rbi_annual_report_2024.pdf
│   │   ├── npci_upi_report_2024.pdf
│   │   └── bajaj_finance_q3_2024_transcript.txt
│   └── ground_truth/
│       └── eval_pairs.json         # 20 query/relevant-chunk pairs for Precision@K
│
├── src/
│   ├── __init__.py
│   ├── ingest.py                   # Document loading, chunking, embedding, ChromaDB storage
│   ├── retriever.py                # Query ChromaDB, return top-K chunks with metadata
│   ├── memory.py                   # ConversationBufferMemory setup and management
│   ├── chain.py                    # LangChain QA chain combining retriever + memory + Claude
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── precision.py            # Precision@K computation against ground truth
│   │   └── faithfulness.py         # LLM-as-Judge faithfulness scorer
│   └── utils.py                    # Logging, config loader, token counter
│
├── app/
│   ├── streamlit_app.py            # Main Streamlit entrypoint
│   ├── pages/
│   │   ├── chat.py                 # Chat tab UI
│   │   └── eval_dashboard.py       # Eval metrics tab UI
│   └── components/
│       ├── message_bubble.py       # Chat message component
│       └── source_expander.py      # Source chunk expander component
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
└── chroma_db/                      # Auto-created by ChromaDB, gitignored
```

---

## 4. Module Specifications

### 4.1 `src/ingest.py`

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

### 4.2 `src/retriever.py`

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

### 4.3 `src/memory.py`

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

### 4.4 `src/chain.py`

**Purpose:** Assemble the full RAG + memory chain. Core of the application.

```python
def build_qa_chain(retriever, memory) -> ConversationalRetrievalChain:
    """
    Build LangChain ConversationalRetrievalChain:
    - LLM: Euron API (gpt-5.3-instant) via ChatOpenAI with base_url="https://api.euron.one/api/v1/euri"
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

### 4.5 `src/eval/precision.py`

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

### 4.6 `src/eval/faithfulness.py`

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
    Call Euron API (gpt-5.3-instant) with FAITHFULNESS_PROMPT.
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

### 4.7 `src/utils.py`

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

## 5. Streamlit Application

### 5.1 `app/streamlit_app.py`

**Entry point.** Sets up page config, loads chain + memory, renders tab navigation.

```python
# Page config
st.set_page_config(page_title="FinRAG", layout="wide", page_icon="📊")

# Tabs
tab1, tab2 = st.tabs(["💬 Chat", "📊 Eval Dashboard"])

with tab1:
    render_chat_tab()

with tab2:
    render_eval_dashboard()
```

**Session state to initialise:**
```python
if "chain" not in st.session_state:
    st.session_state.chain = build_qa_chain(retriever, memory)
if "memory" not in st.session_state:
    st.session_state.memory = create_memory()
if "messages" not in st.session_state:
    st.session_state.messages = []
if "eval_log" not in st.session_state:
    st.session_state.eval_log = []  # List of {query, answer, precision, faithfulness}
```

---

### 5.2 Chat Tab (`app/pages/chat.py`)

**Layout:**
```
[Sidebar]                    [Main panel]
- Loaded documents list      - Chat message history
- Chunk count                - Input box (bottom)
- "New Conversation" btn     - Source expander below each answer
- Eval summary (last 5)
```

**Behaviour:**
- User types question → `run_query(chain, question)` → display answer
- Below each answer: collapsible `st.expander("📄 Sources (K chunks)")` showing source filename, page, similarity score, chunk preview (first 200 chars)
- After each answer: run `score_faithfulness()` → display `🟢 Faithful (4/5)` or `🟡 Moderate (3/5)` or `🔴 Low (1-2/5)` badge inline
- "New Conversation" button clears memory and resets `st.session_state.messages`

---

### 5.3 Eval Dashboard Tab (`app/pages/eval_dashboard.py`)

**Three sections:**

**Section 1 — Session Eval Log**
Table of all queries in current session:
| Query | Faithfulness Score | Reason |
|---|---|---|
| What was UPI volume in FY24? | 4/5 | Accurate summary of NPCI data |

**Section 2 — Batch Precision@K Runner**
- Button: "Run Precision@K Eval"
- On click: runs `run_batch_precision_eval()` against `eval_pairs.json`
- Shows: mean Precision@K score + per-query breakdown table
- Bar chart: precision score per query (use `st.bar_chart`)

**Section 3 — Retrieval Health**
- Mean faithfulness score (current session)
- Mean Precision@K (last batch run)
- Simple traffic light: 🟢 if both > 0.7, 🟡 if either 0.5–0.7, 🔴 if either < 0.5

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

## 9. `requirements.txt`

```
openai>=1.0.0
langchain>=0.1.0
langchain-openai>=0.1.0
langchain-community>=0.0.20
langchain-chroma>=0.1.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
pypdf>=3.0.0
streamlit>=1.32.0
pyyaml>=6.0
python-dotenv>=1.0.0
pytest>=7.0.0
```

---

## 10. `.env.example`

```
EURON_API_KEY=your_key_here
```

---

## 11. `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-run ingestion at build time (optional — comment out if data not bundled)
# RUN python scripts/run_ingest.py --data-dir data/raw

EXPOSE 8501

CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

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
> **Goal:** Scaffold the project, set up config, and install dependencies.

- [ ] 1.1 Scaffold full directory structure with empty files
- [ ] 1.2 Write `requirements.txt`
- [ ] 1.3 Implement `config.yaml` and `.env.example`
- [ ] 1.4 Implement `src/utils.py` (config loader, logger, token counter)
- [ ] 1.5 Set up `.gitignore` (chroma_db/, .env, __pycache__, etc.)

**Milestone:** `pip install -r requirements.txt` succeeds, config loads without error.

---

### Phase 2: Ingestion & Retrieval Pipeline
> **Goal:** Build the core data pipeline — load documents, chunk, embed, store, and retrieve.

- [ ] 2.1 Implement `src/ingest.py` — all 4 functions (load, chunk, embed, orchestrate)
- [ ] 2.2 Implement `src/retriever.py` — both functions (get_retriever, retrieve_with_scores)
- [ ] 2.3 Implement `scripts/run_ingest.py` (CLI for ingestion)
- [ ] 2.4 Add sample documents to `data/raw/`
- [ ] 2.5 Verify: `python scripts/run_ingest.py --data-dir data/raw` processes documents and reports chunk count

**Milestone:** Documents are ingested into ChromaDB, retrieval returns top-K chunks with scores.

---

### Phase 3: Memory & RAG Chain
> **Goal:** Wire up conversation memory and the full RAG chain with Claude.

- [ ] 3.1 Implement `src/memory.py` — all 3 functions (create, get_as_string, clear)
- [ ] 3.2 Implement `src/chain.py` — both functions (build_qa_chain, run_query)
- [ ] 3.3 Verify: chain answers a fintech question from CLI and returns source documents

**Milestone:** End-to-end RAG pipeline works — query → retrieve → generate answer with sources.

---

### Phase 4: Evaluation Layer
> **Goal:** Add self-scoring retrieval eval — Precision@K and faithfulness.

- [ ] 4.1 Generate `data/ground_truth/eval_pairs.json` — 20 query/relevant-chunk pairs
- [ ] 4.2 Implement `src/eval/precision.py` — both functions (compute_precision_at_k, run_batch)
- [ ] 4.3 Implement `src/eval/faithfulness.py` — LLM-as-Judge scorer
- [ ] 4.4 Implement `scripts/run_eval.py` (CLI for batch eval)
- [ ] 4.5 Verify: `python scripts/run_eval.py` outputs mean Precision@5 and per-query scores

**Milestone:** Eval pipeline produces Precision@K and faithfulness scores for all ground truth queries.

---

### Phase 5: Streamlit UI
> **Goal:** Build the multi-tab Streamlit app — Chat + Eval Dashboard.

- [ ] 5.1 Implement `app/streamlit_app.py` (entry point, page config, session state, tabs)
- [ ] 5.2 Implement `app/components/message_bubble.py` and `app/components/source_expander.py`
- [ ] 5.3 Implement `app/pages/chat.py` (chat UI, source expanders, faithfulness badges)
- [ ] 5.4 Implement `app/pages/eval_dashboard.py` (session log, batch Precision@K, retrieval health)
- [ ] 5.5 Verify: `streamlit run app/streamlit_app.py` launches both tabs and chat works end-to-end

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

- [ ] 7.1 Write `Dockerfile`
- [ ] 7.2 Test Docker build and run locally
- [ ] 7.3 Deploy to Render (connect GitHub repo: https://github.com/BenRoshan100/fin-rag.git)
- [ ] 7.4 Verify live URL is accessible and functional
- [ ] 7.5 Write `README.md` (problem, architecture, demo GIF, eval results, setup steps)

**Milestone:** App is live on Railway, README is complete, project is portfolio-ready.

---

## 14. Acceptance Criteria

- [ ] `run_ingest.py` processes 3 documents and confirms chunk count in terminal
- [ ] Chat tab answers a fintech question and shows source chunks in expander
- [ ] Follow-up question uses prior context (memory working)
- [ ] Each answer shows faithfulness badge (🟢/🟡/🔴)
- [ ] Eval dashboard batch run shows Precision@5 score and bar chart
- [ ] Ingestion is idempotent — running twice does not duplicate chunks
- [ ] All 4 test files pass with `pytest`
- [ ] App deploys to Render via Dockerfile (GitHub repo connected)
- [ ] Live URL accessible and functional

---

*PRD v1.0 — FinRAG. Feed this entire file to Claude Code as the project specification.*