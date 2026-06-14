import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks.manager import CallbackManagerForRetrieverRun
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from server.utils import load_config, setup_logger

load_dotenv()

logger = setup_logger(__name__)

DEFAULT_WORKSPACE = "default"

# Singleton caches — avoids re-loading Chroma (and its embeddings) on every request
_vs_cache: dict[str, Chroma] = {}
_retriever_cache: dict[str, "HybridRetriever"] = {}


def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.environ.get("EURON_API_KEY"),
        openai_api_base="https://api.euron.one/api/v1/euri",
    )


def get_vectorstore(collection_name: str = DEFAULT_WORKSPACE) -> Chroma:
    """Return cached ChromaDB collection; create once per workspace."""
    if collection_name not in _vs_cache:
        _vs_cache[collection_name] = Chroma(
            collection_name=collection_name,
            embedding_function=_get_embeddings(),
            persist_directory="./chroma_db",
        )
    return _vs_cache[collection_name]


def invalidate_cache(workspace_id: str) -> None:
    """Drop cached vectorstore + retriever after ingest so next call rebuilds cleanly."""
    _vs_cache.pop(workspace_id, None)
    _retriever_cache.pop(workspace_id, None)


class HybridRetriever(BaseRetriever):
    """Dense + BM25 sparse retrieval fused via RRF, then cross-encoder reranked."""

    vectorstore: Any
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    retrieve_k: int = 10
    rerank_k: int = 5
    workspace_id: str = "default"

    class Config:
        arbitrary_types_allowed = True

    def _dense_retrieve(self, query: str, k: int) -> list[dict]:
        results = self.vectorstore.similarity_search_with_relevance_scores(query, k=k)
        output = []
        for doc, score in results:
            output.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", ""),
                "page": doc.metadata.get("page"),
                "chunk_index": doc.metadata.get("chunk_index"),
                "similarity_score": round(float(score), 4),
            })
        return output

    def _rrf_fuse(self, dense: list[dict], sparse: list[dict]) -> list[dict]:
        """Weighted Reciprocal Rank Fusion. k=60 is standard RRF constant."""
        rrf_k = 60
        scores: dict[str, float] = {}
        docs_map: dict[str, dict] = {}

        for rank, doc in enumerate(dense):
            key = doc["content"][:120]
            scores[key] = scores.get(key, 0.0) + self.dense_weight / (rrf_k + rank + 1)
            docs_map[key] = doc

        for rank, doc in enumerate(sparse):
            key = doc["content"][:120]
            scores[key] = scores.get(key, 0.0) + self.sparse_weight / (rrf_k + rank + 1)
            if key not in docs_map:
                docs_map[key] = doc

        sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
        result = []
        for key in sorted_keys:
            doc = dict(docs_map[key])
            doc["rrf_score"] = round(scores[key], 6)
            result.append(doc)
        return result

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        from server.bm25_index import get_index
        from server.reranker import rerank

        dense_results = self._dense_retrieve(query, k=self.retrieve_k)
        sparse_results = get_index(self.workspace_id).search(query, k=self.retrieve_k)
        fused = self._rrf_fuse(dense_results, sparse_results)
        reranked = rerank(query, fused[: self.retrieve_k], top_k=self.rerank_k)

        docs = []
        for i, d in enumerate(reranked):
            metadata = {
                "source": d.get("source", ""),
                "page": d.get("page"),
                "chunk_index": d.get("chunk_index"),
                "citation_index": i + 1,
                "similarity_score": d.get("similarity_score"),
                "bm25_score": d.get("bm25_score"),
                "rrf_score": d.get("rrf_score"),
                "rerank_score": d.get("rerank_score"),
            }
            docs.append(Document(page_content=d["content"], metadata=metadata))
        return docs


def get_retriever(workspace_id: str = DEFAULT_WORKSPACE) -> HybridRetriever:
    """Return cached HybridRetriever; build once per workspace."""
    if workspace_id not in _retriever_cache:
        config = load_config()
        retrieval_cfg = config.get("retrieval", {})
        vectorstore = get_vectorstore(workspace_id)
        _retriever_cache[workspace_id] = HybridRetriever(
            vectorstore=vectorstore,
            dense_weight=retrieval_cfg.get("dense_weight", 0.7),
            sparse_weight=retrieval_cfg.get("sparse_weight", 0.3),
            retrieve_k=retrieval_cfg.get("retrieve_k", 10),
            rerank_k=retrieval_cfg.get("rerank_k", 5),
            workspace_id=workspace_id,
        )
    return _retriever_cache[workspace_id]


def retrieve_with_scores(query: str, k: int = 5) -> list[dict]:
    """Compatibility shim for precision eval — returns top-k chunks as dicts."""
    retriever = get_retriever()
    retriever.rerank_k = k
    docs = retriever.invoke(query)
    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "page": doc.metadata.get("page"),
            "citation_index": doc.metadata.get("citation_index"),
            "similarity_score": doc.metadata.get("similarity_score"),
            "bm25_score": doc.metadata.get("bm25_score"),
            "rrf_score": doc.metadata.get("rrf_score"),
            "rerank_score": doc.metadata.get("rerank_score"),
        }
        for doc in docs
    ]


def get_document_stats(workspace_id: str = DEFAULT_WORKSPACE) -> list[dict]:
    """Return [{name, chunk_count}] for all unique sources in collection."""
    vectorstore = get_vectorstore(workspace_id)
    try:
        existing = vectorstore.get()
        if not existing or not existing["ids"]:
            return []
        from collections import Counter
        source_counts = Counter(m.get("source", "unknown") for m in existing["metadatas"])
        return [{"name": name, "chunk_count": count} for name, count in sorted(source_counts.items())]
    except Exception:
        return []


def has_documents(workspace_id: str = DEFAULT_WORKSPACE) -> bool:
    return len(get_document_stats(workspace_id)) > 0
