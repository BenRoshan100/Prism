from langchain_openai import ChatOpenAI
from langchain_classic.chains import ConversationalRetrievalChain

from server.utils import load_config, setup_logger

logger = setup_logger(__name__)

SYSTEM_PROMPT = (
    "You are FinRAG, a fintech research assistant. Answer questions using "
    "only the provided context. If the answer is not in the context, say "
    "'I could not find this in the loaded documents.' Do not hallucinate. "
    "Be concise and cite your source document."
)


def _create_llm(llm_config: dict) -> ChatOpenAI:
    """
    Create ChatOpenAI instance pointed at Euron API.
    Works with any model Euron supports (OpenAI, Anthropic, Google, Meta, etc.)
    — just change the model name in config.yaml.
    """
    model = llm_config["model"]
    logger.info(f"Using LLM: {model}")

    return ChatOpenAI(
        model=model,
        base_url=llm_config.get("base_url", "https://api.euron.one/api/v1/euri"),
        api_key=_get_api_key(),
        temperature=llm_config.get("temperature", 0.1),
        extra_body={"max_tokens": llm_config.get("max_tokens", 1000)},
    )


def build_qa_chain(retriever, memory) -> ConversationalRetrievalChain:
    """
    Build LangChain ConversationalRetrievalChain:
    - LLM: any model via Euron API (set in config.yaml)
    - Retriever: from retriever.py
    - Memory: from memory.py
    - return_source_documents: True
    """
    config = load_config()
    llm_config = config.get("llm", {})
    llm = _create_llm(llm_config)

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
        verbose=False,
    )

    logger.info("QA chain built successfully")
    return chain


def run_query(chain, question: str) -> dict:
    """
    Run chain on question.
    Return dict with answer, source_documents, and question.
    """
    result = chain.invoke({"question": question})

    source_docs = []
    for doc in result.get("source_documents", []):
        source_docs.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "page": doc.metadata.get("page", None),
            "chunk_index": doc.metadata.get("chunk_index", None),
            "similarity_score": doc.metadata.get("similarity_score"),
            "bm25_score": doc.metadata.get("bm25_score"),
            "rrf_score": doc.metadata.get("rrf_score"),
            "rerank_score": doc.metadata.get("rerank_score"),
        })

    return {
        "answer": result.get("answer", ""),
        "source_documents": source_docs,
        "question": question,
        "retrieval_method": "hybrid+rerank",
    }


def _get_api_key() -> str:
    """Load Euron API key from environment."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("EURON_API_KEY", "")
    if not key:
        logger.warning("EURON_API_KEY not set in environment")
    return key
