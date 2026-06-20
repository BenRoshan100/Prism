# Contextual Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `contextualize_chunks()` to the ingest pipeline and a `--contextual` flag to the eval script so v1.3.0 "Violet" can be run with LLM-prefixed chunk embeddings.

**Architecture:** New function `contextualize_chunks(chunks, documents)` in `server/ingest.py` calls Groq 8B per chunk to generate a 2-sentence context prefix, prepends it to `chunk.page_content` before embedding. The eval script gains `--contextual` which clears the dedicated `eval_ctx` ChromaDB collection, runs contextualized ingest into it, then evaluates against it. Production upload routes are untouched.

**Tech Stack:** Python 3.11, LangChain, langchain-groq, ChromaDB, pytest

## Global Constraints

- Model for context generation: `llama-3.1-8b-instant` (500k TPD — do not use 70B here)
- Sleep between Groq calls: `0.1s` (rate limit safety)
- On any Groq failure: log warning, keep original chunk text, continue — never raise
- Full doc text passed to prompt: truncated to 3000 chars
- Eval collection name: `eval_ctx` (hardcoded — isolated from all production workspaces)
- ChromaDB persist directory: `./chroma_db` (matches existing code)
- Production routes (`server/routes/upload.py`, `server/routes/chat.py`): do not touch

---

## File Map

| File | Change |
|------|--------|
| `server/ingest.py` | Add `contextualize_chunks()` function |
| `config.yaml` | Add `contextual_retrieval` section |
| `tests/test_ingest.py` | Add 3 tests for `contextualize_chunks` |
| `scripts/run_eval_versioned.py` | Add `--contextual` + `--data-dir` args, `_ingest_contextual()`, update `run_data` config |

---

## Task 1: `contextualize_chunks()` + config

**Files:**
- Modify: `server/ingest.py`
- Modify: `config.yaml`
- Modify: `tests/test_ingest.py`

**Interfaces:**
- Produces: `contextualize_chunks(chunks: list, documents: list, model: str = "llama-3.1-8b-instant", sleep_between_calls: float = 0.1) -> list`

- [ ] **Step 1: Write 3 failing tests in `tests/test_ingest.py`**

Add these imports at the top of the file (after existing imports):
```python
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
```

Add these 3 test functions at the bottom of `tests/test_ingest.py`:

```python
def test_contextualize_chunks_prepends_context():
    """Context prefix must be prepended to chunk.page_content."""
    chunks = [Document(
        page_content="The limit was revised to ₹2 lakh.",
        metadata={"source": "rbi.pdf", "page": 1}
    )]
    documents = [Document(
        page_content="Full RBI document text about UPI limits.",
        metadata={"source": "rbi.pdf"}
    )]

    mock_response = MagicMock()
    mock_response.content = "RBI Circular 2024 on UPI limits. This section covers payment caps."

    with patch("server.ingest.ChatGroq") as MockGroq:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        MockGroq.return_value = mock_llm

        result = contextualize_chunks(chunks, documents, sleep_between_calls=0)

    assert result[0].page_content.startswith("RBI Circular 2024")
    assert "The limit was revised to ₹2 lakh." in result[0].page_content


def test_contextualize_chunks_fallback_on_llm_failure():
    """On Groq failure, original chunk text must be preserved unchanged."""
    original_text = "Original chunk text."
    chunks = [Document(page_content=original_text, metadata={"source": "doc.pdf", "page": 1})]
    documents = [Document(page_content="Full document.", metadata={"source": "doc.pdf"})]

    with patch("server.ingest.ChatGroq") as MockGroq:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Groq timeout")
        MockGroq.return_value = mock_llm

        result = contextualize_chunks(chunks, documents, sleep_between_calls=0)

    assert result[0].page_content == original_text


def test_contextualize_chunks_skips_empty_content():
    """Empty chunks must not trigger a Groq call."""
    chunks = [
        Document(page_content="", metadata={"source": "doc.pdf"}),
        Document(page_content="Real content.", metadata={"source": "doc.pdf"}),
    ]
    documents = [Document(page_content="Full doc.", metadata={"source": "doc.pdf"})]

    mock_response = MagicMock()
    mock_response.content = "Context sentence 1. Context sentence 2."

    with patch("server.ingest.ChatGroq") as MockGroq:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        MockGroq.return_value = mock_llm

        result = contextualize_chunks(chunks, documents, sleep_between_calls=0)

    assert result[0].page_content == ""
    assert mock_llm.invoke.call_count == 1  # only called for non-empty chunk
```

