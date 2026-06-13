# Prism — Design Spec
**Date:** 2026-06-13  
**Author:** Ben Roshan D  
**Status:** Approved  

---

## Overview

Prism is a domain-agnostic document intelligence platform. Load any documents or URLs → Prism becomes an instant SME on that corpus. Built on the FinRAG v2 retrieval engine (BM25 + ChromaDB + RRF + CrossEncoder rerank + Groq), rebranded and extended with URL ingestion, auto-briefing, and inline citation UI.

**Not a finance tool.** Works equally for legal docs, HR policy, medical literature, research papers, or any text corpus.

---

## URLs & Repo

| Platform | Old | New |
|----------|-----|-----|
| GitHub | `FinRag` | `prism` |
| Vercel | `fin-rag-git-main-benroshan100s-projects.vercel.app` | `askprism.vercel.app` |
| Render service name | `finrag` | `prism` (display name; URL unchanged until redeploy) |
| Render URL | `finrag-v2.onrender.com` | `prism.onrender.com` (after redeploy) |

**Local directory:** `D:\ACADEMIC\GenAI Projects\FinRag` → rename to `Prism` after GitHub rename.

---

## Approach

Incremental feature stack on existing infra. Zero retrieval architecture changes. Features shipped in priority order: rebrand → URL ingestion → auto-briefing → citation UI → multi-workspace.

---

## Architecture

### What stays identical
- ChromaDB (persistent) + BM25 (in-memory) + RRF fusion (dense 0.7 + sparse 0.3)
- TinyBERT-L-2-v2 CrossEncoder reranker (top-10 → top-5)
- Euron API embeddings (text-embedding-3-small)
- Groq LLM (llama-3.3-70b-versatile)
- ConversationalRetrievalChain + ConversationBufferWindowMemory(k=10)
- Tavily web search (live queries, not ingestion)
- LangSmith tracing

### Data flow after changes
```
Input: PDF / TXT / CSV / URL
         ↓
   server/ingest.py + server/url_loader.py
         ↓
   ChromaDB["prism"] + BM25 index
         ↓
   server/briefing.py (Groq call)
   → summary (5 bullets) + suggested questions (3)
         ↓
   POST /api/upload response includes `briefing` field
         ↓
   Chat: HybridRetriever → RRF → CrossEncoder → Groq answer
   Answer includes inline [1][2] citations
         ↓
   Frontend: MessageBubble renders <sup> citation markers
   clicking jumps to SourceExpander card
```

---

## Features

### Phase 0 — Rebrand (Day 1)

**Files to rename/update:**

| File | Change |
|------|--------|
| `config.yaml` | `collection_name: "finrag"` → `"prism"` |
| `server/ingest.py` | default `collection_name` args + print statements |
| `server/retriever.py` | 3× default `collection_name` args |
| `server/utils.py` | `finrag.log` → `prism.log` |
| `scripts/run_ragas_local.py` | `collection_name="finrag"` |
| `server/chain.py` | `SYSTEM_PROMPT` — remove "FinRAG"/"fintech", replace with domain-agnostic copy |
| `render.yaml` | service name `finrag` → `prism` |
| `docs/api-spec.md` | Render URL |
| `README.md` | Vercel URL, collection name refs, folder name, title |
| `frontend/src/App.jsx` | Header: "FinRAG" → "Prism", subtitle "Fintech Research Agent" → "Document Intelligence" |

**New system prompt (domain-agnostic):**
```
You are Prism, a document intelligence assistant.
Answer questions grounded strictly in the provided context documents.
When web search context is provided, use it alongside document context.
If the exact information is not available but a close value exists, provide it and state the date/source clearly.
Only say you don't know if the topic is completely absent from all context.
Do not hallucinate. Be concise and cite your source by index [1], [2] etc.
```

---

### Phase A — URL Ingestion (Days 2–4)

**New file:** `server/url_loader.py`

```python
async def load_url(url: str) -> list[Document]:
    """Fetch URL, extract text via BeautifulSoup, return LangChain Documents."""
```

- `httpx.get(url, follow_redirects=True, timeout=15)` 
- BeautifulSoup extracts `<p>`, `<h1>`–`<h6>`, `<li>` tags
- Strips scripts, nav, footer, ads
- Returns `Document(page_content=text, metadata={"source": url, "type": "web", "fetched_at": ISO})`
- If status != 200: raise `ValueError(f"Failed to fetch {url}: HTTP {status}")`
- JS-rendered SPAs: returns partial content with warning in metadata

**Modified:** `server/routes/upload.py`
- Form body: add optional `url: str = Form(None)` alongside `file: UploadFile = File(None)`
- If `url` provided: call `load_url(url)` → chunk → ingest → BM25 rebuild
- If `file` provided: existing flow unchanged
- Both can be provided in one request
- Validation: reject if neither file nor url provided

