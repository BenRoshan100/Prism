# Technical Decisions — Prism

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
| 2026-06-14 | Multi-workspace: one ChromaDB collection per workspace | Isolated document sets per workspace; `workspace_id` passed on every request; `list_collections()` normalised for chromadb ≥0.5.4 (returns `list[str]`) and <0.5 (returns `list[Collection]`) | Active |
| 2026-06-14 | Multi-workspace frontend: workspace switcher + per-workspace doc list and chat | Sidebar shows all workspaces; switching remounts ChatArea via React key prop to clear stale messages and state | Active |
| 2026-06-14 | Singleton vectorstore/retriever cache keyed by workspace_id | Every chat request was creating a new Chroma instance (full embedding reload) on top of the existing one → OOM on repeated queries. Cache dict in `retriever.py` reuses instances; invalidated after ingest. | Active |
| 2026-06-14 | URL size guard in url_loader.py before embedding | Large external pages (news, filings) could exhaust 512MB RAM during URL ingest. Guard truncates/rejects oversized content before embed call. | Active |
| 2026-06-16 | HyDE for dense retrieval; toggled via config.yaml `hyde_enabled` | Hypothetical answer embedding lands closer to real answer chunks in vector space than raw query. BM25 + reranker still use original query. Off by default — adds one Groq call (~200ms); enable to measure RAGAS lift before committing. | Active |
| 2026-06-17 | Web search mandatory (not toggle) | Opt-in toggle caused users to get hallucinated answers grounded in wrong corpus docs when web search was off. Always-on Tavily + RAG gives grounded answers for both corpus and open-domain queries. | Active |
| 2026-06-17 | Separate eval-dashboard as own Vercel project | Eval tooling is not user-facing; separating avoids bloating the main frontend and lets eval dashboard evolve independently | Active |
| 2026-06-17 | answer_correctness replaces faithfulness as primary metric | faithfulness (judge vs retrieved chunks) is circular — inflates when eval pairs were designed alongside corpus. answer_correctness (judge vs ground_truth reference) is independent signal | Active |
| 2026-06-17 | Per-message faithfulness badge removed from user UI | Badge added noise without value to end users; saves one Groq call per query (~200ms latency reduction); eval moved to dedicated dashboard | Active |
| 2026-06-17 | eval_pairs.json expanded 20 → 50 pairs | 20 samples not statistically meaningful; added multi-hop, comparative, negative, numeric, edge-case question types | Active |
| 2026-06-17 | Versioned eval JSON runs + index.json registry | Single flat JSON had no history; versioned runs let dashboard show metric evolution across architecture changes | Active |

## Rejected alternatives

| Alternative | Why rejected |
|-------------|-------------|
| sentence-transformers local embeddings | ~400MB RAM → OOM on Render free tier |
| Pinecone / Weaviate vector store | Adds external dependency and cost; ChromaDB sufficient for demo scale |
| LlamaIndex instead of LangChain | LangChain has better ParentDocumentRetriever and ConversationalRetrievalChain support |
| Streaming LLM responses | Adds frontend complexity; acceptable latency at demo scale |
| BM25 persisted to disk | Not required for demo; rebuild on startup is fast enough (~1s for sample corpus) |
