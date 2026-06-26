# Prism — Learning Concepts

## Concept Index by Product Workflow

Every concept in this file maps to a specific stage in Prism's request lifecycle. Use this to understand *when* each idea becomes relevant, not just *what* it is.

```
┌─────────────────────────────────────────────────────────────────┐
│  USER UPLOADS A DOCUMENT                                        │
│                                                                 │
│  PDF/TXT/CSV → chunk → embed → store → briefing                │
│                                                                 │
│  Concept 11  RecursiveCharacterTextSplitter                     │
│              How text is split into chunks (paragraph → line    │
│              → word → char priority). Overlap bridges splits.   │
│                                                                 │
│  Concept 1   Parent-Child Chunking                              │
│              Design pattern: small child chunks for retrieval,  │
│              large parent chunks sent to LLM.                   │
│                                                                 │
│  Concept 2   InMemoryStore                                      │
│              Where parent chunks live (RAM only, dies on        │
│              restart). ChromaDB stores child vectors on disk.   │
│                                                                 │
│  Concept 10  Idempotent Ingestion (MD5)                         │
│              Re-uploading same file won't create duplicate       │
│              chunks. MD5(source+page+text) = chunk ID.          │
│                                                                 │
│  Concept 14  LLM at Ingest Time (Briefing)                      │
│              After ingest, LLM auto-generates 5-bullet summary  │
│              + 3 suggested questions. Runs once, not per query. │
│                                                                 │
│  Concept 16  Multi-Workspace Isolation                          │
│              Each workspace = one ChromaDB collection. Upload   │
│              goes into selected workspace only.                 │
│                                                                 │
│  Concept 18  FastAPI BackgroundTasks                            │
│              Two-phase upload: sync embed first (<3s queryable) │
│              → background contextual replacement (~30–60s).     │
│                                                                 │
│  Concept 19  asyncio.Semaphore for rate limiting                │
│              Cap parallel Groq calls at 3 → 3000 TPM burst vs  │
│              6000 TPM limit. Smart 429 retry parses wait time.  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  USER SENDS A QUESTION                                          │
│                                                                 │
│  question → (optionally) multi-query expand → (optionally)     │
│  HyDE expand → retrieve → fuse → rerank → top-5 chunks         │
│                                                                 │
│  Concept 17  Multi-Query Retrieval                              │
│              LLM generates 3 phrasings of query → retrieve for │
│              each → pool + deduplicate → RRF → rerank.          │
│              Fixes low recall caused by single-phrasing misses. │
│              (toggle: multi_query_enabled in config.yaml)       │
│                                                                 │
│  Concept 7   HyDE                                               │
│              LLM generates fake answer → embed fake answer      │
│              instead of query → closes question/answer vector   │
│              space gap → higher context recall.                 │
│              (toggle: hyde_enabled in config.yaml)              │
│                                                                 │
│  Concept 4   BM25Okapi                                          │
│              Sparse keyword retrieval. Catches exact terms       │
│              (section numbers, ₹ amounts) that dense misses.    │
│              TF saturation prevents high-frequency term bias.   │
│                                                                 │
│  Concept 3   RRF + Cross-Encoder Pipeline                       │
│              Dense (0.7) + BM25 (0.3) merged via weighted RRF. │
│              Cross-encoder reranks top-10 jointly → top-5.      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  WEB SEARCH (always on)                                         │
│                                                                 │
│  question → condense with history → Tavily → web results        │
│                                                                 │
│  Concept 5   ConversationalRetrievalChain Condensation Trap     │
│              Chain's internal condense step strips prepended    │
│              web context. Fix: bypass chain entirely for web    │
│              queries. Direct LLM call preserves all context.    │
│                                                                 │
│  Concept 12  ConversationBufferWindowMemory                     │
│              Sliding k=10 window of chat history injected into  │
│              condense_question() before Tavily search, so       │
│              follow-up queries have full context.               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LLM GENERATES ANSWER                                           │
│                                                                 │
│  [doc chunks] + [web results] + [chat history] → LLM → answer  │
│                                                                 │
│  Concept 12  ConversationBufferWindowMemory (output_key trap)   │
│              Memory saves this turn for next question.          │
│              output_key="answer" required — chain returns       │
│              multiple keys, memory needs to know which to save. │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SERVER INFRASTRUCTURE (runs across all stages above)           │
│                                                                 │
│  Concept 6   Singleton ML Model Pattern                         │
│              BM25, CrossEncoder, vectorstore, retriever all     │
│              cached at module level. One load per process.      │
│              Without this: OOM after 2–3 queries on Render.     │
│                                                                 │
│  Concept 13  Python GC + ML Object Retention                    │
│              LangChain circular refs prevent auto-release.      │
│              gc.collect() called after every chat request.      │
│                                                                 │
│  Concept 16  Multi-Workspace Isolation                          │
│              Every request carries workspace_id. Retriever,     │
│              BM25 index, vectorstore all keyed per workspace.   │
│              React key={workspaceId} remounts chat on switch.   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  EVALUATION (offline, run via scripts/run_eval_versioned.py)    │
│                                                                 │
│  50 eval pairs → retrieve → answer → score → versioned JSON    │
│                                                                 │
│  Concept 8   Eval Metric Design (Faithfulness Is Circular)      │
│              Why faithfulness 1.0 was meaningless. How          │
│              answer_correctness (vs ground truth) is honest.    │
│                                                                 │
│  Concept 9   Precision@K vs Recall Diagnostic                   │
│              P@5=0.89 + recall=0.51 = pool too narrow.          │
│              The combination tells you exactly what to fix.     │
│                                                                 │
│  Concept 15  All 7 Eval Metrics — Full Reference                │
│              Answer Correctness, Answer Relevancy, Context      │
│              Recall, Precision@5, Latency p50/p95/p99.          │
│              Includes computation steps, failure modes,         │
│              Prism v1.0.0 results, and metric interaction map.  │
│                                                                 │
│  Concept 20  Semantic Chunking Tradeoff                         │
│              Topic-boundary splits improve recall but hurt      │
│              precision when eval pairs are aligned to fixed     │
│              chunk boundaries. Measured: +9.3pp recall,         │
│              -27.3pp P@5, 5× latency (v1.4.0 ablation).        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Parent-Child Chunking — The Retrieval-Faithfulness Tradeoff

### The Problem with One Chunk Size

| Chunk Size | Retrieval | LLM Answer Quality |
| --- | --- | --- |
| Small (200 chars) | Precise — matches exact phrase | Bad — too little context, answer is fragmented |
| Large (800 chars) | Imprecise — embedding averages over too much text | Good — LLM sees full context |

**Key insight:** Embeddings of large chunks get "diluted" — the vector represents the average meaning of 800 chars. Small chunks have sharper, more focused vectors that match queries better.

### How ParentDocumentRetriever Works

**INGEST:**

- 800-char parent → stored in `InMemoryStore` (keyed by ID)
- 200-char children → embedded → stored in ChromaDB

**QUERY:**

1. Query hits ChromaDB → finds best matching 200-char child chunk
2. Look up `parent_id` from child metadata
3. Return the full 800-char parent to LLM

### Why This Works

- **Child chunk** = precise retrieval target (dense vector = focused meaning)
- **Parent chunk** = rich answer context (LLM gets surrounding sentences)

### Concrete Example — RBI Circular PDF

**Raw text (one paragraph):**

> "The Reserve Bank of India has mandated that all UPI transactions above ₹2,000 must undergo additional authentication from January 2025. This includes biometric verification or OTP-based second factor. Non-compliant PSPs will face penalties up to ₹10 lakh per violation."
> 

**After chunking:**

- **Parent (800 chars) → InMemoryStore:** Full paragraph above
- **Child A (200 chars) → ChromaDB:** "The Reserve Bank of India has mandated that all UPI transactions above ₹2,000 must undergo additional authentication from January 2025."
- **Child B:** "This includes biometric verification or OTP-based second factor."
- **Child C:** "Non-compliant PSPs will face penalties up to ₹10 lakh per violation."

**Query:** `"What is the UPI transaction authentication limit?"`

→ ChromaDB finds **Child A** (score: 0.91) — focused vector on UPI + ₹2000 + authentication

→ Fetches parent_id → returns **full parent paragraph** to LLM

**Comparison Table:**

| Approach | LLM Gets | Problem |
| --- | --- | --- |
| Dense-only, large chunks | Full paragraph (good) | Match was imprecise — wrong paragraph might score higher |
| Dense-only, small chunks | Child A only (38 words) | Misses penalty info — incomplete answer |
| ParentDocumentRetriever | Full paragraph (precise match + rich context) | ✅ Best of both |

**LLM final answer:** "UPI transactions above ₹2,000 require additional authentication (biometric or OTP) from Jan 2025. Non-compliant PSPs face up to ₹10 lakh penalty."

---

## 2. InMemoryStore — What It Actually Is

**Key point: InMemoryStore is NOT part of ChromaDB. It's a separate, RAM-only store.**

Under the hood it's essentially a plain Python dict wrapped in a LangChain class:

```python
store = {}
store["parent_id_abc123"] = "Full 800-char parent chunk text..."
store["parent_id_def456"] = "Another parent chunk..."
```

### Two Separate Stores in Prism

| ChromaDB (on disk) | InMemoryStore (RAM only) |
| --- | --- |
| Child chunk vectors | Parent chunk text |
| [vector, metadata] → find similar | parent_id → full text |
| ✅ Survives restart | ❌ Dies on restart |

### Flow

```
Child A metadata = { "parent_id": "abc123", "text": "short child..." }
                            ↓
             InMemoryStore["abc123"]
                            ↓
             "Full 800-char parent text" → LLM
