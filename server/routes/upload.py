import copy
import gc
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse
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


async def _embed_and_contextualize_bg(
    app,
    documents: list,
    chunks: list,
    workspace: str,
    saved_paths: list[str],
    job_id: str,
) -> None:
    """Background: embed chunks, rebuild chain, generate briefing, optionally contextualize."""
    jobs = app.state.upload_jobs
    cfg = load_config()
    ctx_cfg = cfg.get("contextual_retrieval", {})

    try:
        # Phase 1: embed
        n = len(chunks)
        jobs[job_id]["status"] = "embedding"
        jobs[job_id]["message"] = f"Embedding {n} chunks..."
        log_memory_mb(logger, "bg-embed-start")

        embed_and_store(chunks, collection_name=workspace)
        _rebuild_chain(app, workspace)
        gc.collect()
        log_memory_mb(logger, "bg-embed-done")

        # Briefing
        briefing = None
        try:
            vs = get_vectorstore(workspace)
            existing = vs.get(where={"source": Path(saved_paths[0]).name})
            if existing and existing.get("documents"):
                sample_text = " ".join(existing["documents"][:6])
                briefing = generate_briefing(Path(saved_paths[0]).name, sample_text)
        except Exception as e:
            logger.warning("Briefing skipped: %s", e)
        jobs[job_id]["briefing"] = briefing
        gc.collect()

        # Phase 2: contextual refresh (optional)
        if ctx_cfg.get("enabled", False):
            ctx_model = ctx_cfg.get("model", "llama-3.1-8b-instant")
            max_concurrent = ctx_cfg.get("max_concurrent", 3)
            source_filenames = [Path(p).name for p in saved_paths]

            jobs[job_id]["status"] = "contextualizing"
            jobs[job_id]["message"] = f"Adding context to {n} chunks..."
            app.state.is_contextualizing = True
            log_memory_mb(logger, "bg-ctx-start")

            try:
                ctx_chunks = copy.deepcopy(chunks)
                await contextualize_chunks_async(
                    ctx_chunks, documents, model=ctx_model, max_concurrent=max_concurrent
                )
                vs = get_vectorstore(workspace)
                for filename in source_filenames:
                    result = vs.get(where={"source": filename})
                    old_ids = result.get("ids", [])
                    if old_ids:
                        vs.delete(ids=old_ids)
                embed_and_store(ctx_chunks, collection_name=workspace)
                _rebuild_chain(app, workspace)
                log_memory_mb(logger, "bg-ctx-done")
            finally:
                app.state.is_contextualizing = False
                gc.collect()

        jobs[job_id]["status"] = "ready"
        jobs[job_id]["message"] = "Ready"
        logger.info("Upload job %s complete (workspace=%s)", job_id, workspace)

    except Exception as e:
        logger.error("Upload job %s failed: %s", job_id, e)
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = "Processing failed"
        jobs[job_id]["error"] = str(e)
        app.state.is_contextualizing = False


@router.post("/upload", status_code=202)
async def upload_files(
    request: Request,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    workspace: str = Form("default"),
):
    """
    Accept file uploads. Parse and chunk synchronously (fast), return 202 with job_id.
    Embedding and contextualisation run in background.
    Poll GET /api/upload/status/{job_id} for progress.
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
        logger.info("Saved uploaded file: %s (workspace=%s)", f.filename, workspace)

    # Parse + chunk synchronously so we can return 422 for bad files immediately
    try:
        documents = load_documents_from_paths(saved_paths)
    except ValueError as e:
        raise HTTPException(422, str(e))
    chunks = chunk_documents(documents)

    # Register job
    job_id = uuid.uuid4().hex
    request.app.state.upload_jobs[job_id] = {
        "status": "embedding",
        "message": f"Embedding {len(chunks)} chunks...",
        "briefing": None,
        "error": None,
        "workspace": workspace,
    }

    background_tasks.add_task(
        _embed_and_contextualize_bg,
        request.app, documents, chunks, workspace, saved_paths, job_id,
    )

    logger.info(
        "Upload job %s started: workspace=%s, %d chunks", job_id, workspace, len(chunks)
    )
    return {"job_id": job_id, "uploaded": [f.filename for f in files], "total_chunks": len(chunks)}


@router.get("/upload/status/{job_id}")
async def upload_status(job_id: str, request: Request):
    """Poll upload job status. Returns status, message, and briefing when ready."""
    job = request.app.state.upload_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"Job '{job_id}' not found")
    return {
        "status": job["status"],
        "message": job["message"],
        "briefing": job.get("briefing"),
        "error": job.get("error"),
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

    try:
        result = vectorstore.get(where={"source": filename})
        chunk_ids = result.get("ids", [])
    except Exception as e:
        raise HTTPException(500, f"Failed to query ChromaDB: {e}")

    if not chunk_ids:
        raise HTTPException(404, f"Document '{filename}' not found in index")

    vectorstore.delete(ids=chunk_ids)
    logger.info(f"Deleted {len(chunk_ids)} chunks for '{filename}' from ChromaDB (workspace={workspace})")

    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted file: {file_path}")

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
