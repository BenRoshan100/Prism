from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, HTTPException

from server.ingest import ingest_files
from server.retriever import get_document_stats, get_retriever, get_vectorstore
from server.bm25_index import build_from_vectorstore
from server.chain import build_qa_chain
from server.memory import create_memory
from server.utils import setup_logger

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

    # Rebuild BM25 index and chain with new data
    build_from_vectorstore(get_vectorstore())
    request.app.state.retriever = get_retriever()
    request.app.state.memory = create_memory()
    request.app.state.chain = build_qa_chain(
        request.app.state.retriever, request.app.state.memory
    )
    logger.info("Chain rebuilt after upload")

    docs = get_document_stats()
    return {"uploaded": [f.filename for f in files], "documents": docs}


@router.get("/documents")
async def list_documents():
    """Return list of uploaded documents with chunk counts."""
    docs = get_document_stats()
    return {"documents": docs}
