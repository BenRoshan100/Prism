from unittest.mock import MagicMock, patch
from langchain_core.documents import Document
from server.retriever import HybridRetriever, get_retriever_filtered


def _make_retriever(filter_docs=None):
    mock_vs = MagicMock()
    mock_vs.similarity_search_with_relevance_scores.return_value = [
        (Document(page_content="UPI grew in 2024", metadata={"source": "rbi.pdf", "page": 1, "chunk_index": 0}), 0.85),
        (Document(page_content="NPCI payments record", metadata={"source": "npci.pdf", "page": 1, "chunk_index": 0}), 0.72),
    ]
    return HybridRetriever(
        vectorstore=mock_vs,
        dense_weight=0.7,
        sparse_weight=0.3,
        retrieve_k=10,
        rerank_k=5,
        workspace_id="test",
        use_hyde=False,
        use_multi_query=False,
        filter_docs=filter_docs,
    )


def test_filter_docs_field_defaults_to_none():
    retriever = _make_retriever()
    assert retriever.filter_docs is None


def test_filter_docs_field_set():
    retriever = _make_retriever(filter_docs=["rbi.pdf"])
    assert retriever.filter_docs == ["rbi.pdf"]


def test_dense_retrieve_passes_filter_to_chroma():
    retriever = _make_retriever(filter_docs=["rbi.pdf"])
    retriever._dense_retrieve("UPI", k=5)
    call_kwargs = retriever.vectorstore.similarity_search_with_relevance_scores.call_args
    assert call_kwargs.kwargs.get("filter") == {"source": {"$in": ["rbi.pdf"]}}


def test_dense_retrieve_no_filter_when_none():
    retriever = _make_retriever(filter_docs=None)
    retriever._dense_retrieve("UPI", k=5)
    call_kwargs = retriever.vectorstore.similarity_search_with_relevance_scores.call_args
    assert call_kwargs.kwargs.get("filter") is None


def test_get_retriever_filtered_returns_retriever_with_filter():
    mock_vs = MagicMock()
    with patch("server.retriever.get_vectorstore", return_value=mock_vs), \
         patch("server.retriever.load_config", return_value={
             "retrieval": {"dense_weight": 0.7, "sparse_weight": 0.3,
                           "retrieve_k": 10, "rerank_k": 5,
                           "hyde_enabled": False, "multi_query_enabled": False}
         }):
        r = get_retriever_filtered("default", ["rbi.pdf"])
    assert r.filter_docs == ["rbi.pdf"]
    assert r.vectorstore is mock_vs


def test_get_retriever_filtered_does_not_modify_singleton_cache():
    from server.retriever import _retriever_cache
    initial_keys = set(_retriever_cache.keys())
    mock_vs = MagicMock()
    with patch("server.retriever.get_vectorstore", return_value=mock_vs), \
         patch("server.retriever.load_config", return_value={
             "retrieval": {"dense_weight": 0.7, "sparse_weight": 0.3,
                           "retrieve_k": 10, "rerank_k": 5,
                           "hyde_enabled": False, "multi_query_enabled": False}
         }):
        get_retriever_filtered("workspace-filtered", ["doc.pdf"])
    assert "workspace-filtered" not in _retriever_cache
    assert set(_retriever_cache.keys()) == initial_keys
