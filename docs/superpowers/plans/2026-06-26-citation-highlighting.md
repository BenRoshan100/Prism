# Citation Highlighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make inline `[N]` citation markers in LLM answers clickable — clicking opens a popover showing the full source chunk (content, filename, page, scores) positioned relative to the clicked marker.

**Architecture:** Pure React state — no new npm deps. `CitedText` (already exists in `MessageBubble.jsx`) parses `[N]` markers; clicking passes the element's `DOMRect` to `handleCitationClick` which sets `openCitation` state; `CitationPopover` positions itself using that rect. Backend adds a `GET /api/files/{filename}` route so PDF sources can link to their file at the right page.

**Tech Stack:** React 19, Tailwind CSS v4, FastAPI, Python 3.11+

## Global Constraints

- Zero new npm dependencies
- Tailwind CSS v4 utility classes only (no arbitrary CSS files)
- Python 3.11+ type hints on all new functions
- `VITE_API_URL` env var for backend base URL (already set in Vercel)
- PDFs saved at `data/raw/{filename}` on backend — path traversal must be blocked
- Page numbers in source metadata are 0-indexed; browser PDF viewer uses 1-indexed (`page + 1`)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `server/main.py` | Modify | Add `GET /api/files/{filename}` route |
| `tests/test_file_serving.py` | Create | Tests for file serving route |
| `frontend/src/components/CitationPopover.jsx` | Create | Popover UI + viewport-aware positioning |
| `frontend/src/components/SourceExpander.jsx` | Modify | Remove 200-char content truncation |
| `frontend/src/components/MessageBubble.jsx` | Modify | Wire `openCitation` state + render `CitationPopover` |

---

## Task 1: Backend file serving route

**Files:**
- Modify: `server/main.py`
- Create: `tests/test_file_serving.py`

**Interfaces:**
- Produces: `GET /api/files/{filename}` → `FileResponse` for files in `data/raw/`; 404 if missing; 400 if path traversal detected

- [ ] **Step 1: Write failing tests**

Create `tests/test_file_serving.py`:

```python
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


def test_serve_existing_file(tmp_path, monkeypatch):
    """Returns 200 + file content for a file that exists."""
    fake_raw = tmp_path / "raw"
    fake_raw.mkdir()
    pdf = fake_raw / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr("server.main.UPLOAD_DIR", fake_raw)

    from server.main import app
    client = TestClient(app)
    resp = client.get("/api/files/report.pdf")
    assert resp.status_code == 200
    assert resp.content == b"%PDF-1.4 fake"


def test_serve_missing_file(tmp_path, monkeypatch):
    """Returns 404 for a filename that doesn't exist."""
    fake_raw = tmp_path / "raw"
    fake_raw.mkdir()

    monkeypatch.setattr("server.main.UPLOAD_DIR", fake_raw)

    from server.main import app
    client = TestClient(app)
    resp = client.get("/api/files/does_not_exist.pdf")
    assert resp.status_code == 404


def test_serve_blocks_path_traversal(tmp_path, monkeypatch):
    """Returns 400 for path traversal attempts."""
    fake_raw = tmp_path / "raw"
    fake_raw.mkdir()

    monkeypatch.setattr("server.main.UPLOAD_DIR", fake_raw)

    from server.main import app
    client = TestClient(app)
    resp = client.get("/api/files/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd "D:\ACADEMIC\GenAI Projects\Prism"
python -m pytest tests/test_file_serving.py -v
```

