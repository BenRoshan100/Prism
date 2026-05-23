# API Specification — FinRAG v2

## Base URL
- Local: `http://localhost:8000`
- Production: `https://finrag-v2.onrender.com` (set after deploy)

---

## Chat

### POST /api/chat
**Purpose:** Submit a question; returns answer with sources and eval scores.

**Request:**
```json
{ "question": "What was UPI transaction volume in FY24?" }
```
**Response:**
```json
{
  "answer": "India processed over 100 billion UPI transactions in FY2024...",
  "sources": [
    {
      "content": "chunk text...",
      "source": "npci_upi_report_2024.pdf",
      "page": 12,
      "similarity_score": 0.87,
      "bm25_score": 3.42,
      "rrf_score": 0.021,
      "rerank_score": 4.91
    }
  ],
  "faithfulness": { "score": 4, "reason": "Answer well-grounded in context." },
  "retrieval_method": "hybrid+rerank"
}
```

### DELETE /api/chat/memory
**Purpose:** Clear conversation history (new conversation).
**Response:** `{ "status": "cleared" }`

---

## Upload

### POST /api/upload
**Purpose:** Upload a document and re-ingest into the corpus.
**Content-Type:** `multipart/form-data` | Field: `file`
**Allowed types:** `.pdf`, `.txt`, `.csv` | Max size: 20MB

**Response:**
```json
{
  "filename": "new_document.pdf",
  "chunks_added": 143,
  "total_chunks": 990,
  "status": "ingested"
}
```
**Error:** 422 if file type unsupported.

---

## Eval

### GET /api/eval/session
**Purpose:** Get per-turn faithfulness log for current session.
**Response:**
```json
[
  {
    "query": "...",
    "answer": "...",
    "faithfulness_score": 4,
    "reason": "..."
  }
]
```

### POST /api/eval/precision
**Purpose:** Run batch Precision@K against ground truth pairs.
**Response:**
```json
{
  "mean_precision_at_k": 0.74,
  "per_query_results": [...]
}
```

### POST /api/eval/ragas
**Purpose:** Run RAGAS evaluation on last N session QA pairs.
**Request:** `{ "n_pairs": 10 }`
**Response:**
```json
{
  "faithfulness": 0.87,
  "answer_relevancy": 0.91,
  "context_precision": 0.74,
  "context_recall": 0.68,
  "per_query": [...]
}
```

---

## Health

### GET /health
**Response:** `{ "status": "ok", "version": "2.0.0" }`
