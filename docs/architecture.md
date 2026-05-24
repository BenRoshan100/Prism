# Architecture — FinRAG v2

## Problem
Fintech analysts spend hours manually reading RBI circulars, NPCI reports, and earnings transcripts. Standard dense-only RAG fails silently and misses exact keyword matches in regulatory text (section numbers, policy codes).

## Architecture overview
Query → hybrid retrieval (ChromaDB dense + BM25 sparse) → weighted RRF fusion → cross-encoder rerank (top-20 → top-5) → LLM answer → faithfulness eval + LangSmith trace. ParentDocumentRetriever stores 200-char child chunks for retrieval but returns 800-char parent chunks to LLM.

## Component breakdown

| Component | Technology | Purpose |
|-----------|------------|---------|
| Vector store | ChromaDB (persistent) | Dense embedding storage and retrieval |
| Sparse retrieval | rank_bm25 (BM25Okapi) | Keyword-match retrieval for regulatory text |
| Hybrid fusion | Weighted RRF (dense 0.7 + sparse 0.3) | Merge dense + sparse result lists |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 | Re-score top-20 → return top-5 |
| Embeddings | Euron API (text-embedding-3-small) | API-based; avoids OOM on Render free tier. Groq has no embeddings endpoint. |
| LLM | Groq (llama-3.3-70b-versatile) via langchain-groq | Fast open-weight inference; OpenAI-compatible |
| Chunking | LangChain ParentDocumentRetriever | Child 200-char indexed, parent 800-char sent to LLM |
| Memory | ConversationBufferWindowMemory (k=10) | Last 10 conversation turns |
| Chain | ConversationalRetrievalChain | LangChain orchestration |
| Eval (primary) | RAGAS | faithfulness, answer_relevancy, context_precision, context_recall |
| Eval (secondary) | Custom LLM-as-Judge | 1–5 faithfulness score per turn (retained from v1) |
| Eval (retrieval) | Precision@K | Ground-truth chunk matching |
| Observability | LangSmith | Traces all LLM + retrieval calls via LANGCHAIN_TRACING_V2=true |
| Document parsing | LlamaParse (primary), pypdf (fallback) | PDF extraction |
| Backend | FastAPI + Uvicorn | REST API |
| Frontend | React 19 + Vite + Tailwind CSS v4 | Chat / Eval / Upload tabs |
| Deployment | Render (Docker backend) + Vercel (frontend) | Production |

## Data flow

### Ingestion
1. `run_ingest.py` or `POST /api/upload` → load PDFs/TXT/CSV
2. `ParentDocumentRetriever`: split into 800-char parent + 200-char child chunks
3. Embed child chunks via Euron API (text-embedding-3-small) → store in ChromaDB
4. Store parent chunks in `InMemoryStore`
5. Build BM25 index over child chunk corpus

### Query
1. `POST /api/chat` receives question
2. `dense_retrieve`: ChromaDB top-20 by cosine similarity
3. `sparse_retrieve`: BM25 top-20 by keyword score
4. `reciprocal_rank_fusion`: merge → deduplicate → RRF score
5. `Reranker.rerank`: cross-encoder score → return top-5 parent chunks
6. `ConversationalRetrievalChain`: LLM answers with context + memory
7. `score_faithfulness`: LLM-as-Judge scores answer 1–5
8. Response includes: answer, sources (with scores), faithfulness, retrieval_method

## Key design decisions
- **API embeddings over local**: sentence-transformers ~400MB OOMs on Render 512MB free tier; Euron API ~0MB. Groq used for LLM; Euron retained for embeddings (Groq exposes no embeddings endpoint).
- **ParentDocumentRetriever**: small chunks improve retrieval precision; large parent chunks improve answer faithfulness
- **Cross-encoder reranker**: bi-encoder (ChromaDB) is fast but approximate; cross-encoder is slower but more accurate on top-20 pool
- **BM25 weight 0.3**: regulatory text has exact keyword matches (section numbers); sparse retrieval catches what dense misses
- **RAGAS as primary eval**: 4 named metrics that interviewers recognise; custom scorer retained as supplementary

## Known limitations
- InMemoryStore for parent chunks: does not survive server restart (re-ingest required)
- BM25 index rebuilt in memory on each startup (not persisted to disk)
- Render free tier: 512MB RAM, cold starts after inactivity

## Future improvements
- Persist BM25 index to disk (pickle)
- Multi-collection ChromaDB (one per document set)
- Streaming responses from LLM
