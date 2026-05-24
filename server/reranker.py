from sentence_transformers import CrossEncoder

from server.utils import setup_logger

logger = setup_logger(__name__)

MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model: CrossEncoder | None = None


def load_reranker() -> CrossEncoder:
    """Load cross-encoder model (call at startup to avoid cold-start latency)."""
    global _model
    if _model is None:
        logger.info(f"Loading reranker: {MODEL_NAME}")
        _model = CrossEncoder(MODEL_NAME)
        logger.info("Reranker loaded")
    return _model


def rerank(query: str, docs: list[dict], top_k: int = 5) -> list[dict]:
    """Score query-doc pairs; return top_k sorted by rerank_score desc."""
    if not docs:
        return []
    model = load_reranker()
    pairs = [(query, d["content"]) for d in docs]
    scores = model.predict(pairs, batch_size=4)
    ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    result = []
    for score, doc in ranked[:top_k]:
        doc = dict(doc)
        doc["rerank_score"] = round(float(score), 4)
        result.append(doc)
    return result
