import os
from dotenv import load_dotenv

from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics import Faithfulness, AnswerRelevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from server.utils import load_config, setup_logger

load_dotenv()
logger = setup_logger(__name__)


def _safe_round(val, decimals: int = 4):
    """Round float or return None if val is None/NaN."""
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return None


def _get_api_key() -> str:
    return os.getenv("EURON_API_KEY", "")


def _make_llm() -> LangchainLLMWrapper:
    config = load_config()
    llm_cfg = config.get("llm", {})
    llm = ChatOpenAI(
        model=llm_cfg["model"],
        base_url=llm_cfg.get("base_url", "https://api.euron.one/api/v1/euri"),
        api_key=_get_api_key(),
        temperature=0.0,
    )
    return LangchainLLMWrapper(llm)


def _make_embeddings() -> LangchainEmbeddingsWrapper:
    emb = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=_get_api_key(),
        openai_api_base="https://api.euron.one/api/v1/euri",
    )
    return LangchainEmbeddingsWrapper(emb)


def run_ragas_eval(eval_log: list[dict], n_pairs: int = 10) -> dict:
    """
    Run RAGAS on last n_pairs from session eval_log.

    Computes faithfulness + answer_relevancy (no ground_truth required).
    context_precision + context_recall return null — require labeled ground_truth dataset.

    Args:
        eval_log: list of {query, answer, contexts, ...} dicts from session
        n_pairs: number of recent pairs to evaluate

    Returns:
        dict with faithfulness, answer_relevancy, context_precision (null),
        context_recall (null), per_query, sample_count
    """
    pairs = [p for p in eval_log if p.get("contexts")]
    pairs = pairs[-n_pairs:]

    if not pairs:
        return {
            "faithfulness": None,
            "answer_relevancy": None,
            "context_precision": None,
            "context_recall": None,
            "per_query": [],
            "sample_count": 0,
            "note": "No session pairs with contexts found. Ask questions first.",
        }

    samples = [
        SingleTurnSample(
            user_input=p["query"],
            response=p["answer"],
            retrieved_contexts=p["contexts"],
        )
        for p in pairs
    ]

    dataset = EvaluationDataset(samples=samples)
    ragas_llm = _make_llm()
    ragas_emb = _make_embeddings()

    metrics = [
        Faithfulness(llm=ragas_llm),
        AnswerRelevancy(llm=ragas_llm, embeddings=ragas_emb),
    ]

    logger.info(f"Running RAGAS on {len(samples)} pairs")
    results = evaluate(dataset=dataset, metrics=metrics)

    scores_df = results.to_pandas()
    per_query = []
    for i, row in scores_df.iterrows():
        per_query.append({
            "query": pairs[i]["query"],
            "faithfulness": _safe_round(row.get("faithfulness")),
            "answer_relevancy": _safe_round(row.get("answer_relevancy")),
        })

    return {
        "faithfulness": _safe_round(results["faithfulness"]),
        "answer_relevancy": _safe_round(results["answer_relevancy"]),
        "context_precision": None,
        "context_recall": None,
        "per_query": per_query,
        "sample_count": len(samples),
        "note": "context_precision and context_recall require labeled ground_truth dataset",
    }