Also update the import line at the top of `tests/test_ingest.py` from:
```python
from server.ingest import load_documents, chunk_documents, embed_and_store
```
to:
```python
from server.ingest import load_documents, chunk_documents, embed_and_store, contextualize_chunks
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_ingest.py::test_contextualize_chunks_prepends_context tests/test_ingest.py::test_contextualize_chunks_fallback_on_llm_failure tests/test_ingest.py::test_contextualize_chunks_skips_empty_content -v
```

Expected: `ImportError: cannot import name 'contextualize_chunks'`

- [ ] **Step 3: Implement `contextualize_chunks()` in `server/ingest.py`**

Add this import at the top of `server/ingest.py` (after existing imports):
```python
import time
```

Add this function after `chunk_documents()` and before `_chunk_id()`:

```python
def contextualize_chunks(
    chunks: list,
    documents: list,
    model: str = "llama-3.1-8b-instant",
    sleep_between_calls: float = 0.1,
) -> list:
    """Prepend 2-sentence LLM context to each chunk before embedding.

    Falls back to original chunk text on any Groq failure.
    """
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage

    doc_text_map: dict[str, str] = {}
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        doc_text_map[source] = doc_text_map.get(source, "") + " " + doc.page_content

    llm = ChatGroq(
        model=model,
        api_key=os.environ.get("GROQ_API_KEY", ""),
        temperature=0.1,
        max_tokens=150,
    )

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        if not chunk.page_content.strip():
            continue

        source = chunk.metadata.get("source", "unknown")
        full_doc_text = doc_text_map.get(source, "")[:3000]

        prompt = (
            "You are helping improve document retrieval. Given a document and a chunk "
            "from it, write 2 concise sentences situating the chunk within the document.\n\n"
            f"Document name: {source}\n"
            f"Full document text: {full_doc_text}\n\n"
            f"Chunk to situate:\n{chunk.page_content}\n\n"
            "Write only the 2 situating sentences. No preamble."
        )

        for attempt in range(2):
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                context_prefix = response.content.strip()
                chunk.page_content = f"{context_prefix} {chunk.page_content}"
                logger.info(
                    "Contextualized chunk %d/%d: %s page %s",
                    i + 1, total, source, chunk.metadata.get("page", "?"),
                )
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(
                        "Groq call failed for chunk %d/%d, retrying in 2s: %s",
                        i + 1, total, e,
                    )
                    time.sleep(2)
                else:
                    logger.warning(
                        "Groq call failed for chunk %d/%d (attempt 2), using original text: %s",
                        i + 1, total, e,
                    )

        time.sleep(sleep_between_calls)

    return chunks
```

- [ ] **Step 4: Add `contextual_retrieval` section to `config.yaml`**

Add at the end of `config.yaml`:
```yaml
contextual_retrieval:
  enabled: false
  model: "llama-3.1-8b-instant"
```

- [ ] **Step 5: Run tests to confirm they pass**

```
pytest tests/test_ingest.py::test_contextualize_chunks_prepends_context tests/test_ingest.py::test_contextualize_chunks_fallback_on_llm_failure tests/test_ingest.py::test_contextualize_chunks_skips_empty_content -v
```

Expected: `3 passed`

- [ ] **Step 6: Run full test suite to confirm no regressions**

```
pytest tests/ -v --ignore=tests/test_retriever.py
```

(`test_retriever.py` requires ChromaDB to be populated — skip for now)

Expected: all existing tests pass

- [ ] **Step 7: Commit**

```bash
git add server/ingest.py config.yaml tests/test_ingest.py
git commit -m "feat: add contextualize_chunks() for LLM-prefixed chunk embeddings"
```

---

## Task 2: `--contextual` flag in eval script

**Files:**
- Modify: `scripts/run_eval_versioned.py`

**Interfaces:**
- Consumes: `contextualize_chunks(chunks, documents, model, sleep_between_calls)` from `server.ingest`
- Consumes: `load_documents(data_dir)`, `chunk_documents(documents)`, `embed_and_store(chunks, collection_name)` from `server.ingest`

- [ ] **Step 1: Add `_ingest_contextual()` helper to `scripts/run_eval_versioned.py`**

Add this function after `_compute_percentile()` and before `main()`:

