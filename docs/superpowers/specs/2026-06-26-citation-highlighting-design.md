# Citation Highlighting — Design Spec
**Date:** 2026-06-26
**Status:** Approved

---

## Problem

Sources are listed below each answer as truncated text snippets. Users cannot see which exact passage in the answer corresponds to which source. The LLM already outputs `[1]`, `[2]` inline citations but they are rendered as plain text — unclickable, non-interactive.

---

## Goal

Make inline citation markers `[N]` in the answer text clickable. Clicking opens a popover showing the full source chunk — content, filename/URL, page number, scores. Works for all source types: PDF, URL, TXT, CSV.

---

## Approach

Pure React + Tailwind. Zero new npm dependencies. Four file changes.

---

## Architecture

### 1. Answer text parsing (`MessageBubble.jsx`)

Split `msg.text` on regex `/(\[\d+\])/g` → alternating text segments and citation tokens.

Each `[N]` token renders as:
```jsx
<button
  className="inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold
             bg-indigo-100 text-indigo-700 rounded-full mx-0.5 hover:bg-indigo-200
             transition-colors cursor-pointer align-super"
  onClick={() => setOpenCitation(N === openCitation ? null : N)}
  ref={citationRefs[N]}
>
  {N}
</button>
```

State: `const [openCitation, setOpenCitation] = useState(null)` — tracks which `N` is open (or null).

Click-away: `useEffect` adds `mousedown` listener on `document` → closes if click outside popover and outside all citation buttons.

One `CitationPopover` rendered at a time — conditionally when `openCitation !== null` and `sources[openCitation - 1]` exists.

---

### 2. CitationPopover component (`CitationPopover.jsx` — new)

**Props:** `source` (chunk object), `anchorRef` (ref to `[N]` button), `onClose`

**Positioning:**
- On mount: `anchorRef.current.getBoundingClientRect()` → get button position
- If button `top > 60% of window.innerHeight` → open above (transform: `translateY(-100%)` minus gap)
- Otherwise → open below (default)
- Fixed width: `320px`, max-height body: `192px` (scrollable)
- Z-index: `50` (above message bubbles)

**Content:**

```
┌─────────────────────────────────────┐
│ [pdf] npci_report.pdf    Page 12    │  ← header
├─────────────────────────────────────┤
│ Full chunk content text here,       │  ← body (scrollable)
│ no truncation. All text shown.      │
│ ...                                 │
├─────────────────────────────────────┤
│ rerank: 4.91        Open page 12 → │  ← footer
└─────────────────────────────────────┘
```

**Source type handling:**

| Source type | Header | Footer action |
|-------------|--------|---------------|
| PDF | filename + page badge | "Open page N →" → `GET /api/files/{filename}#page={page+1}` (page is 0-indexed in metadata; browser PDF viewer uses 1-indexed) |
| Web/URL | title or URL (truncated) | "Open source →" → `src.url` (existing link) |
| TXT/CSV | filename | no link |

Source type detected by: `src.source_type === "web"` for web; else check `src.source.endsWith(".pdf")` for PDF; else plain file.

---

### 3. SourceExpander change (`SourceExpander.jsx`)

Remove truncation:
```jsx
// Before
{src.content.length > 200 ? src.content.slice(0, 200) + "..." : src.content}

// After
{src.content}
```

No other changes. Expander still exists — shows full text, page badge, score badges.

---

### 4. Backend file serving (`server/main.py`)

```python
from fastapi.responses import FileResponse
from pathlib import Path

@app.get("/api/files/{filename}")
async def serve_file(filename: str):
    path = Path("data/raw") / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(path)
```

Simple route. No auth needed for demo. Only PDFs use this — `#page=N` fragment handled by browser's built-in PDF viewer.

---

## Data flow

```
LLM streams answer with "[1]", "[2]" tokens
    ↓
MessageBubble parses text → renders [N] as clickable buttons
    ↓
User clicks [1]
    ↓
openCitation = 1 → CitationPopover renders with sources[0]
    ↓
Popover positions relative to button (above/below based on viewport)
    ↓
User sees: full chunk text + source name + page + scores
    ↓
If PDF: "Open page N →" → GET /api/files/{filename}#page=N → browser PDF viewer
```

---

## Error handling

| Scenario | Handling |
|----------|----------|
| `[N]` in answer but `sources[N-1]` missing | Button renders but click is no-op (guard: `if (!src) return`) |
| File not found at `data/raw/` | Backend 404; frontend "Open page" link just fails gracefully (dead link) |
| Popover off-screen horizontally | Clamp left position: `Math.min(rect.left, window.innerWidth - 336)` |
| Answer has no `[N]` markers | Regex split returns single text segment, no buttons rendered — no change to existing UI |

---

## Files changed

| File | Type | Change |
|------|------|--------|
| `frontend/src/components/MessageBubble.jsx` | Edit | Parse `[N]`, render citation buttons, manage state, render `CitationPopover` |
| `frontend/src/components/CitationPopover.jsx` | New | Popover UI + positioning |
| `frontend/src/components/SourceExpander.jsx` | Edit | Remove 200-char truncation |
| `server/main.py` | Edit | Add `GET /api/files/{filename}` route |

---

## Out of scope

- Bounding box / word-level highlight inside PDF (requires pdfplumber at ingest — future)
- Citation highlighting for streaming tokens mid-answer (only after `done` event with sources)
- Auth on `/api/files/` (demo app, no auth layer)
- Mobile popover (click-away works, positioning works — not optimised for small screens)
