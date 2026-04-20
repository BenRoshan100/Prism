import json

from server.retriever import retrieve_with_scores
from server.utils import setup_logger

logger = setup_logger(__name__)


def compute_precision_at_k(query: str, retrieved_chunks: list[dict], ground_truth: dict, k: int = 5) -> float:
    """
    Precision@K = (relevant chunks in top-K) / K

    A chunk is "relevant" if:
    - Its source matches ground_truth["relevant_sources"], OR
    - Its content contains any keyword from ground_truth["relevant_chunk_keywords"]

    Return float between 0 and 1.
    """
    relevant_sources = ground_truth.get("relevant_sources", [])
    keywords = ground_truth.get("relevant_chunk_keywords", [])

    top_k = retrieved_chunks[:k]
    relevant_count = 0

    for chunk in top_k:
        source_match = chunk.get("source", "") in relevant_sources
        keyword_match = any(
            kw.lower() in chunk.get("content", "").lower() for kw in keywords
        )
        if source_match or keyword_match:
            relevant_count += 1

    precision = relevant_count / k if k > 0 else 0.0
    return round(precision, 4)


def run_batch_precision_eval(eval_pairs_path: str, k: int = 5) -> dict:
    """
    Run precision@K for all queries in eval_pairs.json.
    Return dict with mean_precision_at_k and per_query_results.
    """
    with open(eval_pairs_path, "r") as f:
        eval_pairs = json.load(f)

    per_query_results = []

    for pair in eval_pairs:
        query = pair["query"]
        retrieved = retrieve_with_scores(query, k=k)
        precision = compute_precision_at_k(query, retrieved, pair, k=k)
        retrieved_sources = [c["source"] for c in retrieved]

        per_query_results.append({
            "query": query,
            "precision_at_k": precision,
            "retrieved_sources": retrieved_sources,
        })

        logger.info(f"P@{k}={precision:.2f} | {query[:60]}...")

    mean_precision = sum(r["precision_at_k"] for r in per_query_results) / len(per_query_results)

    return {
        "mean_precision_at_k": round(mean_precision, 4),
        "per_query_results": per_query_results,
    }


def run_batch_precision_eval_multi_k(eval_pairs_path: str, ks: list[int]) -> dict:
    """
    Run precision evaluation for multiple K values.
    Return a dict keyed by precision@K.
    """
    results = {}
    for k in ks:
        results[f"precision@{k}"] = run_batch_precision_eval(eval_pairs_path, k=k)
    return results