```python
def _ingest_contextual(data_dir: str, ctx_model: str) -> None:
    """Clear eval_ctx ChromaDB collection and re-ingest with LLM context prefixes."""
    import chromadb
    from server.ingest import load_documents, chunk_documents, contextualize_chunks, embed_and_store

    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection("eval_ctx")
        print("  Cleared existing eval_ctx collection.")
    except Exception:
        pass

    documents = load_documents(data_dir)
    chunks = chunk_documents(documents)
    print(f"  Contextualizing {len(chunks)} chunks with {ctx_model}...")
    chunks = contextualize_chunks(chunks, documents, model=ctx_model, sleep_between_calls=0.1)
    embed_and_store(chunks, collection_name="eval_ctx")
    print(f"  Done. eval_ctx collection ready ({len(chunks)} chunks).")
```

- [ ] **Step 2: Add CLI args and wire `--contextual` in `main()`**

In `main()`, add two new args after the existing `--judge-model` arg:

```python
parser.add_argument("--contextual", action="store_true",
                    help="Ingest corpus with LLM context prefixes into eval_ctx before eval")
parser.add_argument("--data-dir", default="data/raw",
                    help="Source documents dir for --contextual ingest (default: data/raw)")
```

Replace the existing line:
```python
retriever = _build_retriever(config, workspace_id=args.workspace)
```

With:
```python
workspace_id = "eval_ctx" if args.contextual else args.workspace

if args.contextual:
    ctx_cfg = config.get("contextual_retrieval", {})
    ctx_model = ctx_cfg.get("model", args.judge_model)
    print(f"Contextual retrieval: ingesting {args.data_dir} → eval_ctx ({ctx_model})...")
    _ingest_contextual(args.data_dir, ctx_model=ctx_model)

retriever = _build_retriever(config, workspace_id=workspace_id)
```

- [ ] **Step 3: Update `run_data["config"]` to log contextual flag**

In `main()`, find the `run_data` dict. Replace the `"config"` block:

```python
"config": {
    "hyde_enabled": retrieval_cfg.get("hyde_enabled", False),
    "retrieve_k": retrieval_cfg.get("retrieve_k", 10),
    "rerank_k": retrieval_cfg.get("rerank_k", 5),
    "llm": config.get("llm", {}).get("model", "unknown"),
    "judge_model": args.judge_model,
    "workspace": args.workspace,
},
```

With:
```python
"config": {
    "hyde_enabled": retrieval_cfg.get("hyde_enabled", False),
    "multi_query_enabled": retrieval_cfg.get("multi_query_enabled", False),
    "contextual_retrieval": args.contextual,
    "retrieve_k": retrieval_cfg.get("retrieve_k", 10),
    "rerank_k": retrieval_cfg.get("rerank_k", 5),
    "llm": config.get("llm", {}).get("model", "unknown"),
    "judge_model": args.judge_model,
    "workspace": workspace_id,
},
```

- [ ] **Step 4: Smoke test `--contextual` flag parses correctly**

```
python scripts/run_eval_versioned.py --help
```

Expected output includes:
```
--contextual    Ingest corpus with LLM context prefixes into eval_ctx before eval
--data-dir      Source documents dir for --contextual ingest (default: data/raw)
```

- [ ] **Step 5: Commit**

```bash
git add scripts/run_eval_versioned.py
git commit -m "feat: add --contextual flag to eval script for contextual retrieval eval run"
```

---

## Task 3: Run eval v1.3.0

- [ ] **Step 1: Verify `.env` has both keys**

```
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('GROQ:', bool(os.getenv('GROQ_API_KEY'))); print('EURON:', bool(os.getenv('EURON_API_KEY')))"
```

Expected:
```
GROQ: True
EURON: True
```

- [ ] **Step 2: Run contextual eval (50 pairs, ~45–60 min total)**

```
python scripts/run_eval_versioned.py --version v1.3.0 --tag "Violet" --n 50 --contextual
```

Watch for:
- `Contextualizing N chunks with llama-3.1-8b-instant...` — confirms contextualization running
- Per-chunk log lines: `Contextualized chunk X/N: rbi.pdf page Y`
- Per-query lines: `correctness=X.XX p@5=X.XX latency=XXXXms`
- Final metrics block

- [ ] **Step 3: Commit eval results**

```bash
git add eval-dashboard/public/data/runs/v1.3.0_*.json eval-dashboard/public/data/index.json
git commit -m "eval: v1.3.0 Violet — contextual retrieval results"
```

- [ ] **Step 4: Update `docs/evolution.md` with Stage 10 results**

Add a new `## Stage 10 — Contextual Retrieval` section with:
- What was wrong (recall=0.51, chunking quality root cause)
- What was built (contextualize_chunks, --contextual flag)
- Actual v1.3.0 metric results
- Next step decision based on whether recall target (>0.65) was met

Update `Current State Snapshot` block with v1.3.0 results.
