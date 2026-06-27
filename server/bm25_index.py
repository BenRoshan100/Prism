from rank_bm25 import BM25Okapi

from server.utils import setup_logger

logger = setup_logger(__name__)

DEFAULT_WORKSPACE = "default"


class BM25Index:
    def __init__(self):
        self._bm25 = None
        self._corpus: list[dict] = []

    def build(self, corpus: list[dict]) -> None:
        self._corpus = corpus
        tokenized = [doc["content"].lower().split() for doc in corpus]
        self._bm25 = BM25Okapi(tokenized)
        logger.info(f"BM25 index built: {len(corpus)} docs")

    def search(self, query: str, k: int = 20, filter_sources: set[str] | None = None) -> list[dict]:
        if self._bm25 is None:
            return []

        # If no filter, use pre-built index and corpus as-is
        if filter_sources is None:
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

        # Filter corpus by sources
        corpus = [d for d in self._corpus if d["source"] in filter_sources]
        if not corpus:
            return []

        # Build temporary BM25 index on filtered corpus
        tokenized_corpus = [doc["content"].lower().split() for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)
        top_k_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        results = []
        for idx in top_k_idx:
            # For filtered corpus, include all results (small corpora can produce negative BM25 scores)
            doc = dict(corpus[idx])
            doc["bm25_score"] = round(float(scores[idx]), 4)
            results.append(doc)
        return results

    def is_built(self) -> bool:
        return self._bm25 is not None


# Workspace-keyed dict of BM25 indexes
_indexes: dict[str, BM25Index] = {}


def get_index(workspace_id: str = DEFAULT_WORKSPACE) -> BM25Index:
    if workspace_id not in _indexes:
        _indexes[workspace_id] = BM25Index()
    return _indexes[workspace_id]


def build_from_vectorstore(vectorstore, workspace_id: str = DEFAULT_WORKSPACE) -> None:
    """Fetch all docs from ChromaDB collection and rebuild BM25 index for workspace."""
    try:
        existing = vectorstore.get()
        if not existing or not existing.get("ids"):
            logger.warning("ChromaDB empty for workspace '%s' — BM25 not built", workspace_id)
            return
        corpus = []
        for text, meta in zip(existing["documents"], existing["metadatas"]):
            corpus.append({
                "content": text,
                "source": meta.get("source", ""),
                "page": meta.get("page"),
                "chunk_index": meta.get("chunk_index"),
            })
        get_index(workspace_id).build(corpus)
    except Exception as e:
        logger.error("Failed to build BM25 for workspace '%s': %s", workspace_id, e)


def delete_workspace_index(workspace_id: str) -> None:
    """Remove BM25 index for a deleted workspace."""
    _indexes.pop(workspace_id, None)
    logger.info("BM25 index deleted for workspace '%s'", workspace_id)