Expected: `ImportError` or `404` on the route (route doesn't exist yet).

- [ ] **Step 3: Add `UPLOAD_DIR` module-level constant and file serving route to `server/main.py`**

Add after the existing imports and before `configure_logging()`:

```python
from fastapi import HTTPException
from fastapi.responses import FileResponse
```

Add `UPLOAD_DIR` as a module-level constant (so tests can monkeypatch it) right after the imports block:

```python
UPLOAD_DIR = Path("data/raw")
```

Add this route after the `/health` endpoint:

```python
@app.get("/api/files/{filename}")
async def serve_file(filename: str):
    """Serve uploaded files from data/raw/ for citation PDF links."""
    upload_root = UPLOAD_DIR.resolve()
    target = (UPLOAD_DIR / filename).resolve()
    if not str(target).startswith(str(upload_root)):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python -m pytest tests/test_file_serving.py -v
```

Expected output:
```
tests/test_file_serving.py::test_serve_existing_file PASSED
tests/test_file_serving.py::test_serve_missing_file PASSED
tests/test_file_serving.py::test_serve_blocks_path_traversal PASSED
3 passed
```

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
python -m pytest tests/ -v
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add server/main.py tests/test_file_serving.py
git commit -m "feat: add GET /api/files/{filename} route for citation PDF links"
```

---

## Task 2: Remove SourceExpander content truncation

**Files:**
- Modify: `frontend/src/components/SourceExpander.jsx:81`

**Interfaces:**
- Consumes: `src.content` (full string, no length limit)
- Produces: same component, renders full content

- [ ] **Step 1: Edit `SourceExpander.jsx` — remove truncation**

Find this block (around line 80):
```jsx
<p className="text-xs text-gray-500 leading-relaxed">
  {src.content.length > 200
    ? src.content.slice(0, 200) + "..."
    : src.content}
</p>
```

Replace with:
```jsx
<p className="text-xs text-gray-500 leading-relaxed">
  {src.content}
</p>
```

- [ ] **Step 2: Manual verify**

Start the dev server and send a query. Open the "Show sources" expander below an answer. Confirm chunks show full text (not cut off at ~200 chars).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SourceExpander.jsx
git commit -m "fix: show full chunk content in SourceExpander (remove 200-char truncation)"
```

---

## Task 3: CitationPopover component

**Files:**
- Create: `frontend/src/components/CitationPopover.jsx`

**Interfaces:**
- Consumes:
  - `source: { content, source, source_type, page, url, title, rerank_score, similarity_score }` — one entry from the `sources` array in the SSE `done` event
  - `anchorRect: DOMRect` — bounding rect of the clicked `[N]` button, captured at click time
  - `onClose: () => void` — called when user clicks outside
- Produces: exported default `CitationPopover` component

- [ ] **Step 1: Create `CitationPopover.jsx`**

```jsx
import { useEffect, useRef } from "react";

export default function CitationPopover({ source, anchorRect, onClose }) {
  const popoverRef = useRef(null);

  useEffect(() => {
    function handleMouseDown(e) {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, [onClose]);

  if (!source || !anchorRect) return null;

  const openAbove = anchorRect.top > window.innerHeight * 0.6;
  const left = Math.min(anchorRect.left, window.innerWidth - 336); // 320px + 16px buffer

  const style = {
    position: "fixed",
    left: `${Math.max(8, left)}px`,
    width: "320px",
    zIndex: 50,
    ...(openAbove
      ? { bottom: `${window.innerHeight - anchorRect.top + 8}px` }
      : { top: `${anchorRect.bottom + 8}px` }),
  };

  const isWeb = source.source_type === "web";
  const isPdf = !isWeb && typeof source.source === "string" &&
    source.source.toLowerCase().endsWith(".pdf");
  const pageNum = source.page != null ? source.page + 1 : null; // 0-indexed → 1-indexed
  const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

  return (
    <div
      ref={popoverRef}
      style={style}
      className="bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
              isWeb
                ? "bg-emerald-100 text-emerald-700"
                : "bg-indigo-100 text-indigo-700"
            }`}
          >
            {isWeb ? "web" : isPdf ? "pdf" : "file"}
          </span>
          <span className="text-xs font-medium text-gray-700 truncate">
            {isWeb ? source.title || source.url : source.source}
          </span>
        </div>
        {pageNum != null && (
          <span className="text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded shrink-0 ml-2">
            Page {pageNum}
          </span>
        )}
      </div>

      {/* Body */}
      <div className="px-3 py-2.5 max-h-48 overflow-y-auto">
        <p className="text-xs text-gray-600 leading-relaxed">{source.content}</p>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-gray-100 bg-gray-50">
        <div className="flex gap-2">
          {source.rerank_score != null && (
            <span className="text-[10px] text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded font-medium">
              rerank: {Number(source.rerank_score).toFixed(2)}
            </span>
          )}
        </div>
        {isWeb && source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-emerald-600 hover:text-emerald-800 font-medium"
          >
            Open source →
          </a>
        )}
        {isPdf && pageNum != null && (
          <a
            href={`${API_BASE}/api/files/${encodeURIComponent(source.source)}#page=${pageNum}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Open page {pageNum} →
          </a>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Manual smoke-check (import only)**

In `frontend/src/components/MessageBubble.jsx`, temporarily add:
```jsx
import CitationPopover from "./CitationPopover";
```
Run `npm run dev` in the `frontend/` directory. Confirm no import errors in console. Remove the import — it will be wired properly in Task 4.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CitationPopover.jsx
git commit -m "feat: add CitationPopover component for citation highlighting"
```

---

## Task 4: Wire CitationPopover into MessageBubble

**Files:**
- Modify: `frontend/src/components/MessageBubble.jsx`

**Interfaces:**
- Consumes:
  - `CitationPopover` from `./CitationPopover`
  - `useState` from `react`
  - `message.sources: array` — existing prop, already present
- `CitedText`'s `onCitationClick` prop signature changes: `(idx: number, el: HTMLElement) => void`

**Note:** `CitedText` already exists in `MessageBubble.jsx` at line 30. It renders `[N]` as `<sup>` with `onClick={() => onCitationClick(idx)}`. We change the click to pass `e.currentTarget` as the second argument, then update `handleCitationClick` to capture the `DOMRect`.

- [ ] **Step 1: Update `CitedText` to pass the DOM element on click**

Find the existing `CitedText` function (line 30–54). Change the `onClick` handler on `<sup>` from:

```jsx
onClick={() => onCitationClick(idx)}
```

to:

```jsx
onClick={(e) => onCitationClick(idx, e.currentTarget)}
```

Full updated `CitedText` function:

```jsx
function CitedText({ text, onCitationClick }) {
  if (!text) return null;
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const idx = parseInt(match[1], 10);
          return (
            <sup
              key={i}
              onClick={(e) => onCitationClick(idx, e.currentTarget)}
              className="ml-0.5 text-indigo-500 font-semibold cursor-pointer hover:text-indigo-700 text-xs select-none"
              title={`View source [${idx}]`}
            >
              [{idx}]
            </sup>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
```

- [ ] **Step 2: Add `useState` import and `CitationPopover` import to `MessageBubble.jsx`**

Current first line:
```jsx
import SourceExpander from "./SourceExpander";
```

Replace with:
```jsx
import { useState } from "react";
import CitationPopover from "./CitationPopover";
import SourceExpander from "./SourceExpander";
```

- [ ] **Step 3: Replace `handleCitationClick` and add `openCitation` state in `MessageBubble`**

Find the existing `MessageBubble` component (line 56–102). Replace the entire function body with:

```jsx
export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  const [openCitation, setOpenCitation] = useState(null); // { idx, rect } | null

  function handleCitationClick(idx, el) {
    if (openCitation?.idx === idx) {
      setOpenCitation(null);
    } else {
      setOpenCitation({ idx, rect: el.getBoundingClientRect() });
    }
  }

  const activeSrc =
    openCitation && message.sources
      ? message.sources.find((s) => s.citation_index === openCitation.idx) ||
        message.sources[openCitation.idx - 1]
      : null;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-2xl px-5 py-3.5 ${
          isUser
            ? "bg-indigo-600 text-white"
            : "bg-white text-gray-800 shadow-sm"
        }`}
      >
        <p className="text-sm whitespace-pre-wrap leading-relaxed">
          {isUser ? (
            message.content
          ) : message.loading && !message.content ? (
            <span className="inline-flex items-center gap-1 text-indigo-400">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" />
            </span>
          ) : (
            <>
              <CitedText text={message.content} onCitationClick={handleCitationClick} />
              {message.loading && (
                <span className="inline-block w-0.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-middle" />
              )}
            </>
          )}
        </p>

        {!isUser && !message.loading && message.sources && (
          <WebSourcesList sources={message.sources} />
        )}

        {!isUser && !message.loading && message.sources && (
          <SourceExpander sources={message.sources} />
        )}
      </div>

      {openCitation && activeSrc && (
        <CitationPopover
          source={activeSrc}
          anchorRect={openCitation.rect}
          onClose={() => setOpenCitation(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Manual test — basic popover**

```bash
cd frontend && npm run dev
```

1. Upload a PDF document.
2. Ask a question that returns an answer with `[1]`, `[2]` markers.
3. Click `[1]` superscript → popover appears near the marker with source name, page, full content.
4. Click `[1]` again → popover closes (toggle).
5. Click `[2]` while `[1]` is open → popover switches to source 2.
6. Click anywhere outside popover → popover closes.

- [ ] **Step 5: Manual test — viewport edge cases**

7. Scroll to bottom of a long chat → ask a question → click a citation at the bottom of the viewport → confirm popover opens **above** the marker (not off-screen below).
8. Ask a question when chat is near the top → confirm popover opens **below** the marker.

- [ ] **Step 6: Manual test — source type variants**

9. Upload a TXT file → ask a question → click citation → confirm: no "Open page" link, shows "file" badge.
10. Ask a question that triggers web search → click a web-sourced citation → confirm "Open source →" link appears with the URL.
11. Upload a PDF → click citation for a PDF source → confirm "Open page N →" link opens the PDF in the browser at the correct page.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/MessageBubble.jsx
git commit -m "feat: wire citation popover — click [N] in answer to view source chunk"
```

---

## Self-Review

**Spec coverage:**
- ✅ `[N]` markers rendered as clickable — Task 4 Step 1
- ✅ Click opens popover — Task 4 Step 3
- ✅ Popover positions above/below based on viewport — Task 3 Step 1 (`openAbove` logic)
- ✅ Full chunk content, no truncation — Task 2
- ✅ Source type handling (PDF/web/file) — Task 3 Step 1
- ✅ "Open page N →" for PDF with `page+1` correction — Task 3 Step 1
- ✅ "Open source →" for web — Task 3 Step 1
- ✅ Horizontal clamp (`Math.max(8, left)`) — Task 3 Step 1
- ✅ Click-away closes popover — Task 3 Step 1 (`useEffect` mousedown)
- ✅ Toggle same citation closes — Task 4 Step 3 (`openCitation?.idx === idx`)
- ✅ Missing source guard (`activeSrc` null check before render) — Task 4 Step 3
- ✅ Backend path traversal blocked — Task 1 Step 3
- ✅ Backend 404 for missing file — Task 1 Step 3

**Type consistency:**
- `onCitationClick(idx, el)` defined in Task 4 Step 3, consumed in Task 4 Step 1 — ✅ consistent
- `anchorRect: DOMRect` defined in Task 3, passed from `el.getBoundingClientRect()` in Task 4 — ✅ consistent
- `source` object shape: `{ content, source, source_type, page, url, title, rerank_score }` — matches what `stream_query_with_web` yields in `chain.py` — ✅ consistent

**No placeholders:** All steps have complete code. ✅
