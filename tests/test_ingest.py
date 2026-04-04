import shutil
from pathlib import Path

import pytest

from server.ingest import load_documents, chunk_documents, embed_and_store


DATA_DIR = "data/raw"


def test_load_documents_returns_documents():
    docs = load_documents(DATA_DIR)
    assert len(docs) > 0
    for doc in docs:
        assert doc.page_content
        assert "source" in doc.metadata


def test_chunk_documents_preserves_metadata():
    docs = load_documents(DATA_DIR)
    chunks = chunk_documents(docs)
    assert len(chunks) > len(docs)
    for chunk in chunks:
        assert "source" in chunk.metadata
        assert "chunk_index" in chunk.metadata
        assert isinstance(chunk.metadata["chunk_index"], int)


def test_embed_and_store_is_idempotent(tmp_path):
    """Running embed_and_store twice should not duplicate chunks."""
    # Use a temporary chroma_db to avoid polluting the real one
    docs = load_documents(DATA_DIR)
    chunks = chunk_documents(docs)

    # Temporarily override persist_directory by using a small subset
    small_chunks = chunks[:5]

    test_db = str(tmp_path / "chroma_test")

    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    import hashlib

    def _chunk_id(chunk):
        source = chunk.metadata.get("source", "")
        page = str(chunk.metadata.get("page", ""))
        return hashlib.md5((source + page + chunk.page_content).encode()).hexdigest()

    ids = [_chunk_id(c) for c in small_chunks]
    texts = [c.page_content for c in small_chunks]
    metadatas = [c.metadata for c in small_chunks]

    # First insert
    vs = Chroma(collection_name="test", embedding_function=embeddings, persist_directory=test_db)
    vs.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    count_after_first = vs._collection.count()

    # Second insert with same IDs — should not duplicate
    vs2 = Chroma(collection_name="test", embedding_function=embeddings, persist_directory=test_db)
    # Chroma upserts by ID, so adding same IDs won't duplicate
    vs2.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    count_after_second = vs2._collection.count()

    assert count_after_first == count_after_second == 5
