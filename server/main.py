from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.retriever import get_retriever, has_documents
from server.memory import create_memory
from server.chain import build_qa_chain
from server.utils import setup_logger

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize chain, memory, retriever on startup."""
    logger.info("Starting FinRAG server...")
    app.state.memory = create_memory()
    app.state.retriever = None
    app.state.chain = None
    app.state.eval_log = []

    if has_documents():
        app.state.retriever = get_retriever()
        app.state.chain = build_qa_chain(app.state.retriever, app.state.memory)
        logger.info("Chain initialized with existing documents")
    else:
        logger.info("No documents found - chain will be built after first upload")

    logger.info("FinRAG server ready")
    yield


app = FastAPI(title="FinRAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include route modules
from server.routes import chat, eval, upload  # noqa: E402

app.include_router(chat.router, prefix="/api")
app.include_router(eval.router, prefix="/api")
app.include_router(upload.router, prefix="/api")

# Serve React frontend build if it exists
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
