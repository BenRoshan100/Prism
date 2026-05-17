from rank_bm25 import BM25Okapi

from server.utils import setup_logger

logger = setup_logger(__name__)


class BM25Index:
    def __init__(self):
        self._bm25 = None
        self._corpus: list[dict] = []

    def build(self, corpus: list[dict]) -> None:
        """Build BM25 index from corpus of dicts with 'content' key."""
        self._corpus = corpus
        tokenized = [doc["content"].lower().split() for doc in corpus]
        self._bm25 = BM25Okapi(tokenized)
        logger.info(f"BM25 index built: {len(corpus)} docs")

    def search(self, query: str, k: int = 20) -> list[dict]:
        """Return top-k docs with bm25_score. Returns [] if index not built."""
        if self._bm25 is None:
            return []
        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)
        top_k_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for idx in top_k_idx:
            if scores[idx] > 0:
                doc = dict(self._corpus[idx])
                doc["bm25_score"] = round(float(scores[idx]), 4)
                results.append(doc)
        return results

    def is_built(self) -> bool:
        return self._bm25 is not None


# Module-level singleton
_index = BM25Index()


def get_index() -> BM25Index:
    return _index


def build_from_vectorstore(vectorstore) -> None:
    """Fetch all docs from ChromaDB and rebuild BM25 index."""
    try:
        existing = vectorstore.get()
        if not existing or not existing.get("ids"):
            logger.warning("ChromaDB empty — BM25 index not built")
            return
        corpus = []
        for text, meta in zip(existing["documents"], existing["metadatas"]):
            corpus.append({
                "content": text,
                "source": meta.get("source", ""),
                "page": meta.get("page"),
                "chunk_index": meta.get("chunk_index"),
            })
        _index.build(corpus)
    except Exception as e:
        logger.error(f"Failed to build BM25 index: {e}")