```

### ⚠️ Known Limitation in Prism

Render free tier cold-starts → InMemoryStore is wiped → must **re-ingest PDFs on every cold start**.

ChromaDB persists to disk so child vectors survive, but parent text is gone.

### ⚠️ Architecture Note — Intended vs Current Implementation

`architecture.md` and Concept 1 describe ParentDocumentRetriever (child 200 / parent 800). The current `ingest.py` uses a single-pass `RecursiveCharacterTextSplitter` at 500 chars — no separate parent store. The ParentDocumentRetriever was the original design and is documented as such. Both chunking approaches teach the same tradeoff; the parent-child concept remains valid as a pattern even if the current code simplified to single-pass chunking.

---

## 3. RRF + Cross-Encoder Reranker Pipeline

### 3a. RRF — Reciprocal Rank Fusion

**Problem:** Dense retrieval returns a ranked list. BM25 returns a ranked list. Scores are on different scales (BM25: 0–15, cosine: 0–1) — can't add them directly.

**RRF Solution:** Ignore raw scores. Use only rank position.

```
Standard RRF formula:
score(doc) = Σ  1 / (k + rank_in_list)
             k = 60  (constant, dampens top-rank advantage)

Prism's weighted RRF (applied inside the formula per list):
score(doc) += dense_weight  / (k + rank_in_dense_list)   # 0.7 × contribution
score(doc) += sparse_weight / (k + rank_in_sparse_list)  # 0.3 × contribution
```

**Example:**

| Doc | Dense (ChromaDB) | BM25 | RRF Score |
| --- | --- | --- | --- |
| Doc A | Rank 1 (0.91) | Rank 2 (9.1) | 1/61 + 1/62 = **0.0325** ✅ |
| Doc C | Rank 3 (0.71) | Rank 1 (12.3) | 1/63 + 1/61 = **0.0320** |
| Doc B | Rank 2 (0.87) | — | 1/62 = 0.0161 |
| Doc D | — | Rank 3 (7.4) | 1/63 = 0.0159 |

**Doc A wins** — appeared high in BOTH lists → signals true relevance.

> In Prism: `dense_weight=0.7`, `sparse_weight=0.3` applied **inside** the RRF formula — each list's contribution is multiplied by its weight before summing. Not "before RRF" as a pre-filter, but as a per-list scaling factor within fusion (see Concept 4 for the actual code).
> 

### 3b. Cross-Encoder Reranker

**Problem:** RRF gives top-10 candidates. Bi-encoder (ChromaDB) encodes query and doc *separately* → approximate similarity.

**Cross-Encoder:** Feeds query + doc *together* into BERT → full attention across both → much more accurate relevance score.

|  | Bi-Encoder (ChromaDB) | Cross-Encoder (TinyBERT) |
| --- | --- | --- |
| Method | embed(query) + embed(doc) → cosine(q,d) | BERT([query][SEP][doc]) → single score 0–1 |
| Speed | Fast | Slow |
| Accuracy | Approximate | Accurate |
| Encoding | Independent | Joint |

**Example — after RRF top-10:**

| Pair | Cross-Encoder Score |
| --- | --- |
| (query, Doc A) | 0.94 ✅ |
| (query, Doc B) | 0.88 ✅ |
| (query, Doc C) | 0.61 |
| (query, Doc D) | 0.23 |

Top-5 by cross-encoder score → LLM

### Full Retrieval Pipeline

```
Query
  |
  ├→ ChromaDB dense  → top-10 ranked docs
  ├→ BM25 sparse     → top-10 ranked docs
  |
  ↓
RRF fusion → merged top-10 (rank-based, scale-agnostic)
  |
  ↓
Cross-encoder → re-scores all 10 jointly with query
  |
  ↓
Top-5 parent chunks → LLM
```

---

---

## 4. BM25Okapi — Why Keywords Beat Embeddings for Exact Terms

### The Problem with Dense Retrieval on Regulatory Text

Embeddings capture *meaning*. But regulatory text has exact identifiers — section numbers, policy codes, rupee amounts — where the exact token matters, not the meaning.

**Example:**

Query: `"What is the penalty for UPI non-compliance?"`

A dense embedding model reads this as: *"something about UPI and consequences"*.

Two chunks in corpus:
- Chunk A: `"Non-compliant PSPs will face penalties up to ₹10 lakh per violation."` ← exact answer
- Chunk B: `"UPI has transformed digital payments in India with over 100 billion transactions."` ← semantically close (UPI topic) but wrong

Dense retrieval might rank Chunk B high because it's heavily UPI-themed. BM25 ranks Chunk A high because "penalt" and "non-compli" are rare, high-signal tokens.

### How BM25Okapi Works

Plain TF-IDF problem: a doc that says "UPI" 50 times gets 50× the score. That's unfair — one mention of "₹10 lakh" in the right context should beat 50 mentions of "UPI" in a generic overview.

BM25 fixes this with **term frequency saturation**:

```
BM25 score = IDF(term) × [ tf × (k1 + 1) ] / [ tf + k1 × (1 - b + b × dl/avgdl) ]

Where:
  tf    = how many times term appears in this chunk
  IDF   = how rare the term is across all chunks (log scale)
  k1    = saturation constant (~1.5) — controls how fast TF saturates
  b     = length normalization (~0.75)
  dl    = this chunk's length
  avgdl = average chunk length in corpus
```

**Saturation in plain English:**

| tf (term count in chunk) | TF-IDF score | BM25 score (k1=1.5) |
| --- | --- | --- |
| 1 | 1.0 | 1.0 |
| 5 | 5.0 | 1.56 ← plateaus |
| 20 | 20.0 | 1.79 ← barely grows |
| 50 | 50.0 | 1.88 ← effectively capped |

A chunk mentioning "UPI" 50 times scores almost the same as one mentioning it 5 times. But "₹10 lakh" appearing once in a chunk that has it = high IDF (rare token) × full TF benefit.

### In Prism

```python
# bm25_index.py
from rank_bm25 import BM25Okapi

# .lower() matters — "UPI" and "upi" are different tokens without it
corpus = [doc["content"].lower().split() for doc in all_chunks]
bm25 = BM25Okapi(corpus)

# At query time — query also lowercased to match corpus tokenization:
scores = bm25.get_scores(query.lower().split())
top_k_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
```

BM25 operates on raw tokens (word split). No embeddings. No GPU. Rebuilds in ~1s at startup from corpus.

**Weight in Prism:** `sparse_weight=0.3` in RRF — BM25 is complementary, not dominant. Dense handles semantic meaning; BM25 catches exact matches dense misses.

---

## 5. ConversationalRetrievalChain — The Silent Context Killer

### What the Chain Does Internally

`ConversationalRetrievalChain` has two internal steps most people don't know about:

```
User question + chat history
        ↓
[STEP 1] Condense question
        LLM rewrites "Is the price level good?" 
        → "Is Bajaj Finance stock ₹908-924 a good buy in 2026?"
        (standalone question for retrieval)
        ↓
[STEP 2] Retrieve + Answer
        Standalone question → retriever → top-5 chunks → LLM answer
```

Step 1 exists so follow-up questions work without full history context. Good design for RAG.

### The Bug: Web Context Gets Stripped

When Prism added Tavily web search, the naive approach was:

```python
web_results = tavily.search(question)
augmented_question = f"Web context: {web_results}\n\nQuestion: {question}"
chain.invoke({"question": augmented_question})  # ← WRONG
```

What actually happens:

```
augmented_question (with Tavily content prepended)
        ↓
[STEP 1] Chain's condense LLM:
        "Rewrite this as a standalone retrieval query."
        Output: "What is Bajaj Finance stock price?"
        ← ALL TAVILY CONTENT STRIPPED. LLM never sees it.
        ↓
