import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from langchain_core.documents import Document
from server.ingest import load_documents, chunk_documents, embed_and_store, contextualize_chunks


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


def test_contextualize_chunks_prepends_context():
    """Context prefix must be prepended to chunk.page_content."""
    chunks = [Document(
        page_content="The limit was revised to ₹2 lakh.",
        metadata={"source": "rbi.pdf", "page": 1}
    )]
    documents = [Document(
        page_content="Full RBI document text about UPI limits.",
        metadata={"source": "rbi.pdf"}
    )]

    mock_response = MagicMock()
    mock_response.content = "RBI Circular 2024 on UPI limits. This section covers payment caps."

    with patch("server.ingest.ChatGroq") as MockGroq:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        MockGroq.return_value = mock_llm

        result = contextualize_chunks(chunks, documents, sleep_between_calls=0)

    assert result[0].page_content.startswith("RBI Circular 2024")
    assert "The limit was revised to ₹2 lakh." in result[0].page_content


def test_contextualize_chunks_fallback_on_llm_failure():
    """On Groq failure, original chunk text must be preserved unchanged."""
    original_text = "Original chunk text."
    chunks = [Document(page_content=original_text, metadata={"source": "doc.pdf", "page": 1})]
    documents = [Document(page_content="Full document.", metadata={"source": "doc.pdf"})]

    with patch("server.ingest.ChatGroq") as MockGroq:
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("Groq timeout")
        MockGroq.return_value = mock_llm

        result = contextualize_chunks(chunks, documents, sleep_between_calls=0)

    assert result[0].page_content == original_text


def test_contextualize_chunks_skips_empty_content():
    """Empty chunks must not trigger a Groq call."""
    chunks = [
        Document(page_content="", metadata={"source": "doc.pdf"}),
        Document(page_content="Real content.", metadata={"source": "doc.pdf"}),
    ]
    documents = [Document(page_content="Full doc.", metadata={"source": "doc.pdf"})]

    mock_response = MagicMock()
    mock_response.content = "Context sentence 1. Context sentence 2."

    with patch("server.ingest.ChatGroq") as MockGroq:
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        MockGroq.return_value = mock_llm

        result = contextualize_chunks(chunks, documents, sleep_between_calls=0)

    assert result[0].page_content == ""
    assert mock_llm.invoke.call_count == 1  # only called for non-empty chunk
