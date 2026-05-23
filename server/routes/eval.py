from fastapi import APIRouter, Request
from pydantic import BaseModel

from server.eval.precision import run_batch_precision_eval
from server.eval.ragas_eval import run_ragas_eval
from server.utils import load_config, setup_logger

logger = setup_logger(__name__)

router = APIRouter()


class RagasRequest(BaseModel):
    n_pairs: int = 10


@router.get("/eval/session")
async def get_session_eval_log(request: Request):
    """Return the session eval log: list of {query, answer, faithfulness_score, reason}."""
    return {"eval_log": request.app.state.eval_log}


@router.post("/eval/precision")
async def run_precision_eval():
    """
    Run batch Precision@K eval against ground truth.
    Returns mean_precision_at_k and per_query_results.
    """
    config = load_config()
    eval_config = config.get("eval", {})
    ground_truth_path = eval_config.get("ground_truth_path", "data/ground_truth/eval_pairs.json")
    k = eval_config.get("precision_k", 5)

    results = run_batch_precision_eval(ground_truth_path, k=k)
    return results


@router.post("/eval/ragas")
async def run_ragas_evaluation(request: Request, body: RagasRequest):
    """
    Run RAGAS on last n_pairs from session.
    Returns faithfulness, answer_relevancy (context_precision/recall require ground_truth).
    """
    eval_log = request.app.state.eval_log
    results = run_ragas_eval(eval_log, n_pairs=body.n_pairs)
    return results
