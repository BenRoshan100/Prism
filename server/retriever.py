import os

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from server.utils import load_config, setup_logger

load_dotenv()

logger = setup_logger(__name__)


def _get_embeddings():
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.environ.get("EURON_API_KEY"),
        openai_api_base="https://api.euron.one/api/v1/euri",
    )


def get_retriever(collection_name: str = "finrag", k: int = 5):
    """
    Load existing ChromaDB collection.
    Return LangChain retriever with k results.
    """
    config = load_config()
    collection_name = config.get("retrieval", {}).get("collection_name", collection_name)
    k = config.get("retrieval", {}).get("k", k)

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
        persist_directory="./chroma_db",
    )

    return vectorstore.as_retriever(search_kwargs={"k": k})


def retrieve_with_scores(query: str, k: int = 5) -> list[dict]:
    """
    Return list of dicts with content, source, page, chunk_index, similarity_score.
    """
    config = load_config()
    collection_name = config.get("retrieval", {}).get("collection_name", "finrag")
    k = config.get("retrieval", {}).get("k", k)

    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
        persist_directory="./chroma_db",
    )

    results = vectorstore.similarity_search_with_relevance_scores(query, k=k)

    output = []
    for doc, score in results:
        output.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "page": doc.metadata.get("page", None),
            "chunk_index": doc.metadata.get("chunk_index", None),
            "similarity_score": round(score, 4),
        })

    return output


def get_document_stats(collection_name: str = "finrag") -> list[dict]:
    """Return list of {name, chunk_count} for all unique sources in the collection."""
    config = load_config()
    collection_name = config.get("retrieval", {}).get("collection_name", collection_name)
    vectorstore = Chroma(
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
        persist_directory="./chroma_db",
    )
    try:
        existing = vectorstore.get()
        if not existing or not existing["ids"]:
            return []
        from collections import Counter
        source_counts = Counter(m.get("source", "unknown") for m in existing["metadatas"])
        return [{"name": name, "chunk_count": count} for name, count in sorted(source_counts.items())]
    except Exception:
        return []


def has_documents(collection_name: str = "finrag") -> bool:
    """Check if any documents exist in the collection."""
    return len(get_document_stats(collection_name)) > 0
