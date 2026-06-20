import asyncio
import hashlib
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq

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


def contextualize_chunks(
    chunks: list,
    documents: list,
    model: str = "llama-3.1-8b-instant",
    sleep_between_calls: float = 0.1,
) -> list:
    """Prepend 2-sentence LLM context to each chunk before embedding.

    Falls back to original chunk text on any Groq failure.
    """
    from langchain_core.messages import HumanMessage

    doc_text_map: dict[str, str] = {}
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        doc_text_map[source] = doc_text_map.get(source, "") + " " + doc.page_content

    llm = ChatGroq(
        model=model,
        api_key=os.environ.get("GROQ_API_KEY", ""),
        temperature=0.1,
        max_tokens=150,
    )

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        if not chunk.page_content.strip():
            continue

        source = chunk.metadata.get("source", "unknown")
        full_doc_text = doc_text_map.get(source, "")[:3000]

        prompt = (
            "You are helping improve document retrieval. Given a document and a chunk "
            "from it, write 2 concise sentences situating the chunk within the document.\n\n"
            f"Document name: {source}\n"
            f"Full document text: {full_doc_text}\n\n"
            f"Chunk to situate:\n{chunk.page_content}\n\n"
            "Write only the 2 situating sentences. No preamble."
        )

        for attempt in range(2):
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                context_prefix = response.content.strip()
                chunk.page_content = f"{context_prefix} {chunk.page_content}"
                logger.info(
                    "Contextualized chunk %d/%d: %s page %s",
                    i + 1, total, source, chunk.metadata.get("page", "?"),
                )
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning(
                        "Groq call failed for chunk %d/%d, retrying in 2s: %s",
                        i + 1, total, e,
                    )
                    time.sleep(2)
                else:
                    logger.warning(
                        "Groq call failed for chunk %d/%d (attempt 2), using original text: %s",
                        i + 1, total, e,
                    )

        time.sleep(sleep_between_calls)

    return chunks


async def _contextualize_one(
    sem: asyncio.Semaphore,
    llm,
    chunk,
    doc_text_map: dict,
    idx: int,
    total: int,
) -> None:
    from langchain_core.messages import HumanMessage
    if not chunk.page_content.strip():
        return
    source = chunk.metadata.get("source", "unknown")
    full_doc_text = doc_text_map.get(source, "")[:3000]
    prompt = (
        "You are helping improve document retrieval. Given a document and a chunk "
        "from it, write 2 concise sentences situating the chunk within the document.\n\n"
        f"Document name: {source}\n"
        f"Full document text: {full_doc_text}\n\n"
        f"Chunk to situate:\n{chunk.page_content}\n\n"
        "Write only the 2 situating sentences. No preamble."
    )
    async with sem:
        for attempt in range(2):
            try:
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                chunk.page_content = f"{response.content.strip()} {chunk.page_content}"
                logger.info("Contextualized chunk %d/%d: %s", idx + 1, total, source)
                break
            except Exception as e:
                if attempt == 0:
                    logger.warning("Chunk %d/%d retry in 2s: %s", idx + 1, total, e)
                    await asyncio.sleep(2)
                else:
                    logger.warning("Chunk %d/%d fallback to original: %s", idx + 1, total, e)


async def contextualize_chunks_async(
    chunks: list,
    documents: list,
    model: str = "llama-3.1-8b-instant",
    max_concurrent: int = 20,
) -> list:
    """Parallel async contextualization — ~10× faster than sequential contextualize_chunks().

    Uses asyncio.gather with a semaphore to cap concurrent Groq calls.
    Falls back to original chunk text on any failure. Safe to use in FastAPI background tasks.
    """
    doc_text_map: dict[str, str] = {}
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        doc_text_map[source] = doc_text_map.get(source, "") + " " + doc.page_content

    llm = ChatGroq(
        model=model,
        api_key=os.environ.get("GROQ_API_KEY", ""),
        temperature=0.1,
        max_tokens=150,
    )

    sem = asyncio.Semaphore(max_concurrent)
    total = len(chunks)
    await asyncio.gather(*[
        _contextualize_one(sem, llm, chunk, doc_text_map, i, total)
        for i, chunk in enumerate(chunks)
    ])
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
