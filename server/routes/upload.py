from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel

from server.ingest import ingest_files
from server.retriever import get_document_stats, get_retriever, get_vectorstore
from server.bm25_index import build_from_vectorstore
from server.chain import build_qa_chain
from server.memory import create_memory
from server.utils import setup_logger
from server.briefing import generate_briefing

logger = setup_logger(__name__)

router = APIRouter()

UPLOAD_DIR = Path("data/raw")
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv"}


@router.post("/upload")
async def upload_files(request: Request, files: list[UploadFile] = File(...)):
    """
    Accept file uploads (PDF, TXT, CSV).
    Save to data/raw/, run ingestion, rebuild chain.
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
        logger.info(f"Saved uploaded file: {f.filename}")

    # Run ingestion on uploaded files
    ingest_files(saved_paths)

    # Generate briefing from first uploaded file's chunks
    briefing = None
    try:
        vs = get_vectorstore()
        existing = vs.get(where={"source": Path(saved_paths[0]).name})
        if existing and existing.get("documents"):
            sample_text = " ".join(existing["documents"][:6])
            briefing = generate_briefing(Path(saved_paths[0]).name, sample_text)
    except Exception as e:
        logger.warning("Briefing skipped: %s", e)

    # Rebuild BM25 index and chain with new data
    build_from_vectorstore(get_vectorstore())
    request.app.state.retriever = get_retriever()
    request.app.state.memory = create_memory()
    request.app.state.chain = build_qa_chain(
        request.app.state.retriever, request.app.state.memory
    )
    logger.info("Chain rebuilt after upload")

    docs = get_document_stats()
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
        embed_and_store(chunks)
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

    build_from_vectorstore(get_vectorstore())
    request.app.state.retriever = get_retriever()
    request.app.state.memory = create_memory()
    request.app.state.chain = build_qa_chain(
        request.app.state.retriever, request.app.state.memory
    )
    logger.info("Chain rebuilt after URL ingest: %s", body.url)

    docs = get_document_stats()
    return {
        "url": body.url,
        "chunks_added": len(chunks),
        "documents": docs,
        "briefing": briefing,
    }


@router.get("/documents")
async def list_documents():
    """Return list of uploaded documents with chunk counts."""
    docs = get_document_stats()
    return {"documents": docs}


@router.delete("/documents/{filename}")
async def delete_document(filename: str, request: Request):
    """
    Remove all chunks for a document from ChromaDB, delete the raw file,
    then rebuild BM25 index and chain.
    """
    vectorstore = get_vectorstore()

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
    logger.info(f"Deleted {len(chunk_ids)} chunks for '{filename}' from ChromaDB")

    # Delete raw file if it exists
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted file: {file_path}")

    # Rebuild BM25 + chain
    build_from_vectorstore(get_vectorstore())
    request.app.state.retriever = get_retriever()
    request.app.state.memory = create_memory()
    request.app.state.chain = build_qa_chain(
        request.app.state.retriever, request.app.state.memory
    )
    logger.info("Chain rebuilt after document deletion")

    docs = get_document_stats()
    return {"deleted": filename, "chunks_removed": len(chunk_ids), "documents": docs}