**New deps:** `httpx`, `beautifulsoup4` → add to `requirements.txt`

---

### Phase C — Auto-Briefing on Upload (Days 5–6)

**New file:** `server/briefing.py`

```python
def generate_briefing(doc_name: str, text_sample: str) -> dict:
    """Call Groq with first 3000 chars, return summary + suggested questions."""
    # Returns: {summary: [str x5], suggested_questions: [str x3], doc_name: str}
```

- Uses `llama-3.3-70b-versatile` (same as chat — acceptable, briefing is rare not hot-path)
- Prompt: *"Summarize this document in exactly 5 bullet points. Then list exactly 3 questions a user would most likely ask. Return JSON: {summary: [...], suggested_questions: [...]}."*
- Called in `routes/upload.py` after successful ingest
- `POST /api/upload` response extended:
```json
{
  "filename": "...",
  "chunks_added": 143,
  "total_chunks": 990,
  "status": "ingested",
  "briefing": {
    "doc_name": "policy.pdf",
    "summary": ["...", "...", "...", "...", "..."],
    "suggested_questions": ["...", "...", "..."]
  }
}
```

**Frontend:** `FileUpload.jsx`
- After upload success: render briefing card below upload zone
- Suggested questions rendered as clickable chips
- Clicking chip → auto-fills chat input and submits

---

### Phase D — Citation UI (Days 7–8)

**Backend:** `server/routes/chat.py`
- Number sources before injecting into prompt context: `[1] source1.pdf\n[2] source2.pdf\n...`
- System prompt already instructs `[1][2]` notation (set in Phase 0)
- Response stays unchanged — LLM will now include `[1]` markers in answer text

**Frontend:** `MessageBubble.jsx`
- Regex `\[(\d+)\]` on answer text → replace with `<sup className="citation">` elements
- Citation click → scroll to matching source card in `SourceExpander`
- Source cards numbered to match inline citations

---

### Phase B — Multi-Workspace (Days 9–11)

**Backend:**
- `workspace_id` slug passed as query param: `?workspace=legal-docs`
- Default workspace: `"default"`
- `ingest.py`: `collection_name = workspace_id`
- `bm25_index.py`: `_indexes: dict[str, BM25Index]` singleton dict keyed by workspace_id
- All routes accept `workspace_id` param and pass through to retriever + ingest
- `GET /api/workspaces` → list all ChromaDB collections as workspace list
- `DELETE /api/workspaces/{workspace_id}` → delete collection + BM25 index entry

**Frontend:** `Sidebar.jsx`
- Workspace dropdown above document list
- "New workspace" input → creates on first upload
- Switching workspace reloads document list + clears chat

---

## New Files

| File | Purpose |
|------|---------|
| `server/url_loader.py` | Fetch + parse URL → LangChain Documents |
| `server/briefing.py` | Post-ingest LLM briefing (summary + suggested Qs) |

## Modified Files (summary)

| File | Touches |
|------|---------|
| `config.yaml` | collection name |
| `server/ingest.py` | collection name, add URL path |
| `server/retriever.py` | collection name |
| `server/utils.py` | log filename |
| `server/chain.py` | system prompt |
| `server/routes/upload.py` | URL input, briefing call, response schema |
| `server/routes/chat.py` | numbered source injection |
| `scripts/run_ragas_local.py` | collection name |
| `render.yaml` | service name |
| `requirements.txt` | httpx, beautifulsoup4 |
| `README.md` | full rebrand |
| `docs/api-spec.md` | URLs |
| `frontend/src/App.jsx` | branding |
| `frontend/src/components/FileUpload.jsx` | URL input + briefing card |
| `frontend/src/components/MessageBubble.jsx` | citation superscripts |

---

## Dependencies Added

```
httpx>=0.27.0
beautifulsoup4>=4.12.0
```

No new API keys. All new features use existing Groq key.

---

## Out of Scope (this iteration)

- YouTube transcript ingestion
- Google Docs / Notion connectors
- Audio overview / podcast generation
- Auth / multi-user
- Streaming LLM responses
- JS-rendered SPA scraping (Playwright)

---

## Deployment Notes

- Render free tier: briefing adds ~1 Groq call per upload (not hot path, acceptable)
- URL loader: `httpx` is lightweight, no RAM impact
- BeautifulSoup: ~2MB, no RAM concern
- Multi-workspace: BM25 dict grows with workspaces — acceptable at demo scale

---

## Resume Bullet (post-ship)

> Built Prism, a domain-agnostic document intelligence platform (hybrid BM25+dense retrieval, cross-encoder rerank, URL ingestion, auto-briefing, inline citations) — deployed on Render + Vercel; demo at askprism.vercel.app