[STEP 2] Answer LLM gets: corpus chunks only. No web context.
```

The chain's condensation step rewrites the question for retrieval quality — and throws away everything else.

### The Fix in Prism

Bypass the chain entirely for web queries. Direct LLM call:

```python
# chain.py
def run_query_with_web(question, rag_docs, web_sources, memory):
    history = memory.load_memory_variables({})["history"]
    
    prompt = f"""
    Chat history: {history}
    
    Web search results:
    {web_sources}
    
    Document context:
    {rag_docs}
    
    Question: {question}
    Answer:"""
    
    answer = llm.invoke(prompt)
    memory.save_context({"input": question}, {"answer": answer})
    return answer
```

No condensation step. Web context reaches the LLM guaranteed.

**Lesson:** LangChain abstractions are powerful but opaque. When something doesn't work, read what the chain actually does internally — don't assume the abstraction is transparent.

---

## 6. Singleton ML Model Pattern — OOM Prevention in Production

### The Problem

Every time a user sent a chat message in Prism, this happened:

```python
# routes/chat.py (WRONG — old version)
def chat(request):
    collection = chroma_client.get_or_create_collection(workspace_id)  # new Chroma object
    vectorstore = Chroma(collection=collection, ...)                    # new VectorStore
    retriever = HybridRetriever(vectorstore=vectorstore, ...)           # new Retriever
    return retriever.invoke(question)
```

Three new objects per request. Each Chroma instance reloads embeddings from disk into RAM. After 2–3 queries → 512MB Render limit hit → OOM crash.

### The Fix: Module-Level Cache

```python
# retriever.py — two separate caches, not one tuple dict
_vs_cache: dict[str, Chroma] = {}           # workspace_id → Chroma vectorstore
_retriever_cache: dict[str, HybridRetriever] = {}  # workspace_id → retriever

def get_vectorstore(collection_name: str) -> Chroma:
    if collection_name not in _vs_cache:
        _vs_cache[collection_name] = Chroma(
            collection_name=collection_name,
            embedding_function=_get_embeddings(),
            persist_directory="./chroma_db",
        )
    return _vs_cache[collection_name]

def get_retriever(workspace_id: str) -> HybridRetriever:
    if workspace_id not in _retriever_cache:
        vectorstore = get_vectorstore(workspace_id)
        _retriever_cache[workspace_id] = HybridRetriever(
            vectorstore=vectorstore, ...
        )
    return _retriever_cache[workspace_id]

def invalidate_cache(workspace_id: str) -> None:
    _vs_cache.pop(workspace_id, None)       # drop vectorstore
    _retriever_cache.pop(workspace_id, None)  # drop retriever
    # called from upload.py after ingest so next request rebuilds cleanly
```

**Memory behaviour:**

| Approach | RAM on 3rd request |
| --- | --- |
| New retriever per request | 3× embedding reload = OOM |
| Module-level cache | 1× load, reused = stable |

### Why Module-Level (Not `app.state`)

`app.state` (FastAPI) is also fine for singletons, but module-level has one advantage: importable from anywhere without passing the app object. The BM25 index needs to be rebuilt from `upload.py` — importing `from retriever import invalidate_cache` is cleaner than threading `app` through function signatures.

**Same pattern used for:**
- `bm25_index.py` — BM25Okapi singleton
- `reranker.py` — CrossEncoder singleton  
- `retriever.py` — per-workspace (vectorstore, retriever) cache

**General rule:** Any ML model or index that takes >100ms to load → make it a singleton. Pay the cost once at startup, not on every request.

---

## 7. HyDE — Hypothetical Document Embeddings

### The Problem with Embedding a Question

When you search ChromaDB, you embed the *query* and find similar vectors. But your corpus contains *answers*, not questions. They live in different regions of vector space.

**Concrete example:**

Query: `"What is the UPI transaction limit for P2P transfers?"`

This embeds as a *question vector* — the model has seen millions of questions, it knows this pattern.

The answer in your corpus: `"P2P UPI transfers are capped at ₹1 lakh per transaction per day as per NPCI guidelines."`

This embeds as an *answer vector* — declarative sentence, factual tone, different region in 1536-dimensional space.

They're semantically related, but the vector distance is larger than it should be.

### HyDE's Solution

Before searching, ask the LLM to hallucinate an answer:

```
Step 1: LLM generates a fake answer to the query
  Query: "What is the UPI transaction limit for P2P transfers?"
  Fake answer: "The UPI transaction limit for P2P transfers is typically 
                set by NPCI and varies by bank, generally around ₹1 lakh 
                per day for most PSPs."

Step 2: Embed the FAKE ANSWER (not the query)
  vector = embed("The UPI transaction limit for P2P transfers is...")

Step 3: Search ChromaDB with this vector
  → Finds real answer chunks that are semantically close to a fake answer
  → Much closer in vector space than the original question was
```

### Why "Hypothetical" Works

The fake answer and the real corpus chunk are both declarative, factual, answer-shaped text. They live in the same region of vector space. The query (a question) lives elsewhere.

```
Vector space (simplified):

[Question zone]          [Answer zone]
"What is UPI limit?" --- ... --- "P2P capped at ₹1 lakh..."
       ↑                                    ↑
  far from corpus                    close to corpus chunk
  
HyDE:
"UPI limit is ~₹1 lakh..." ← fake answer → close to real chunk ✅
```

### In Prism

```python
# retriever.py
def _hyde_expand(self, query: str) -> str:
    prompt = f"Write a 2-sentence factual answer to: {query}"
    return self.llm.invoke(prompt).content

def _get_relevant_documents(self, query: str):
    dense_query = self._hyde_expand(query) if self.use_hyde else query
    
    # Dense search uses fake answer embedding
    dense_docs = self.vectorstore.similarity_search(dense_query, k=10)
    
    # BM25 still uses original query (keyword matching needs real terms)
    sparse_docs = self.bm25_retrieve(query, k=10)
    
    return self.rrf_and_rerank(dense_docs, sparse_docs)
```

**Off by default** (`config.yaml` `hyde_enabled: false`) — adds one Groq call per query (~200ms). Enable → run eval → measure context_recall delta → decide.

**Expected lift:** Higher context_recall (currently 0.51 in Prism v1.0.0). HyDE specifically helps recall — it finds chunks that keyword/direct-embed matching misses.

---

## 8. Eval Metric Design — Why Faithfulness Is Circular

### Four RAGAS Metrics and What They Actually Measure

| Metric | Judge compares | Question it answers |
| --- | --- | --- |
| **faithfulness** | LLM answer vs retrieved chunks | "Did the LLM stick to what was in the retrieved docs?" |
| **answer_correctness** | LLM answer vs ground_truth reference | "Is the answer actually right?" |
| **answer_relevancy** | LLM answer vs original question | "Did the answer address what was asked?" |
| **context_recall** | Retrieved chunks vs ground_truth | "Did retrieval find the chunks needed to answer?" |

### The Faithfulness Trap

In Prism v1 eval, faithfulness scored 1.0. Seemed great. Was meaningless.

Here's why:

```
Eval pair designed alongside corpus:
  Question: "What is the UPI P2P transaction limit?"
  Ground truth: "₹1 lakh per day"
  
  Corpus chunk (also written by us): 
  "P2P UPI transfers are capped at ₹1 lakh per day per NPCI guidelines."

