import pytest

from server.retriever import get_retriever
from server.memory import create_memory
from server.chain import build_qa_chain, run_query


@pytest.fixture(scope="module")
def chain():
    retriever = get_retriever()
    memory = create_memory()
    return build_qa_chain(retriever, memory)


def test_run_query_returns_required_keys(chain):
    result = run_query(chain, "What is UPI?")
    assert "answer" in result
    assert "source_documents" in result
    assert "question" in result


def test_answer_is_non_empty_string(chain):
    result = run_query(chain, "What was Bajaj Finance profit in Q3 FY2024?")
    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0


def test_source_documents_is_list(chain):
    result = run_query(chain, "RBI digital lending guidelines")
    assert isinstance(result["source_documents"], list)
    assert len(result["source_documents"]) > 0
