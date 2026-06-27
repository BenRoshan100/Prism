import pytest
from server.bm25_index import BM25Index


@pytest.fixture
def index_with_two_docs():
    idx = BM25Index()
    idx.build([
        {"content": "UPI transaction volume grew exponentially to unprecedented levels in 2024", "source": "rbi.pdf", "page": 1, "chunk_index": 0},
        {"content": "NPCI transaction processing infrastructure uses UPI digital payments", "source": "npci.pdf", "page": 1, "chunk_index": 0},
        {"content": "UPI merchant ceiling limit revised upward to two lakh rupees for retailers", "source": "rbi.pdf", "page": 2, "chunk_index": 1},
        {"content": "Card payment systems and network operations", "source": "other.pdf", "page": 1, "chunk_index": 0},
        {"content": "Mobile banking services and digital wallets", "source": "other.pdf", "page": 2, "chunk_index": 1},
    ])
    return idx


def test_search_no_filter_returns_all_sources(index_with_two_docs):
    results = index_with_two_docs.search("UPI transaction", k=10)
    sources = {r["source"] for r in results}
    assert "rbi.pdf" in sources
    assert "npci.pdf" in sources


def test_search_filter_restricts_to_source(index_with_two_docs):
    results = index_with_two_docs.search("UPI transaction", k=10, filter_sources={"rbi.pdf"})
    assert all(r["source"] == "rbi.pdf" for r in results)
    assert len(results) == 2  # two rbi.pdf chunks scored > 0


def test_search_filter_empty_set_returns_empty(index_with_two_docs):
    results = index_with_two_docs.search("UPI", k=10, filter_sources=set())
    assert results == []


def test_search_filter_nonexistent_source_returns_empty(index_with_two_docs):
    results = index_with_two_docs.search("UPI", k=10, filter_sources={"missing.pdf"})
    assert results == []


def test_search_filter_multiple_sources(index_with_two_docs):
    results = index_with_two_docs.search("UPI", k=10, filter_sources={"rbi.pdf", "npci.pdf"})
    sources = {r["source"] for r in results}
    assert "rbi.pdf" in sources
    assert "npci.pdf" in sources


def test_search_unbuilt_index_returns_empty():
    idx = BM25Index()
    results = idx.search("anything", k=5, filter_sources={"rbi.pdf"})
    assert results == []
