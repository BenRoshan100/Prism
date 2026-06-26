from contextlib import asynccontextmanager
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server.retriever import get_retriever, get_vectorstore, has_documents
from server.bm25_index import build_from_vectorstore, DEFAULT_WORKSPACE as BM25_DEFAULT
from server.reranker import load_reranker
from server.memory import create_memory
from server.chain import build_qa_chain
from server.utils import configure_logging, setup_logger, log_memory_mb

# Module-level constant so tests can monkeypatch it
UPLOAD_DIR = Path("data/raw")

configure_logging()
logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize chain, memory, retriever on startup."""
    logger.info("Starting Prism server...")
    app.state.memory = create_memory()
    app.state.retriever = None
    app.state.chain = None
    app.state.eval_log = []
    app.state.is_contextualizing = False  # True while background contextual refresh runs
    app.state.upload_jobs = {}  # job_id -> {status, message, briefing, error, workspace}

    # Pre-load reranker to avoid cold-start latency on first query
    load_reranker()

    if has_documents(BM25_DEFAULT):
        vectorstore = get_vectorstore(BM25_DEFAULT)
        build_from_vectorstore(vectorstore, workspace_id=BM25_DEFAULT)
        app.state.retriever = get_retriever(BM25_DEFAULT)
        app.state.chain = build_qa_chain(app.state.retriever, app.state.memory)
        logger.info("Chain initialized with existing documents")
    else:
        logger.info("No documents found - chain will be built after first upload")

    log_memory_mb(logger, "startup")
    logger.info("Prism server ready")
    yield


app = FastAPI(title="Prism API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s  %d  %.0fms",
        request.method,
        request.url.path,
        response.status_code,
        ms,
    )
    return response

# Import and include route modules
from server.routes import chat, eval, upload, workspaces  # noqa: E402

app.include_router(chat.router, prefix="/api")
app.include_router(eval.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/files/{filename}")
async def serve_file(filename: str) -> FileResponse:
    """Serve uploaded files from data/raw/ for citation PDF links."""
    upload_root = UPLOAD_DIR.resolve()
    target = (UPLOAD_DIR / filename).resolve()
    if not str(target).startswith(str(upload_root)):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(target))


# Serve React frontend build if it exists
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
