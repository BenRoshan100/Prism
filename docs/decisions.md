# Technical Decisions — FinRAG v2

## Decision log

| Date | Decision | Rationale | Status |
|------|----------|-----------|--------|
| 2026-05 | Euron API for embeddings (not local sentence-transformers) | Local model ~400MB → OOM on Render 512MB free tier | Active |
| 2026-05 | Render (Docker) over Railway for backend | Free tier RAM fit confirmed: embeddings ~150MB + reranker ~85MB = ~250MB total | Active |
| 2026-05 | ParentDocumentRetriever (child 200 / parent 800) | Better faithfulness: small chunks retrieved precisely, large chunks give LLM full context | Active |
| 2026-05 | BM25 weight 0.3 in RRF fusion | Regulatory text has exact keyword matches; sparse recall is complementary, not dominant | Active |
| 2026-05 | RAGAS as primary eval (custom scorer as secondary) | RAGAS provides 4 named metrics (faithfulness, answer_relevancy, context_precision, context_recall) that interviewers recognise; v1 custom scorer retained for per-turn display | Active |
| 2026-05 | LangSmith tracing via env var (no code changes) | LangChain reads LANGCHAIN_TRACING_V2 automatically; zero instrumentation cost | Active |
| 2026-05 | Cross-encoder reranker pre-downloaded at Docker build time | Avoids cold-start latency on first request in production | Active |
| 2026-05 | Idempotent ingestion via md5(source+page+text) chunk IDs | Re-running ingest does not duplicate chunks in ChromaDB | Active |

## Rejected alternatives

| Alternative | Why rejected |
|-------------|-------------|
| sentence-transformers local embeddings | ~400MB RAM → OOM on Render free tier |
| Pinecone / Weaviate vector store | Adds external dependency and cost; ChromaDB sufficient for demo scale |
| LlamaIndex instead of LangChain | LangChain has better ParentDocumentRetriever and ConversationalRetrievalChain support |
| Streaming LLM responses | Adds frontend complexity; acceptable latency at demo scale |
| BM25 persisted to disk | Not required for demo; rebuild on startup is fast enough (~1s for sample corpus) |
