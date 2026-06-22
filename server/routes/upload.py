import copy
import gc
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request, UploadFile, File, Form, HTTPException, Query
from pydantic import BaseModel

from server.ingest import (
    ingest_files, load_documents_from_paths, chunk_documents,
    embed_and_store, contextualize_chunks_async,
)
from server.retriever import get_document_stats, get_retriever, get_vectorstore, invalidate_cache
from server.bm25_index import build_from_vectorstore
from server.chain import build_qa_chain
from server.memory import create_memory
from server.utils import setup_logger, load_config, log_memory_mb
from server.briefing import generate_briefing

logger = setup_logger(__name__)

router = APIRouter()

UPLOAD_DIR = Path("data/raw")
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv"}


def _rebuild_chain(app, workspace: str) -> None:
    invalidate_cache(workspace)
    build_from_vectorstore(get_vectorstore(workspace), workspace_id=workspace)
    app.state.retriever = get_retriever(workspace)
    app.state.memory = create_memory()
    app.state.chain = build_qa_chain(app.state.retriever, app.state.memory)


async def _contextual_refresh_bg(
    app,
    documents: list,
    original_chunks: list,
    workspace: str,
    ctx_model: str,
    source_filenames: list[str],
    max_concurrent: int = 20,
) -> None:
    """Background: replace non-contextual chunks with parallel-async contextual versions."""
    app.state.is_contextualizing = True
    try:
        gc.collect()
        from server.utils import log_memory_mb as _lmb
        rss = _lmb(logger, "ctx-refresh-start")
        # Safety: if base RSS already above threshold, skip contextualization entirely.
        # Non-contextual chunks are already indexed and queryable.
        RSS_LIMIT_MB = 460
        if rss > RSS_LIMIT_MB:
            logger.warning(
                "Contextual refresh SKIPPED: RSS=%.1fMB exceeds %.0fMB guard — "
                "non-contextual chunks remain active. Upgrade to paid tier for contextual retrieval.",
                rss, RSS_LIMIT_MB,
            )
            return
        logger.info(
            "Contextual refresh start: workspace=%s, %d chunks, model=%s, concurrency=%d",
            workspace, len(original_chunks), ctx_model, max_concurrent,
        )
        ctx_chunks = copy.deepcopy(original_chunks)
        await contextualize_chunks_async(ctx_chunks, documents, model=ctx_model, max_concurrent=max_concurrent)

        vs = get_vectorstore(workspace)
        for filename in source_filenames:
            result = vs.get(where={"source": filename})
            old_ids = result.get("ids", [])
            if old_ids:
                vs.delete(ids=old_ids)
                logger.info("Deleted %d non-contextual chunks for %s", len(old_ids), filename)

        embed_and_store(ctx_chunks, collection_name=workspace)
        _rebuild_chain(app, workspace)
        log_memory_mb(logger, "ctx-refresh-done")
        logger.info("Contextual refresh done: workspace=%s", workspace)
    except Exception as e:
        logger.error("Contextual refresh failed: workspace=%s: %s", workspace, e)
    finally:
        app.state.is_contextualizing = False


