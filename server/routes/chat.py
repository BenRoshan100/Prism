import gc
import json

from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from server.chain import stream_query_with_web, condense_question
from server.memory import clear_memory
from server.utils import setup_logger, log_memory_mb

logger = setup_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    workspace: str = Query("default"),
):
    chain = request.app.state.chain
    retriever = getattr(request.app.state, "retriever", None)
    if retriever is None:
        from server.retriever import get_retriever as _get_retriever
        retriever = _get_retriever(workspace)

    eval_log = request.app.state.eval_log
    memory = request.app.state.memory

    async def generate():
        try:
            if chain is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No documents uploaded yet. Please upload documents first.'})}\n\n"
                return

            log_memory_mb(logger, "chat-start")
            logger.info("QUERY | workspace=%s | %s", workspace, body.question[:100])

            web_sources = []
            try:
                from server.web_search import search_web
                search_query = condense_question(body.question, memory)
                web_sources = search_web(search_query)
            except Exception as e:
                logger.warning("Web search failed: %s", e)

            full_answer_parts: list[str] = []

            try:
                async for event in stream_query_with_web(retriever, memory, body.question, web_sources):
                    if event["type"] == "token":
                        full_answer_parts.append(event["content"])
                        yield f"data: {json.dumps(event)}\n\n"

                    elif event["type"] == "done":
                        all_sources = event["sources"] + web_sources
                        for i, src in enumerate(all_sources):
                            if not src.get("citation_index"):
                                src["citation_index"] = i + 1
                        done_payload = {
                            "type": "done",
                            "sources": all_sources,
                            "retrieval_method": event["retrieval_method"],
                        }
                        yield f"data: {json.dumps(done_payload)}\n\n"
                        eval_log.append({
                            "query": body.question,
                            "answer": "".join(full_answer_parts),
                            "contexts": [s["content"] for s in all_sources],
                        })
                        logger.info(
                            "RESPONSE | workspace=%s | rag=%d | web=%d",
                            workspace, len(event["sources"]), len(web_sources),
                        )

                    elif event["type"] == "error":
                        yield f"data: {json.dumps(event)}\n\n"
                        return

            except Exception as e:
                logger.error("Streaming chat error: %s", e)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        finally:
            gc.collect()
            log_memory_mb(logger, "chat-end")

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.delete("/chat/memory")
async def clear_chat_memory(request: Request):
    """Clear conversation memory for a new conversation."""
    memory = request.app.state.memory
    clear_memory(memory)
    return {"status": "cleared"}
