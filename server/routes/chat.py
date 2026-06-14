import gc

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from server.chain import run_query_with_web, condense_question
from server.memory import clear_memory
from server.eval.faithfulness import score_faithfulness
from server.utils import setup_logger

logger = setup_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    web_search: bool = False


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    workspace: str = Query("default"),
):
    """
    Run a RAG query and return answer + sources + faithfulness score.
    If web_search=True, Tavily results are prepended as additional context.
    workspace param selects which ChromaDB collection to retrieve from.
    """
    chain = request.app.state.chain
    if chain is None:
        raise HTTPException(status_code=400, detail="No documents uploaded yet. Please upload documents first.")
    eval_log = request.app.state.eval_log

    # Use cached retriever from app.state (set at upload time); fall back to singleton cache
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        from server.retriever import get_retriever as _get_retriever
        retriever = _get_retriever(workspace)

    web_sources = []
    question = body.question

    logger.info("QUERY | workspace=%s | web_search=%s | %s", workspace, body.web_search, body.question[:100])

    if body.web_search:
        from server.web_search import search_web
        memory = request.app.state.memory
        search_query = condense_question(question, memory)
        web_sources = search_web(search_query)

    memory = request.app.state.memory
    if body.web_search and web_sources:
        result = run_query_with_web(chain, retriever, memory, question, web_sources)
    else:
        result = run_query_with_web(chain, retriever, memory, question, [])

    all_sources = result["source_documents"] + web_sources

    # Ensure citation_index is set on all sources for frontend rendering
    for i, src in enumerate(all_sources):
        if "citation_index" not in src or src["citation_index"] is None:
            src["citation_index"] = i + 1

    faithfulness = score_faithfulness(result["answer"], all_sources)

    logger.info(
        "RESPONSE | workspace=%s | faithfulness=%s | rag_sources=%d | web_sources=%d",
        workspace,
        faithfulness["score"],
        len(result["source_documents"]),
        len(web_sources),
    )

    eval_log.append({
        "query": body.question,
        "answer": result["answer"],
        "contexts": [doc["content"] for doc in all_sources],
        "faithfulness_score": faithfulness["score"],
        "reason": faithfulness["reason"],
    })

    retrieval_method = result.get("retrieval_method", "hybrid+rerank")
    if body.web_search and web_sources:
        retrieval_method += "+web"

    gc.collect()

    return {
        "answer": result["answer"],
        "sources": all_sources,
        "faithfulness": faithfulness,
        "retrieval_method": retrieval_method,
    }


@router.delete("/chat/memory")
async def clear_chat_memory(request: Request):
    """Clear conversation memory for a new conversation."""
    memory = request.app.state.memory
    clear_memory(memory)
    return {"status": "cleared"}
