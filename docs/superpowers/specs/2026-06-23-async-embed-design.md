# Async Embed Upload — Design Spec
Date: 2026-06-23

## Problem
`embed_and_store()` in `POST /api/upload` blocks the HTTP response ~150s (30 chunks × ~5s/chunk via Euron API). User sees spinner, cannot query, cannot cancel.

## Goal
Upload returns in <1s. Frontend shows stage labels. User can query corpus immediately after "Ready".

## Architecture

### Sync path (before 202 response)
1. Save files to `data/raw/`
2. `load_documents_from_paths()` — parse, validate (raises 422 for encrypted PDFs)
3. `chunk_documents()` — split into chunks
4. Generate `job_id` (uuid4)
5. Register job in `app.state.upload_jobs[job_id] = {status: "embedding", ...}`
6. Schedule `_embed_and_contextualize_bg()` as BackgroundTask
7. Return `202 {job_id, filename, total_chunks}`

### Background path
```
embed_and_store(chunks, workspace)       → status: "embedding"
_rebuild_chain(app, workspace)
generate_briefing(...)                   → stored in job dict
contextualize_chunks_async(...)          → status: "contextualizing" (if enabled)
_rebuild_chain(app, workspace)           → after contextual
status: "ready"                          → briefing attached
```
On any unhandled exception → `status: "failed"`, `error: str(e)`

### Job state shape
```python
{
    "status": "embedding" | "contextualizing" | "ready" | "failed",
    "message": str,        # human-readable stage label
    "briefing": str | None,
    "error": str | None,
    "workspace": str,
}
```

## API changes

### POST /api/upload (modified)
**Response:** `202 {job_id, uploaded: [filename], total_chunks: N}`
(Previously: `200 {uploaded, documents, briefing}`)

### GET /api/upload/status/{job_id} (new)
**Response:** `{status, message, briefing?, error?}`
**404** if job_id not found.

## Frontend changes

### api.js
Add `getUploadStatus(jobId)` — `GET /api/upload/status/{jobId}`.

### FileUpload.jsx
After POST returns 202:
- Store `jobId` in state
- Poll `getUploadStatus(jobId)` every 2s via `setInterval`
- Display `message` as stage label below spinner
- On `status === "ready"`: call `onUploadComplete(documents)`, `onBriefing(briefing)`, clear interval
- On `status === "failed"`: show error, clear interval

Stage labels shown to user:
- `"Embedding N chunks..."` 
- `"Adding context to N chunks..."`
- `"Ready"` (triggers completion callbacks)

## Out of scope
- URL upload (keep blocking — faster, no 30-chunk sequential embed)
- Job cleanup / TTL (ephemeral dict, demo scale)
- Per-chunk progress bar
- SSE / WebSocket

## Files changed
| File | Change |
|------|--------|
| `server/main.py` | Init `app.state.upload_jobs = {}` in lifespan |
| `server/routes/upload.py` | Modify `POST /upload`; add `_embed_and_contextualize_bg()`; add `GET /upload/status/{job_id}` |
| `frontend/src/api.js` | Add `getUploadStatus(jobId)` |
| `frontend/src/components/FileUpload.jsx` | Poll status, show stage labels, fire callbacks on ready |
