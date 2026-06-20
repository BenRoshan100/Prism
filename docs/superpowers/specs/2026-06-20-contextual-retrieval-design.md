# Contextual Retrieval — Design Spec
**Date:** 2026-06-20  
**Scope:** Eval-only (production upload untouched)  
**Target eval run:** v1.3.0 "Violet"  
**Hypothesis:** context_recall 0.51 → >0.65 via richer chunk embeddings

---

## Problem

Phase 1 (HyDE + Multi-Query) left context_recall at ~0.51. Root cause confirmed: fixed-size 500-char splits produce decontextualized chunks — weak vectors that miss ~half the relevant content.

Example of the problem:
```
"The limit was revised to ₹2 lakh."
```
No document name, no section, no subject. The embedding is weak and generic.

---

## Solution: Contextual Retrieval

At ingest time, for each chunk, call an LLM to generate 2 situating sentences. Prepend to chunk text before embedding. Zero query-time latency impact.

```
BEFORE: "The limit was revised to ₹2 lakh."
AFTER:  "This chunk is from RBI Master Circular 2024 on UPI P2P transaction limits,
         Section 3 covering revised payment caps. The limit was revised to ₹2 lakh."
```

Anthropic benchmark: ~49% reduction in retrieval failures.

---

## Architecture

### Data flow

```
load_documents()
    → chunk_documents()
    → contextualize_chunks()   ← NEW, eval script only
    → embed_and_store()
```

### New function: `contextualize_chunks()`

Location: `server/ingest.py`

**Inputs:**
- `chunks`: list of LangChain Document objects (output of `chunk_documents()`)
- `documents`: list of original page-level Documents (for full doc text reconstruction)
- `model`: Groq model string (default: `llama-3.1-8b-instant`)

**Processing:**
1. Build `doc_text_map: dict[source_name, str]` — concatenate all pages per source
2. For each chunk: call Groq 8B with [doc name + full doc text (truncated 3000 chars) + chunk text]
3. Prepend 2-sentence context to `chunk.page_content`
4. `time.sleep(0.1)` between calls
5. Return modified chunks list

**Fallback:** any Groq failure → log warning → use original chunk text → continue

### Prompt

```
You are helping improve document retrieval. Given a document and a chunk from it,
write 2 concise sentences situating the chunk within the document.

Document name: {source}
Full document text: {full_doc_text[:3000]}

Chunk to situate:
{chunk_text}

Write only the 2 situating sentences. No preamble.
```

### Eval script changes (`scripts/run_eval_versioned.py`)

New CLI flag: `--contextual` (boolean, default: false)

When `--contextual` is set:
1. Use collection name `eval_ctx` (isolated from all production workspaces)
2. Clear `eval_ctx` collection before ingest
3. Run `contextualize_chunks()` between chunking and embedding
4. Run 50 eval pairs against `eval_ctx`
5. Write versioned JSON as normal

Production `POST /api/upload` is **not changed**.

---

## Config

Addition to `config.yaml`:
```yaml
contextual_retrieval:
  enabled: false
  model: "llama-3.1-8b-instant"
```

`enabled` flag is for future production use. Eval script uses `--contextual` CLI flag directly.

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Groq call fails for a chunk | Log warning, use original chunk text, continue |
| Full doc text > 3000 chars | Truncate to 3000 chars |
| 429 rate limit | `time.sleep(2)` + retry once, then fallback |
| Empty chunk text | Skip context generation, keep chunk as-is |
| Re-run with `--contextual` | `eval_ctx` cleared before each run — idempotent |

---

## Files Changed

| File | Change |
|------|--------|
| `server/ingest.py` | Add `contextualize_chunks()` function |
| `config.yaml` | Add `contextual_retrieval` section |
| `scripts/run_eval_versioned.py` | Add `--contextual` flag + `eval_ctx` collection logic |

No frontend changes. No production route changes.

---

## Success Criteria

Run `python scripts/run_eval_versioned.py --version v1.3.0 --tag "Violet" --n 50 --contextual`

| Metric | Baseline (v1.0.0) | Target |
|--------|-------------------|--------|
| context_recall | 0.51 | >0.65 |
| answer_correctness | 0.82 | ≥0.82 (no regression) |
| P@5 | 0.89 | ≥0.85 (slight drop acceptable — wider context, some noise) |
| latency p50 | 2029ms | ~2029ms (zero query-time impact) |

If recall does not reach 0.65, next step is semantic chunking (Phase 2b).
