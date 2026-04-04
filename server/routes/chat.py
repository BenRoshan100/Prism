from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from server.chain import run_query
from server.memory import clear_memory
from server.eval.faithfulness import score_faithfulness
from server.utils import setup_logger

logger = setup_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    question: str


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """
    Run a RAG query and return answer + sources + faithfulness score.
    """
    chain = request.app.state.chain
    if chain is None:
        raise HTTPException(status_code=400, detail="No documents uploaded yet. Please upload documents first.")
    eval_log = request.app.state.eval_log

    result = run_query(chain, body.question)

    # Score faithfulness
    faithfulness = score_faithfulness(result["answer"], result["source_documents"])

    # Log to session eval
    eval_log.append({
        "query": body.question,
        "answer": result["answer"],
        "faithfulness_score": faithfulness["score"],
        "reason": faithfulness["reason"],
    })

    return {
        "answer": result["answer"],
        "sources": result["source_documents"],
        "faithfulness": faithfulness,
    }


@router.delete("/chat/memory")
async def clear_chat_memory(request: Request):
    """Clear conversation memory for a new conversation."""
    memory = request.app.state.memory
    clear_memory(memory)
    return {"status": "cleared"}