Flow:
  1. LLM retrieves that chunk (of course — it's perfectly matched)
  2. LLM answers: "The UPI P2P limit is ₹1 lakh per day."
  3. RAGAS faithfulness judge: "Does answer match retrieved chunk?" → YES → score: 1.0
```

The judge is comparing the answer to the chunk that was *designed to produce that answer*. Circular. Score tells you the retrieval worked, not whether the answer is correct.

### answer_correctness Is the Honest Metric

```
Flow:
  1. LLM answers: "The UPI P2P limit is ₹1 lakh per day."
  2. Ground truth (human-written reference): "₹1 lakh per transaction per day"
  3. RAGAS judge: "Does answer match ground truth?" → mostly yes → score: 0.82
```

Judge compares to an *independent human reference*. No circular dependency on retrieved chunks. Harder to game.

**Prism v1.0.0 Violet results:**

| Metric | Score | Interpretation |
| --- | --- | --- |
| answer_correctness | 0.82 | 82% of answers match ground truth — honest signal |
| answer_relevancy | 0.62 | RAGAS penalizes verbosity — Groq 70B tends to over-explain |
| context_recall | 0.51 | Only 51% of needed chunks retrieved — target for Multi-Query |
| P@5 | 0.89 | When chunks are retrieved, 89% are correct — precision is fine |

### The P@5 + Recall Diagnostic

P@5=0.89 + recall=0.51 tells you something specific:

```
Retrieval pool is too narrow.

"When we retrieve something, it's usually right (0.89)."
"But we're missing ~half the relevant chunks (0.51)."

Root cause: single-phrasing query misses chunks phrased differently.
Fix: Multi-Query Retrieval — generate 3 phrasings, retrieve for each, pool candidates.
```

This is exactly how production ML teams diagnose retrieval systems. The combination of metrics points to the specific fix.

---

## 9. Precision@K vs Recall — The Retrieval Diagnostic Pair

### Definitions in Plain English

Imagine your corpus has **5 chunks** that are genuinely relevant to a query. Your retriever returns **5 chunks** (K=5).

```
Ground truth relevant chunks: [A, B, C, D, E]
Retrieved chunks:              [A, B, X, Y, Z]

Precision@5 = correct retrieved / K = 2/5 = 0.40
              "Of what I returned, how much was right?"

Recall@5    = correct retrieved / total relevant = 2/5 = 0.40
              "Of all the right chunks, how many did I find?"
```

### The Four Diagnostic Combinations

| P@5 | Recall | Diagnosis | Fix |
| --- | --- | --- | --- |
| High | High | ✅ Retrieval working well | Ship it |
| High | Low | Pool too narrow — finding right chunks but missing others | Multi-Query Retrieval, HyDE |
| Low | High | Too much noise — finding relevant chunks but also junk | Better reranking, stricter K |
| Low | Low | Retrieval fundamentally broken | Check embeddings, chunking strategy |

### Prism v1.0.0 Violet: High P, Low Recall

```
P@5 = 0.89 → "When Prism retrieves a chunk, 89% of the time it's relevant."
Recall = 0.51 → "But Prism only finds 51% of the relevant chunks total."

Example query: "What are the RBI guidelines on UPI merchant limits?"

Relevant chunks in corpus: [merchant_limit_2024, merchant_kyc, limit_circular_2023, payment_cap, psp_obligations]

Prism retrieved: [merchant_limit_2024, merchant_kyc, some_unrelated_chunk, another_unrelated, payment_cap]

Precision@5 = 3/5 = 0.60 (found 3 right ones, 2 noise)
Recall = 3/5 = 0.60 (missed limit_circular_2023 and psp_obligations)
```

Why did it miss them? `limit_circular_2023` might use different phrasing: *"The ceiling for merchant UPI collections was revised..."* — no overlap with "merchant limits". Single-phrasing retrieval misses it.

Multi-Query generates: `"UPI merchant payment ceiling"`, `"RBI merchant collection limit"`, `"PSP merchant UPI cap"` → retrieves from all three → pools candidates → recall rises.

---

---

## 10. Idempotent Ingestion — Content-Addressed Deduplication

### The Problem Without It

User uploads `rbi_circular_2024.pdf`. Server ingests it — 143 chunks in ChromaDB. User uploads the same file again (maybe they weren't sure it worked). Without deduplication: 286 chunks. Same content stored twice. Retrieval returns duplicate chunks → LLM sees `[1]` and `[3]` with identical text → wastes context window → degrades answer quality.

### The Fix: MD5 Content Hash as Chunk ID

```python
# ingest.py
def _chunk_id(chunk) -> str:
    source = chunk.metadata.get("source", "")   # filename
    page = str(chunk.metadata.get("page", ""))  # page number
    content_hash = hashlib.md5(
        (source + page + chunk.page_content).encode()
    ).hexdigest()
    return content_hash  # e.g. "a3f9c2d1..."
```

Same file + same page + same text → same MD5 → same ID. ChromaDB uses IDs as primary keys. Upsert with existing ID = no-op.

```python
def embed_and_store(chunks, collection_name):
    ids = [_chunk_id(chunk) for chunk in chunks]
    
    # Check what already exists
    existing_ids = set(vectorstore.get()["ids"])
    
    # Only embed chunks not already in ChromaDB
    new_indices = [i for i, doc_id in enumerate(ids) if doc_id not in existing_ids]
    
    if new_indices:
        vectorstore.add_texts(
            texts=[texts[i] for i in new_indices],
            ids=[ids[i] for i in new_indices]
        )
        # "Added 143 new chunks (skipped 0 existing)"
    else:
        pass  # "All chunks already exist, skipping"
```

**Result:** Upload same PDF 10 times → still 143 chunks. ChromaDB stays clean.

### Why MD5 (Not Sequential IDs)

| ID scheme | Problem |
| --- | --- |
| Auto-increment (1, 2, 3…) | Same chunk uploaded twice gets IDs 1 and 144 — no way to detect duplicate |
| Random UUID | Same chunk → different UUID every time → duplicates pile up |
| MD5(source + page + text) | Same chunk → same ID → ChromaDB rejects duplicate on upsert |

This is the **content-addressed storage** pattern — same content always maps to same address (hash). Git uses the same idea for blobs.

---

## 11. RecursiveCharacterTextSplitter — How Text Gets Chunked

### The Problem with Fixed Splits

Splitting every 500 characters naively:

```
"...comply with Section 7(b) of the Act. |SPLIT| Payment systems must maintain..."
```

Cut mid-sentence. "Section 7(b)" separated from "Payment systems must maintain" — the context that makes "Section 7(b)" meaningful is now in a different chunk. The embedding for that chunk is weak.

### How RecursiveCharacterTextSplitter Works

It tries a priority list of separators, from most preferred to least:

```python
separators = ["\n\n", "\n", " ", ""]
# Priority: paragraph break > line break > word break > character break
```

For a given `chunk_size=500`:

1. **Try `\n\n` first** — split at paragraph boundaries. If resulting piece ≤ 500 chars: done.
2. **If piece still >500** — try `\n` (line breaks within the paragraph).
3. **If still >500** — try spaces (word boundaries).
4. **Last resort** — split at exact character position.

**Result:** Chunks break at natural language boundaries when possible, hard character cuts only when forced.

### Overlap — Why Adjacent Chunks Share Text

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,  # last 50 chars of chunk N = first 50 chars of chunk N+1
)
```

Without overlap:
```
Chunk 1: "...UPI transaction limits are set by NPCI guidelines for"
Chunk 2: "each payment service provider based on risk assessment."
```
Query `"UPI limit by PSP"` — the full sentence is split. Neither chunk alone has a strong embedding.

With overlap=50:
```
Chunk 1: "...UPI transaction limits are set by NPCI guidelines for each"
Chunk 2: "for each payment service provider based on risk assessment."
```
The bridging phrase appears in both chunks. One of them will have a strong vector for the full concept.

### In Prism

```python
# ingest.py
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,   # from config.yaml
    chunk_overlap=50,
)
chunks = splitter.split_documents(documents)
```

**Note:** Prism originally used ParentDocumentRetriever (child 200 / parent 800). The current code uses a single-pass splitter at 500 chars. The architecture.md documents the intended design; the code reflects the current implementation. Both teach the same concept — chunk size is a precision-vs-context tradeoff.

---

## 12. ConversationBufferWindowMemory — Sliding Window Chat History

### Why You Need Memory in a Chat System

Each `POST /api/chat` is a stateless HTTP request. The LLM has no memory of what was said 10 seconds ago. Without memory:

```
User: "Tell me about UPI transaction limits."
Prism: "UPI P2P limit is ₹1 lakh per day..."

User: "What about merchant payments?"   ← no context
LLM sees: question = "What about merchant payments?"  ← what is "about"? who knows?
Prism: "Merchant payments are a type of..."  ← wrong, generic answer
```

### How ConversationBufferWindowMemory Works

Keeps last `k` conversation turns (human + AI) as a rolling window:

```python
# memory.py
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    return_messages=True,
    output_key="answer",   # ← critical — explained below
    k=10,                  # keep last 10 turns
)
```

Turn 1: `[Human: "Tell me about UPI limits", AI: "UPI P2P is ₹1 lakh..."]`
Turn 2: `[Human: "Tell me about UPI limits", AI: "...", Human: "What about merchant payments?", AI: "Merchant UPI limit is ₹5 lakh..."]`

At turn 11: Turn 1 is evicted. Window always has last 10.

The chain sees:
```
Chat history:
  Human: Tell me about UPI limits
  AI: UPI P2P is ₹1 lakh per day...

Current question: What about merchant payments?
```
→ LLM understands "What about" refers to UPI limits. Answers correctly.

### The output_key Trap

`ConversationalRetrievalChain` returns a dict with multiple keys:

```python
result = chain.invoke({"question": "..."})
# result = {
#   "answer": "UPI P2P limit is ₹1 lakh...",
#   "source_documents": [...],
#   "question": "..."
# }
```

Memory's `save_context` call needs to know which key is the "output" to save:

```python
# WRONG — KeyError because chain returns multiple output keys
memory = ConversationBufferWindowMemory(memory_key="chat_history")

# RIGHT — tell memory exactly which key to save
memory = ConversationBufferWindowMemory(
    memory_key="chat_history",
    output_key="answer",   # save result["answer"], not the whole dict
)
```

Without `output_key="answer"`: LangChain tries to infer the output key, sees multiple candidates, raises `ValueError: Multiple keys returned`. This was a real bug hit during Prism development — subtle because the chain runs fine; the crash happens on the `save_context` call after.

---

## 13. Python GC + Why ML Objects Don't Auto-Release

### The Problem on Render 512MB

Render free tier: 512MB RAM. Prism's base memory after startup:
- CrossEncoder (TinyBERT): ~17MB
- ChromaDB Chroma object: ~50MB
- LLM chain (Groq client + LangChain objects): ~150MB
- Python runtime: ~50MB

Total: ~267MB. Headroom: ~245MB.

A web search query adds:
- Tavily content: ~9KB (small, fine)
- `condense_question()` LLM call: creates new ChatGroq messages + response objects in memory
- `run_query_with_web()` LLM call: same
- String concatenation of context (~5KB of chunk text)

Peak usage during a web query: ~490MB. Close to limit.

After the request completes: Python's reference count for those objects drops to 0. *Should* be released. **Isn't.**

### Why Python Doesn't Auto-Release

Python uses **reference counting** + **cyclic garbage collector**. But:

1. **LangChain objects have circular references.** `chain` → `memory` → `chain` (memory holds a reference to the chain's output_key config). Cyclic references aren't freed by reference counting alone — only the cyclic GC finds them.

2. **Python's cyclic GC runs on a schedule** (every N allocations, not after every request). High-frequency server = GC may not run between requests.

3. **Result:** Objects from request N are still in memory when request N+1 starts. Near 512MB ceiling, request N+1 tips over.

### The Fix: Explicit `gc.collect()` After Each Request

```python
# routes/chat.py
import gc

@router.post("/chat")
async def chat(request, body):
    # ... run query ...
    result = run_query_with_web(chain, retriever, memory, question, web_sources)
    
    gc.collect()  # Force cyclic GC — finds and frees circular ref objects immediately
    
    return result
```

`gc.collect()` runs Python's cyclic garbage collector immediately, freeing objects that reference counting missed. Memory drops back to ~267MB before next request arrives.

**Trade-off:** ~1-2ms per request. Negligible vs query latency (~2s). No choice on 512MB.

**General rule:** Any ML server running on constrained RAM should call `gc.collect()` after each request that creates large intermediate objects (LLM responses, embeddings, string buffers).

---

## 14. LLM at Ingest Time — The Briefing Pattern

### Two Places LLMs Can Run in a RAG System

Most tutorials show LLM running only at **query time**: user asks → retrieve → LLM answers.

Prism also runs LLM at **ingest time**: document uploaded → LLM summarizes → shown to user immediately.

```
INGEST TIME (once, when doc uploaded):
  PDF → chunks → embed → store
                ↓ (also)
            LLM reads first 6 chunks
            → generates 5-bullet summary
            → generates 3 suggested questions
            → returned in upload response

QUERY TIME (every user message):
  question → retrieve → LLM answers
```

### Why This Is Useful

When a user uploads an unfamiliar document, they don't know what to ask. The briefing gives them:

1. **Orientation** — "what is this document about?"
2. **Starting questions** — clickable prompts that immediately work

```python
# briefing.py
def generate_briefing(doc_name: str, text_sample: str) -> dict:
    prompt = f"""
    Analyze this document excerpt and respond with valid JSON only.
    Document: {doc_name}
    Content: {text_sample[:3000]}
    
    Return exactly: {{"summary": ["5 bullet strings"], "suggested_questions": ["3 question strings"]}}
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    # Parse JSON from response → return to frontend
```

```python
# routes/upload.py — after ingestion completes:
briefing = generate_briefing(doc_name, sample_text)
return {
    "uploaded": [filename],
    "documents": docs,
    "briefing": briefing,   # ← frontend shows this immediately
}
```

### Design Decisions

**Non-critical path** — briefing failure doesn't block upload:
```python
try:
    briefing = generate_briefing(...)
except Exception as e:
    logger.warning("Briefing skipped: %s", e)
    briefing = None  # upload still succeeds
```

**JSON extraction from LLM output** — LLMs often wrap JSON in markdown fences (` ```json`). Prism strips these with regex before `json.loads()`:
```python
raw = re.sub(r"^```(?:json)?\s*", "", raw)  # strip opening fence
raw = re.sub(r"\s*```$", "", raw)           # strip closing fence
match = re.search(r"\{.*\}", raw, re.DOTALL)  # extract JSON object
data = json.loads(match.group())
```

**When to use LLM at ingest time vs query time:**

| | Ingest time | Query time |
| --- | --- | --- |
| Runs | Once per document | Once per user message |
| Cost | Fixed (paid once) | Scales with usage |
| Best for | Document-level metadata, summaries, question suggestions | Answering specific user questions |
| Examples | Briefing, contextual retrieval, chunk tagging | RAG answer, faithfulness eval, HyDE |

The most powerful use of ingest-time LLM is **contextual retrieval** (roadmap): for every chunk, ask LLM "given this full document, write 2 sentences situating this chunk" — then prepend that context before embedding. Anthropic reports ~49% reduction in retrieval failures. Same LLM-at-ingest-time pattern, much higher impact.

---

---

## 15. Eval Dashboard Metrics — Full Reference

Prism's eval dashboard shows 7 numbers per run. Each answers a different question about the system. Understanding *what* each metric measures, *how* it's computed, and *what can fool it* is the difference between blindly running evals and actually improving the system.

---

### Overview — What Each Metric Diagnoses

```
Query → [Retrieval] → top-5 chunks → [LLM] → answer
           ↑                ↑                 ↑
      Precision@5     Context Recall     Answer Correctness
                                         Answer Relevancy
                                         Latency p50/p95/p99
```

| Metric | What it measures | Requires ground truth? | LLM call? |
| --- | --- | --- | --- |
| Answer Correctness | Is the answer factually right? | Yes | Yes (judge) |
| Answer Relevancy | Does answer address the question? | No | Yes + embed |
| Context Recall | Did retrieval find all needed chunks? | Yes | Yes (RAGAS) |
| Precision@5 | Are the top-5 chunks relevant? | Yes (keywords/sources) | No |
| Latency p50/p95/p99 | How fast is the system? | No | No |

---

### Metric 1 — Answer Correctness (primary)

**Question it answers:** "Is Prism's answer actually correct?"

**Why it's primary:** The only metric that directly measures answer quality vs a human-authored reference. Everything else is a proxy.

**How it's computed:**

```python
CORRECTNESS_PROMPT = """
You are an evaluation judge. Score the generated answer against the reference answer.

Use a 1–5 integer scale:
5 — All key facts present and correct
4 — Most key facts correct, minor omissions or imprecision
3 — Some key facts correct, moderate gaps
2 — Few facts correct, significant errors or hallucinations
1 — Completely wrong, irrelevant, or contradicts reference

Reference answer: {ground_truth}
Generated answer: {answer}

Respond with JSON: {"score": 4, "reason": "one sentence"}
"""

# Normalize 1–5 → 0–1
score_normalized = (raw_score - 1) / 4
```

**Example:**

```
Ground truth: "UPI P2P limit is ₹1 lakh per transaction per day per NPCI guidelines."
Answer:       "You can transfer up to ₹1 lakh daily on UPI for person-to-person transfers."

Judge: score=4 (correct amount + correct type, slight imprecision on "per transaction")
Normalized: (4-1)/4 = 0.75
```

**What the judge model sees:** Only the answer and ground truth. NOT the retrieved chunks. This is intentional — if the answer is wrong but the chunks were correct, that's an LLM reasoning failure. If the answer is right but the chunks were irrelevant, that's lucky hallucination.

**What fools it:**
- 8B judge is lenient — "approximately correct" often scores 4/5
- Rephrased correct answers may score 3 if judge doesn't recognize equivalence
- Very long answers may confuse the judge — score correct facts buried in padding lower

**Prism v1.0.0 result:** `0.82` — 82% of answers have most key facts correct. Target: >0.85 via better retrieval (Multi-Query → more context → better answers).

---

### Metric 2 — Answer Relevancy

**Question it answers:** "Did Prism answer the question that was actually asked, or did it go off on a tangent?"

**How it's computed (RAGAS):**

```
Step 1: Given the generated answer, LLM generates N reverse questions
        Answer: "UPI P2P limit is ₹1 lakh per day..."
        Reverse Q1: "What is the UPI transaction limit?"
        Reverse Q2: "How much can you transfer via UPI P2P daily?"
        Reverse Q3: "What is the per-day UPI P2P cap?"

Step 2: Embed original question + all N reverse questions
        embed("What is the UPI transaction limit for P2P transfers?") → vector_q
        embed("What is the UPI transaction limit?") → vector_r1
        embed("How much can you transfer via UPI P2P daily?") → vector_r2

Step 3: Cosine similarity between original question and each reverse question
        sim(vector_q, vector_r1) = 0.94
        sim(vector_q, vector_r2) = 0.91
        sim(vector_q, vector_r3) = 0.89

Step 4: Answer relevancy = mean similarity = (0.94 + 0.91 + 0.89) / 3 = 0.91
```

**Intuition:** If the answer actually addresses the question, reverse-engineered questions from that answer will be similar to the original question. If the answer went off-topic, the reverse questions will diverge.

**What fools it:**
- **Verbosity penalty:** Groq 70B tends to over-explain. A padded answer like "Great question! UPI P2P limit is ₹1 lakh. UPI has transformed payments in India, with many PSPs offering..." generates reverse questions about UPI history, not the limit → lower similarity → lower score.
- Doesn't check factual correctness — a confident wrong answer can score high if it's "on topic".

**Prism v1.0.0 result:** `0.62` — lower than expected. Direct cause: Groq 70B verbose responses. Fix: tighter system prompt (`"Be concise. One paragraph maximum."`).

---

### Metric 3 — Context Recall

**Question it answers:** "Did the retriever surface all the chunks that were needed to construct a correct answer?"

**How it's computed (RAGAS):**

```
Step 1: Take ground truth reference answer
        "UPI P2P limit is ₹1 lakh per day. Merchant UPI payments are capped at ₹5 lakh."

Step 2: RAGAS LLM breaks it into individual factual sentences (claims)
        Claim A: "UPI P2P limit is ₹1 lakh per day."
        Claim B: "Merchant UPI payments are capped at ₹5 lakh."

Step 3: For each claim, check: can this claim be attributed to any retrieved chunk?
        Claim A → search retrieved chunks → Chunk 3 contains "P2P cap ₹1 lakh" → ATTRIBUTED ✓
        Claim B → search retrieved chunks → no chunk mentions merchant cap → NOT ATTRIBUTED ✗

Step 4: Context recall = attributed claims / total claims = 1/2 = 0.50
```

**Intuition:** Recall measures completeness of the retrieval pool. Low recall = the retriever missed relevant chunks → LLM can't answer completely even if it tries → answer will be incomplete or hallucinated.

**Why this is the most important metric to improve:**
- Low recall (0.51 in v1.0.0) means ~half the relevant information is missing from context
- LLM can only work with what it's given — perfect LLM + bad retrieval = bad answer
- Improving recall directly improves answer quality

**What fools it:**
- Ground truth phrasing matters — if GT says "₹1 lakh" and the chunk says "100,000 rupees", RAGAS LLM may or may not link them
- Long GT answers with many claims → denominator grows → harder to achieve high recall

**Prism v1.0.0 result:** `0.51` — retriever finds correct chunks (P@5=0.89) but misses ~half the relevant ones. **Directly motivates Multi-Query Retrieval.**

---

### Metric 4 — Precision@5

**Question it answers:** "Of the 5 chunks Prism returned, how many were actually relevant?"

**How it's computed (custom, deterministic — no LLM):**

```python
def compute_precision_at_k(query, retrieved_chunks, ground_truth, k=5):
    relevant_sources = ground_truth.get("relevant_sources", [])   # expected source filenames
    keywords = ground_truth.get("relevant_chunk_keywords", [])     # expected keywords

    top_k = retrieved_chunks[:k]
    relevant_count = 0

    for chunk in top_k:
        source_match = chunk["source"] in relevant_sources
        keyword_match = any(kw.lower() in chunk["content"].lower() for kw in keywords)
        
        if source_match or keyword_match:    # OR — either condition counts
            relevant_count += 1

    return relevant_count / k   # 0.0 – 1.0
```

**Example eval pair:**
```json
{
  "query": "What is the UPI merchant payment limit?",
  "relevant_sources": ["npci_merchant_guidelines.pdf"],
  "relevant_chunk_keywords": ["merchant", "₹5 lakh", "payment cap", "PSP ceiling"]
}
```

Retrieved chunks:
```
Chunk 1 (source: npci_merchant_guidelines.pdf) → source_match ✓ → relevant
Chunk 2 (content: "...merchant PSP ceiling is ₹5 lakh...") → keyword_match ✓ → relevant
Chunk 3 (source: rbi_circular.pdf, content: "UPI transaction monitoring...") → neither → irrelevant
Chunk 4 (source: npci_merchant_guidelines.pdf) → source_match ✓ → relevant
Chunk 5 (content: "...digital payment systems in India...") → neither → irrelevant

P@5 = 3/5 = 0.60
```

**Why deterministic (no LLM):**
- Fast — runs per-query without API calls
- Reproducible — same query always same score
- No rate limits — can evaluate 50 pairs without hitting Groq TPD

**What fools it:**
- Source OR keyword: a chunk from the wrong document that happens to mention a keyword counts as relevant
- Keyword list quality matters — too broad → everything matches, score inflates → too narrow → correct chunks missed, score deflates

**Prism v1.0.0 result:** `0.89` — 89% of retrieved chunks are relevant. High precision + low recall = pool is accurate but too narrow. The retriever is finding the right kind of chunks, just not enough of them.

---

### Metric 5 — Latency p50 / p95 / p99

**Question it answers:** "How fast is Prism in practice?"

**Why three numbers instead of average:**

```
Query latencies (ms): [1800, 1950, 2100, 1900, 2050, 2200, 1850, 3800, 2000, 1950]
                                                                  ↑ one slow outlier

Mean: 2160ms  ← pulled up by the outlier, misleading
p50:  1975ms  ← 50% of queries faster than this (typical experience)
p95:  3230ms  ← 95% of queries faster than this (worst normal case)
p99:  3740ms  ← 99% of queries faster than this (absolute worst)
```

**How it's computed:**

```python
import numpy as np

# Measure per query: retrieval + LLM call (no Tavily, no web search)
t0 = time.time()
answer, docs, chunks = _answer_query(llm, retriever, query)
latency_ms = int((time.time() - t0) * 1000)
latencies.append(latency_ms)

# After all queries:
p50 = int(np.percentile(latencies, 50))   # median
p95 = int(np.percentile(latencies, 95))   # 95th percentile
p99 = int(np.percentile(latencies, 99))   # 99th percentile
```

**What's included in the latency measurement:**
- ChromaDB dense retrieval (cosine ANN search)
- BM25 sparse retrieval (in-memory token scoring)
- RRF fusion (pure Python, negligible)
- TinyBERT cross-encoder reranking (BERT forward pass × 10 pairs)
- Groq LLM call (network + inference)

**What's NOT included:**
- Tavily web search (separate, always adds 500–1000ms)
- HyDE expansion (adds one extra Groq call ~200ms)
- Python GC (`gc.collect()` after response)

**Prism v1.0.0 result:** `p50=2029ms, p95=TBD, p99=TBD` — median 2s. Render free vCPU is the bottleneck (TinyBERT reranker runs on CPU). Groq inference itself is ~300ms; the 1.7s remainder is retrieval on cold hardware.

**Production benchmarks for context:**

| System | p50 target | Notes |
| --- | --- | --- |
| Search engine | <200ms | Pre-indexed, no LLM |
| RAG (GPU cloud) | 500–800ms | GPU reranker + fast LLM |
| Prism (Render free CPU) | ~2000ms | CPU reranker + network LLM |
| Prism + streaming | ~300ms to first token | Same total time, perceived faster |

---

### How the Metrics Interact — Reading the Dashboard

```
High correctness + high recall + high P@5 = system is working ✅

High P@5 + low recall:
→ Retriever finds right chunks but misses others
→ Fix: Multi-Query Retrieval, HyDE

Low P@5 + high recall:
→ Retriever finds many chunks but most are noise
→ Fix: stricter reranking, smaller retrieve_k

High recall + low correctness:
→ Retriever gave good context, LLM failed to use it
→ Fix: better system prompt, larger LLM model

Low relevancy + high correctness:
→ LLM is verbose/padded but factually right
→ Fix: tighter prompt ("be concise, one paragraph maximum")

High latency p99 >> p50:
→ Occasional slow queries (complex retrieval or Groq congestion)
→ Monitor, add timeout handling
```

**Prism v1.0.0 Violet diagnostic:**

```
correctness=0.82  ← good but room to grow
relevancy=0.62    ← low → verbose LLM responses (prompt fix)
recall=0.51       ← low → missing chunks (Multi-Query fix)
P@5=0.89          ← high → retrieved chunks are correct when found
p50=2029ms        ← expected on Render free CPU

Verdict: retrieval recall is the primary bottleneck.
Fix recall → more relevant context → higher correctness → all metrics improve.
```

---

## 16. Multi-Workspace Isolation — One Collection Per Context

### The Problem with a Single Global Collection

Early Prism had one ChromaDB collection for all documents. Load an RBI circular and an earnings transcript → both in the same retrieval pool. Query `"What were NPCI's FY24 revenues?"` → retriever pulls from both → RBI policy chunks contaminate the answer → hallucination risk.

No way to scope a conversation to one document set without re-ingesting everything.

### The Fix: One ChromaDB Collection Per Workspace

```
Workspace "rbi-policy"   → ChromaDB collection: "rbi-policy"   → only RBI docs
Workspace "kotak-q4"     → ChromaDB collection: "kotak-q4"     → only earnings docs
Workspace "default"      → ChromaDB collection: "default"       → general docs
```

Every API request carries `workspace_id`:

```python
# Frontend sends workspace_id on every request
POST /api/chat?workspace=rbi-policy       { "question": "..." }
POST /api/upload?workspace=kotak-q4       (file upload)
GET  /api/documents?workspace=default
```

Backend resolves the correct collection before retrieval:

```python
# routes/chat.py
retriever = get_retriever(workspace_id)   # returns cached retriever for that collection
result = run_query_with_web(chain, retriever, memory, question, web_sources)
```

### The ChromaDB Version Compatibility Bug

`client.list_collections()` changed return type between ChromaDB versions:

```python
# chromadb < 0.5.4 returns:  list[Collection]  (objects with .name attribute)
# chromadb ≥ 0.5.4 returns:  list[str]         (names directly)

# Wrong — crashes on one version or the other:
names = [c.name for c in client.list_collections()]

# Right — isinstance check handles both:
collections = client.list_collections()
names = [c if isinstance(c, str) else c.name for c in collections]
```

Pinning library versions prevents this, but the guard is worth knowing — breaking API changes inside minor versions are common in fast-moving ML libraries.

### Frontend: Remount on Workspace Switch

React component state persists across renders unless the component unmounts. Switching workspace while ChatArea holds 20 messages → messages from workspace A appear in workspace B's view.

Fix: `key` prop forces full remount when workspace changes:

```jsx
// App.jsx
<ChatArea
  key={workspaceId}       // ← when workspaceId changes, React destroys + recreates component
  workspaceId={workspaceId}
  ...
/>
```

`key` prop is React's escape hatch for "this is a genuinely new instance, not an update". Any state inside ChatArea (messages, scroll position, loading flags) resets to initial on workspace switch.

### BM25 + Retriever Cache Per Workspace

Each workspace needs its own BM25 index (built from that collection's chunks) and its own retriever singleton:

```
_indexes: dict[str, BM25Index] = {}         # one BM25 per workspace
_vs_cache: dict[str, Chroma] = {}           # one vectorstore per workspace
_retriever_cache: dict[str, HybridRetriever] = {}  # one retriever per workspace
```

After upload to workspace "rbi-policy":
1. `invalidate_cache("rbi-policy")` — drop stale vectorstore + retriever
2. `build_from_vectorstore(vectorstore, workspace_id="rbi-policy")` — rebuild BM25 from new chunks
3. `get_retriever("rbi-policy")` — rebuild retriever with fresh vectorstore

Other workspaces untouched. Isolation is complete.

---

## 17. Multi-Query Retrieval — Wider Net for Higher Recall

### The Problem: Single Phrasing Has Blind Spots

A query hits ChromaDB + BM25 with one set of tokens. Corpus chunks that express the same concept differently never surface.

```
Query: "What is the UPI merchant limit?"

Corpus has:
  Chunk A: "merchant UPI transaction cap is ₹5 lakh"      ← found ✓ (keyword match)
  Chunk B: "ceiling for PSP collections was revised..."    ← MISSED (different vocab)
  Chunk C: "payment service providers may not exceed..."   ← MISSED (no "merchant" token)
```

Chunk B and C are relevant. Single-phrasing retrieval misses them. This is why Prism v1.0.0 Violet had context_recall = 0.51 — only half the needed chunks were retrieved.

### The Fix: Generate 3 Phrasings, Pool Results

```
Step 1: LLM generates 3 paraphrases of the original query
  Original:    "What is the UPI merchant limit?"
  Phrasing 2:  "What is the PSP payment ceiling for UPI collections?"
  Phrasing 3:  "How much can merchants accept via UPI transactions?"

Step 2: Run retrieval for EACH phrasing
  Original     → [Chunk A, Chunk D, Chunk E, ...]  (retrieve_k per list)
  Phrasing 2   → [Chunk B, Chunk A, Chunk F, ...]  ← Chunk B appears now
  Phrasing 3   → [Chunk C, Chunk B, Chunk G, ...]  ← Chunk C appears now

Step 3: Pool + deduplicate by content key (keep best rank per chunk)
  Combined unique pool: [A, B, C, D, E, F, G, ...]

Step 4: RRF fuse the deduplicated pool → rerank top-5
  Reranker sees 30 candidates instead of 10 → picks best 5 from wider pool
```

### Why Deduplication Uses Best Rank

If Chunk A appears at rank 1 in phrasing 1 and rank 3 in phrasing 2, keep it at rank 1 — its highest-confidence rank. The merged ranked list is then sorted by best rank before RRF fusion.

```python
# retriever.py — deduplication loop
for rank, doc in enumerate(d_results):
    key = doc["content"][:120]
    if key not in dense_seen or rank < dense_seen[key][0]:
        dense_seen[key] = (rank, doc)  # keep best (lowest) rank

dense_pool = [doc for _, doc in sorted(dense_seen.values(), key=lambda x: x[0])]
```

### In Prism

```python
# retriever.py
def _multi_query_expand(self, query: str) -> list[str]:
    prompt = (
        "Generate 3 different phrasings of the following question for document retrieval. "
        "Each phrasing must use different vocabulary but seek the same information. "
        "Return ONLY the 3 questions, one per line, no numbering, no preamble.\n\n"
        f"Question: {query}"
    )
    # returns [original_query, phrasing_2, phrasing_3, phrasing_4]

def _get_relevant_documents(self, query, ...):
    queries = self._multi_query_expand(query) if self.use_multi_query else [query]
    
    dense_seen, sparse_seen = {}, {}
    for q in queries:
        # retrieve for each phrasing, keep best rank per unique chunk
        ...
    
    dense_pool = sorted_by_best_rank(dense_seen)
    sparse_pool = sorted_by_best_rank(sparse_seen)
    
    fused = self._rrf_fuse(dense_pool, sparse_pool)   # wider pool
    reranked = rerank(query, fused[:retrieve_k], top_k=rerank_k)  # reranker uses original query
```

**Off by default** (`config.yaml` `multi_query_enabled: false`) — adds one Groq call per query (~200ms). Enable → run eval (`scripts/run_eval_versioned.py --version v1.1.0 --tag "Indigo"`) → measure context_recall delta vs 0.51.

**Expected lift:** context_recall 0.51 → measurably higher. No change expected to P@5 (already 0.89) — recall improvement without precision degradation.

**Cost:** 1 extra Groq call + 3× retrieval calls (fast, in-memory) + 3× BM25 (negligible). Parallelisable with `asyncio.gather` if latency becomes a concern.

**Reranker still uses original query** — not the phrasings. The phrasings widen the candidate pool; the reranker judges relevance against what the user actually asked.

---

## Summary — Key Concepts Cheatsheet

| Concept | What it solves | Where in Prism |
| --- | --- | --- |
| ParentDocumentRetriever | Retrieval precision + answer faithfulness | Ingestion + retrieval layer |
| InMemoryStore | Fast parent text lookup by ID | RAM store (lost on restart) |
| ChromaDB | Vector similarity search for child chunks | Persistent disk store |
| BM25Okapi | Exact keyword matching with TF saturation | Sparse retrieval (weight 0.3) |
| RRF | Merging dense + sparse rankings (scale-agnostic) | Post-retrieval fusion |
| Cross-Encoder | Accurate joint query-doc relevance scoring | Final reranking step |
| Chain condensation trap | Why LangChain strips web context silently | Web query bypass in chain.py |
| Singleton ML pattern | OOM prevention — one model load per process | BM25, reranker, retriever cache |
| HyDE | Closes question-answer vector space gap | Dense retrieval (toggle: hyde_enabled) |
| Faithfulness is circular | Why eval metrics designed alongside corpus lie | answer_correctness chosen as primary |
| P@5 + Recall diagnostic pair | Identifies whether retrieval pool is narrow or noisy | v1.0.0 Violet: P=0.89, R=0.51 |
| Idempotent ingestion (MD5) | Re-uploading same doc doesn't duplicate chunks | ingest.py `_chunk_id()` |
| RecursiveCharacterTextSplitter | Splits at paragraph/line/word/char in priority order | ingest.py chunking |
| ConversationBufferWindowMemory | Sliding k-window of chat history + output_key trap | memory.py, used in chain |
| gc.collect() for ML servers | Cyclic refs prevent Python auto-release; explicit GC needed | routes/chat.py post-request |
| LLM at ingest time | Briefing pattern — run LLM once per doc, not per query | briefing.py on upload |
| Answer Correctness | LLM judge 1–5 vs ground truth, normalized → 0–1 | Primary metric, independent of retrieved chunks |
| Answer Relevancy | Reverse-question cosine similarity — penalizes verbose LLM | RAGAS, no ground truth needed |
| Context Recall | GT sentences attributed to retrieved chunks ÷ total | RAGAS, measures retrieval completeness |
| Precision@5 | Relevant chunks in top-5 ÷ 5, source + keyword match | Custom deterministic, no LLM call |
| Latency p50/p95/p99 | Percentile timing: median / worst-normal / absolute-worst | numpy.percentile over per-query ms measurements |
| Multi-workspace isolation | One ChromaDB collection per workspace; key prop remounts React | workspaces.py + _vs_cache + _retriever_cache + key={workspaceId} |
| Multi-Query Retrieval | Wider candidate pool → higher context_recall; dedup by best rank | retriever.py `_multi_query_expand()` (toggle: multi_query_enabled) |
| FastAPI BackgroundTasks | Non-blocking background work after response sent | Two-phase contextual upload in routes/upload.py |
| asyncio.Semaphore for rate limits | Cap parallel API calls to stay under TPM ceiling | `contextualize_chunks_async()` with Semaphore(3) |

---

## 18. FastAPI BackgroundTasks — Non-Blocking Post-Response Work

### The Problem

Contextual retrieval requires one Groq LLM call per chunk. 30 chunks × 1 call = 30 serial API calls = ~40s. If upload waits for all of them, user sees a frozen UI for 40s before getting any response.

### The Pattern

```
Request → sync work (fast) → return response → background work (slow, after response sent)
```

FastAPI `BackgroundTasks` runs registered functions **after** the response is returned to the client. The client is unblocked immediately; the server continues the slow work in the background.

```python
from fastapi import BackgroundTasks

@router.post("/upload")
async def upload_files(background_tasks: BackgroundTasks, ...):
    # Phase 1 — sync, fast (<3s)
    chunks = chunk_documents(documents)
    embed_and_store(chunks, workspace)      # Euron API, sequential
    _rebuild_chain(app, workspace)          # user can query now

    # Phase 2 — async, slow (~30–60s, after response)
    background_tasks.add_task(
        _contextual_refresh_bg,             # async function
        app, documents, chunks, workspace, ...
    )

    return {"status": "ingested"}           # returned before bg starts
```

### What `_contextual_refresh_bg` does

1. Deep-copies chunks (so original chunks not mutated)
2. Calls `contextualize_chunks_async()` — parallel Groq calls with Semaphore
3. Deletes old (non-contextual) chunk IDs from ChromaDB
4. Embeds contextual chunks via Euron API
5. Rebuilds chain

### Trade-off

| Approach | Upload latency | Chunk quality on first query |
|----------|---------------|------------------------------|
| Sync contextual | 40s+ | Contextual from start |
| BackgroundTask | <3s | Non-contextual for ~30–60s, then contextual |
| No contextual | <3s | Non-contextual always |

First-query window with non-contextual chunks is acceptable at demo scale — recall difference is measurable on 50-pair eval, not user-perceptible on single queries.

### When BackgroundTasks is wrong

- Long background work that must complete before next request (chain rebuilds mid-query)
- Work that must survive server restart (BackgroundTask lives in process — if Render cold-starts between upload and background completion, the task is lost)
- Fix: use a task queue (Celery, ARQ) for durable background work

---

## 19. asyncio.Semaphore — Rate-Limiting Parallel API Calls

### The Problem

`asyncio.gather()` launches ALL coroutines at once. With 30 chunks and 30 parallel Groq calls, you get a 30k token burst against a 6000 TPM (tokens per minute) rate limit → instant 429 storm.

Naive solution (sequential for loop) is safe but slow: 30 × 1.5s = 45s.

### The Fix — Semaphore

A `Semaphore(N)` is a counter initialized to N. `async with sem:` decrements it; releases on exit. When counter = 0, any new `async with sem:` blocks until another coroutine exits.

Effect: at most N coroutines execute the guarded block simultaneously.

```python
sem = asyncio.Semaphore(3)          # max 3 concurrent Groq calls

async def _contextualize_one(sem, llm, chunk, ...):
    async with sem:                 # blocks if 3 already running
        response = await llm.ainvoke(...)
        chunk.page_content = f"{response.content} {chunk.page_content}"

await asyncio.gather(*[
    _contextualize_one(sem, llm, chunk, ...)
    for chunk in chunks
])
```

### TPM math for Prism

- Each contextualization prompt: ~1000 tokens (doc snippet + chunk + instruction)
- `max_concurrent=3` → max 3 × 1000 = 3000 tokens in flight at once
- Groq free tier: `llama-3.1-8b-instant` → 6000 TPM limit
- 3000 TPM burst = 50% of limit → safe headroom

`max_concurrent=20` was the bug: 20 × 1000 = 20k token burst → 429 on every batch.

### Smart 429 retry

Groq 429 error messages include the suggested wait time:
`"Rate limit exceeded. Please try again in 10.5s."`

Parse this instead of using hardcoded sleep:

```python
except Exception as e:
    wait = 12.0                                   # default fallback
    if "try again in" in str(e):
        m = re.search(r"try again in ([\d.]+)s", str(e))
        if m:
            wait = float(m.group(1)) + 1.0        # suggested + 1s buffer
    await asyncio.sleep(wait)
```

Hardcoded 2s retry was too short — Groq's rate limit resets in 10–60s windows depending on model and tier.

### Semaphore vs other approaches

| Approach | Speed | Safety | Complexity |
|----------|-------|--------|-----------|
| Sequential loop | Slowest | ✅ Never rate limited | Simplest |
| `asyncio.gather` (no sem) | Fastest | ❌ 429 storm | Simple |
| `asyncio.gather` + Semaphore | Near-fastest | ✅ TPM controlled | Low |
| Celery/ARQ task queue | Fast + durable | ✅ Best | High |

---

## 20. Semantic Chunking Tradeoff — Recall vs Precision

### The Problem with Fixed-Size Splits

`RecursiveCharacterTextSplitter` at 500 chars cuts mid-sentence, mid-table, mid-list. Embedding a truncated sentence returns a weak vector — the chunk doesn't represent a complete idea. Semantic chunking fixes this by splitting at topic boundaries (where cosine similarity between adjacent sentences drops below a threshold), producing variable-size chunks that each represent one coherent thought.

### What the Ablation Showed (Prism v1.4.0, 25 samples)

| Stack | recall | P@5 | latency p50 |
|-------|--------|-----|-------------|
| v1.3.0 HyDE+MQ+CTX (fixed 500-char) | 0.768 | **0.984** | 2610ms |
| v1.4.0 + Semantic chunking | **0.861** | 0.711 | 12952ms |
| Delta | +9.3pp | **−27.3pp** | 5× slower |

### Why Recall Went Up

Semantic chunks contain complete sentences and complete ideas. The embedding captures the full meaning — better vector → higher chance of matching the relevant query → more reference content covered → higher context recall.

### Why Precision Collapsed

P@5 measures overlap between retrieved chunks and the ground-truth `relevant_chunks` field in `eval_pairs.json`. Those reference chunks were defined against fixed 500-char splits. Semantic chunks have different, larger boundaries — they contain the relevant content but as part of a bigger unit, so exact overlap with the reference drops. The reranker also receives a wider, noisier candidate pool (variable-size chunks = less uniform scoring surface).

**Key insight:** P@5 is eval-alignment-sensitive. If ground truth was labelled against fixed chunks, semantic chunks will always score lower on P@5 even when they retrieve better content. For a production system with human-labelled relevance judgements (not self-aligned eval pairs), the gap would be smaller.

### Why Latency Was 5×

Semantic chunks are longer on average than 500-char fixed chunks. Longer chunks = more tokens fed to the LLM per answer generation call. Retrieval time is unchanged (semantic chunking is an ingest-time decision), but inference time scales with context length.

### Decision

Semantic chunking rejected for Prism production. v1.3.0 (HyDE + Multi-Query + Contextual) confirmed as best stack: P@5=0.984, recall=0.768, p50=2610ms.

Semantic chunking would make more sense when:
- Ground truth eval labels are created after chunking (aligned to the actual chunk boundaries)
- LLM context window is not a bottleneck
- Recall is the primary metric (e.g. legal/compliance: never miss a relevant clause)

For a demo on Render free tier: `asyncio.gather + Semaphore(3)` is the right call.