@router.post("/upload")
async def upload_files(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    workspace: str = Form("default"),
):
    """
    Accept file uploads (PDF, TXT, CSV).
    Save to data/raw/, run ingestion into the given workspace, rebuild chain.
    If contextual_retrieval.enabled, schedules async background contextualization after fast initial embed.
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")
        dest = UPLOAD_DIR / f.filename
        content = await f.read()
        with open(dest, "wb") as out:
            out.write(content)
        saved_paths.append(str(dest))
        logger.info(f"Saved uploaded file: {f.filename} (workspace={workspace})")

    # Load + chunk (fast)
    try:
        documents = load_documents_from_paths(saved_paths)
    except ValueError as e:
        raise HTTPException(422, str(e))
    chunks = chunk_documents(documents)

    # Embed non-contextual immediately so user can query right away
    embed_and_store(chunks, collection_name=workspace)

    # Rebuild chain before briefing so embed response objects can be GC'd
    _rebuild_chain(request.app, workspace)
    logger.info("Chain rebuilt after upload (workspace=%s)", workspace)
    gc.collect()
    log_memory_mb(logger, "post-embed-gc")

    # Generate briefing after GC to avoid holding embed + briefing response objects simultaneously
    briefing = None
    try:
        vs = get_vectorstore(workspace)
        existing = vs.get(where={"source": Path(saved_paths[0]).name})
        if existing and existing.get("documents"):
            sample_text = " ".join(existing["documents"][:6])
            briefing = generate_briefing(Path(saved_paths[0]).name, sample_text)
    except Exception as e:
        logger.warning("Briefing skipped: %s", e)

    gc.collect()
    log_memory_mb(logger, "post-briefing-gc")

    # Schedule background contextual replacement if enabled
    cfg = load_config()
    ctx_cfg = cfg.get("contextual_retrieval", {})
    if ctx_cfg.get("enabled", False):
        ctx_model = ctx_cfg.get("model", "llama-3.1-8b-instant")
        source_filenames = [Path(p).name for p in saved_paths]
        max_concurrent = ctx_cfg.get("max_concurrent", 20)
        background_tasks.add_task(
            _contextual_refresh_bg,
            request.app, documents, chunks, workspace, ctx_model, source_filenames, max_concurrent,
        )
        logger.info(
            "Contextual refresh scheduled: workspace=%s, %d chunks → ~%ds background",
            workspace, len(chunks), max(5, len(chunks) // 4),
        )

    docs = get_document_stats(workspace)
    return {
        "uploaded": [f.filename for f in files],
        "documents": docs,
        "briefing": briefing,
    }


class UrlUploadRequest(BaseModel):
    url: str
    workspace: str = "default"


@router.post("/upload/url")
async def upload_url(request: Request, body: UrlUploadRequest):
    """Ingest a URL into the document corpus."""
    from server.url_loader import load_url
    from server.ingest import chunk_documents, embed_and_store

    try:
        documents = load_url(body.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("URL fetch error for %s: %s", body.url, e)
        raise HTTPException(502, "Failed to fetch URL. Check that the address is reachable and returns HTML.")

    chunks = []
    try:
        chunks = chunk_documents(documents)
        embed_and_store(chunks, collection_name=body.workspace)
    except Exception as e:
        logger.error("Embedding/store failed for URL %s: %s", body.url, e)
        raise HTTPException(503, "Failed to index URL content. Try again later.")

    # Generate briefing from ingested URL content
    briefing = None
    try:
        sample_text = " ".join(c.page_content for c in chunks[:6])
        briefing = generate_briefing(body.url, sample_text)
    except Exception as e:
        logger.warning("URL briefing skipped: %s", e)

    invalidate_cache(body.workspace)
    build_from_vectorstore(get_vectorstore(body.workspace), workspace_id=body.workspace)
    request.app.state.retriever = get_retriever(body.workspace)
    request.app.state.memory = create_memory()
    request.app.state.chain = build_qa_chain(
        request.app.state.retriever, request.app.state.memory
    )
    logger.info("Chain rebuilt after URL ingest: %s (workspace=%s)", body.url, body.workspace)

    docs = get_document_stats(body.workspace)
    return {
        "url": body.url,
        "chunks_added": len(chunks),
        "documents": docs,
        "briefing": briefing,
    }


@router.get("/documents")
async def list_documents(workspace: str = Query("default")):
    """Return list of uploaded documents with chunk counts."""
    docs = get_document_stats(workspace)
    return {"documents": docs}


@router.delete("/documents/{filename}")
async def delete_document(filename: str, request: Request, workspace: str = Query("default")):
    """
    Remove all chunks for a document from ChromaDB, delete the raw file,
    then rebuild BM25 index and chain.
    """
    vectorstore = get_vectorstore(workspace)

    # Find all chunk IDs for this source
    try:
        result = vectorstore.get(where={"source": filename})
        chunk_ids = result.get("ids", [])
    except Exception as e:
        raise HTTPException(500, f"Failed to query ChromaDB: {e}")

    if not chunk_ids:
        raise HTTPException(404, f"Document '{filename}' not found in index")

    # Delete from ChromaDB
    vectorstore.delete(ids=chunk_ids)
    logger.info(f"Deleted {len(chunk_ids)} chunks for '{filename}' from ChromaDB (workspace={workspace})")

    # Delete raw file if it exists
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted file: {file_path}")

    # Rebuild BM25 + chain
    invalidate_cache(workspace)
    build_from_vectorstore(get_vectorstore(workspace), workspace_id=workspace)
    request.app.state.retriever = get_retriever(workspace)
    request.app.state.memory = create_memory()
    request.app.state.chain = build_qa_chain(
        request.app.state.retriever, request.app.state.memory
    )
    logger.info("Chain rebuilt after document deletion (workspace=%s)", workspace)

    docs = get_document_stats(workspace)
    return {"deleted": filename, "chunks_removed": len(chunk_ids), "documents": docs}
