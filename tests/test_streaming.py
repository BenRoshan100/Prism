import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document


def make_mock_retriever(docs=None):
    retriever = MagicMock()
    if docs is None:
        docs = [Document(page_content="test content", metadata={"source": "test.pdf", "page": 1})]
    retriever.invoke.return_value = docs
    return retriever


def make_mock_memory(history=None):
    memory = MagicMock()
    memory.load_memory_variables.return_value = {"chat_history": history or []}
    return memory


async def collect_events(gen):
    events = []
    async for event in gen:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_stream_yields_tokens_then_done():
    from server.chain import stream_query_with_web

    retriever = make_mock_retriever()
    memory = make_mock_memory()

    mock_chunk1 = MagicMock()
    mock_chunk1.content = "Hello "
    mock_chunk2 = MagicMock()
    mock_chunk2.content = "world."

    async def fake_astream(messages):
        for chunk in [mock_chunk1, mock_chunk2]:
            yield chunk

    with patch("server.chain._create_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.astream = fake_astream
        mock_llm_factory.return_value = mock_llm

        events = await collect_events(
            stream_query_with_web(retriever, memory, "test question", [])
        )

    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]

    assert len(token_events) == 2
    assert token_events[0]["content"] == "Hello "
    assert token_events[1]["content"] == "world."
    assert len(done_events) == 1
    assert done_events[0]["retrieval_method"] == "hybrid+rerank+web"
    assert isinstance(done_events[0]["sources"], list)


@pytest.mark.asyncio
async def test_stream_yields_error_on_llm_failure():
    from server.chain import stream_query_with_web

    retriever = make_mock_retriever()
    memory = make_mock_memory()

    async def failing_astream(messages):
        raise RuntimeError("LLM exploded")
        yield  # make it a generator

    with patch("server.chain._create_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.astream = failing_astream
        mock_llm_factory.return_value = mock_llm

        events = await collect_events(
            stream_query_with_web(retriever, memory, "test question", [])
        )

    assert events[0]["type"] == "error"
    assert "LLM exploded" in events[0]["message"]


@pytest.mark.asyncio
async def test_stream_saves_memory_after_tokens():
    from server.chain import stream_query_with_web

    retriever = make_mock_retriever()
    memory = make_mock_memory()

    mock_chunk = MagicMock()
    mock_chunk.content = "answer text"

    async def fake_astream(messages):
        yield mock_chunk

    with patch("server.chain._create_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.astream = fake_astream
        mock_llm_factory.return_value = mock_llm

        await collect_events(
            stream_query_with_web(retriever, memory, "test question", [])
        )

    memory.save_context.assert_called_once_with(
        {"input": "test question"}, {"answer": "answer text"}
    )
