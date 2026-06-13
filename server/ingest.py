import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from server.utils import load_config, setup_logger

load_dotenv()

logger = setup_logger(__name__)


def load_documents(data_dir: str) -> list:
    """
    Load all PDFs and .txt files from data_dir.
    Return list of LangChain Document objects with metadata:
    - source: filename
    - page: page number (PDFs only)
    """
    data_path = Path(data_dir)
    documents = []

    for file_path in sorted(data_path.iterdir()):
        if file_path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(file_path))
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_path.name
            documents.extend(docs)
        elif file_path.suffix.lower() == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_path.name
            documents.extend(docs)
        elif file_path.suffix.lower() == ".csv":
            loader = CSVLoader(str(file_path), encoding="utf-8")
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_path.name
            documents.extend(docs)

    logger.info(f"Loaded {len(documents)} document pages from {data_dir}")
    return documents


def load_documents_from_paths(file_paths: list[str]) -> list:
    """Load documents from explicit file paths (not directory scan)."""
    documents = []
    for fp in file_paths:
        file_path = Path(fp)
        if file_path.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(file_path))
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_path.name
            documents.extend(docs)
        elif file_path.suffix.lower() == ".txt":
            loader = TextLoader(str(file_path), encoding="utf-8")
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_path.name
            documents.extend(docs)
        elif file_path.suffix.lower() == ".csv":
            loader = CSVLoader(str(file_path), encoding="utf-8")
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_path.name
            documents.extend(docs)
    logger.info(f"Loaded {len(documents)} document pages from {len(file_paths)} files")
    return documents


def ingest_files(file_paths: list[str], collection_name: str = "default") -> Chroma:
    """Ingest specific files: load -> chunk -> embed -> store."""
    documents = load_documents_from_paths(file_paths)
    chunks = chunk_documents(documents)
    vectorstore = embed_and_store(chunks, collection_name=collection_name)
    return vectorstore


def chunk_documents(documents: list, chunk_size: int = 500, chunk_overlap: int = 50) -> list:
    """
    Split documents using RecursiveCharacterTextSplitter.
    Preserve metadata from parent document. Add chunk_index to metadata.
    """
    config = load_config()
    chunk_size = config.get("chunking", {}).get("chunk_size", chunk_size)
    chunk_overlap = config.get("chunking", {}).get("chunk_overlap", chunk_overlap)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = splitter.split_documents(documents)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    logger.info(f"Created {len(chunks)} chunks (size={chunk_size}, overlap={chunk_overlap})")
    return chunks


def _chunk_id(chunk) -> str:
    """Generate a deterministic ID from chunk content + metadata for idempotency."""
    source = chunk.metadata.get("source", "")
    page = str(chunk.metadata.get("page", ""))
    content_hash = hashlib.md5((source + page + chunk.page_content).encode()).hexdigest()
    return content_hash


def embed_and_store(chunks: list, collection_name: str = "default") -> Chroma:
    """
    Embed chunks and store in ChromaDB at ./chroma_db.
    Idempotent: uses content hash as document ID to prevent duplicates.
    collection_name maps to workspace_id — each workspace gets its own ChromaDB collection.
    """
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.environ.get("EURON_API_KEY"),
        openai_api_base="https://api.euron.one/api/v1/euri",
    )

    ids = [_chunk_id(chunk) for chunk in chunks]
    texts = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory="./chroma_db",
    )

    # Filter out chunks that already exist
    existing_ids = set()
    try:
        existing = vectorstore.get()
        if existing and existing["ids"]:
            existing_ids = set(existing["ids"])
    except Exception:
        pass

    new_indices = [i for i, doc_id in enumerate(ids) if doc_id not in existing_ids]

    if new_indices:
        new_texts = [texts[i] for i in new_indices]
        new_metadatas = [metadatas[i] for i in new_indices]
        new_ids = [ids[i] for i in new_indices]
        vectorstore.add_texts(texts=new_texts, metadatas=new_metadatas, ids=new_ids)
        logger.info(f"Added {len(new_indices)} new chunks to ChromaDB (skipped {len(ids) - len(new_indices)} existing)")
    else:
        logger.info("All chunks already exist in ChromaDB, skipping")

    return vectorstore


def run_ingestion_pipeline(data_dir: str) -> Chroma:
    """
    Orchestrates: load -> chunk -> embed -> store.
    """
    print(f"Loading documents from {data_dir}...")
    documents = load_documents(data_dir)
    print(f"Loaded {len(documents)} document pages")

    print("Chunking...")
    chunks = chunk_documents(documents)
    print(f"{len(chunks)} chunks created")

    print("Embedding and storing in ChromaDB...")
    vectorstore = embed_and_store(chunks)

    count = vectorstore._collection.count()
    print(f"{count} chunks ready in ChromaDB")

    return vectorstore
