# Technical Decisions — FinRAG v2

## Decision log

| Date | Decision | Rationale | Status |
|------|----------|-----------|--------|
| 2026-05 | Euron API for embeddings (not local sentence-transformers) | Local model ~400MB → OOM on Render 512MB free tier | Active |
| 2026-05-24 | Groq (llama-3.3-70b-versatile) for LLM; Euron retained for embeddings | Groq: faster inference, open-weight model. Euron kept for embeddings — Groq has no embeddings endpoint. | Active |
| 2026-05 | Render (Docker) over Railway for backend | Free tier RAM fit confirmed: embeddings ~150MB + reranker ~17MB = ~230MB total | Active |
| 2026-05 | ParentDocumentRetriever (child 200 / parent 800) | Better faithfulness: small chunks retrieved precisely, large chunks give LLM full context | Active |
| 2026-05 | BM25 weight 0.3 in RRF fusion | Regulatory text has exact keyword matches; sparse recall is complementary, not dominant | Active |
| 2026-05-30 | RAGAS pre-computed locally, dashboard JSON-driven | `nest_asyncio` cannot patch `uvloop` on Render — live eval endpoint always 500s. Run `scripts/run_ragas_local.py` (8B judge model) → commit `ragas_benchmark.json` → Vercel builds dashboard. | Active |
| 2026-05-30 | RAGAS judge uses `llama-3.1-8b-instant` not `llama-3.3-70b` | 70B model exhausts Groq free-tier 100k TPD in one eval run. 8B has 500k TPD and is sufficient for statement-level faithfulness checks. Answer generation still uses 70B. | Active |
| 2026-05 | LangSmith tracing via env var (no code changes) | LangChain reads LANGCHAIN_TRACING_V2 automatically; zero instrumentation cost | Active |
| 2026-05-30 | Reranker switched to TinyBERT-L-2-v2 (~17MB) from MiniLM-L-6-v2 (~85MB) | MiniLM + base memory + Tavily content + LLM call exceeded 512MB on web queries; TinyBERT saves 68MB permanently with acceptable ranking quality at demo scale | Active |
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
