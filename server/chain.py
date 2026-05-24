from langchain_groq import ChatGroq
from langchain_classic.chains import ConversationalRetrievalChain

from server.utils import load_config, setup_logger

logger = setup_logger(__name__)

SYSTEM_PROMPT = (
    "You are FinRAG, a fintech research assistant. "
    "Answer questions using the provided context documents. "
    "When the question contains a section marked '[Additional context from web search:]', "
    "treat that web content as valid context and use it to answer. "
    "If the exact date or data point requested is not available but a close/recent value is, "
    "provide that value and clearly state the actual date it refers to (e.g. 'As of May 22...'). "
    "Only say you don't know if the topic is completely absent from all context. "
    "Do not hallucinate. Be concise and cite your source (document name or URL)."
)


def _create_llm(llm_config: dict) -> ChatGroq:
    """Create ChatGroq instance. Model set in config.yaml."""
    model = llm_config["model"]
    logger.info(f"Using LLM: {model}")

    return ChatGroq(
        model=model,
        api_key=_get_api_key(),
        temperature=llm_config.get("temperature", 0.1),
        max_tokens=llm_config.get("max_tokens", 1000),
    )


def build_qa_chain(retriever, memory) -> ConversationalRetrievalChain:
    """
    Build LangChain ConversationalRetrievalChain:
    - LLM: Groq (model set in config.yaml)
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
    """Run RAG chain. Returns answer + source_documents."""
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


def condense_question(question: str, memory) -> str:
    """
    Rewrite question as a standalone query using chat history.
    Used before Tavily search so web query has full context.
    Returns original question if no history or condensation fails.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    history = memory.load_memory_variables({}).get("chat_history", [])
    if not history:
        logger.info("condense_question: no history, using raw question")
        return question

    logger.info("condense_question: %d history messages available", len(history))
    history_text = "\n".join(
        f"{'Human' if getattr(m, 'type', '') == 'human' else 'Assistant'}: {m.content[:120]}"
        for m in history[-6:]  # last 3 turns
    )

    config = load_config()
    llm = _create_llm(config.get("llm", {}))

    prompt = (
        f"Given this conversation history:\n{history_text}\n\n"
        f"Rewrite the follow-up question as a complete standalone search query "
        f"(include all relevant entities from history). "
        f"Return ONLY the rewritten query, nothing else.\n\n"
        f"Follow-up question: {question}"
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        condensed = response.content.strip().strip('"')
        logger.info("Condensed query: %s → %s", question[:60], condensed[:80])
        return condensed
    except Exception as e:
        logger.warning("Question condensation failed: %s", e)
        return question


def run_query_with_web(
    chain, retriever, memory, question: str, web_sources: list[dict]
) -> dict:
    """
    Web-search variant: retrieves RAG docs directly (bypasses chain condensation),
    combines with Tavily results, calls LLM once with full context + chat history.
    ConversationalRetrievalChain condensation step strips prepended web context —
    this bypasses that while preserving memory.
    """
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

    # RAG retrieval
    rag_docs_lc = retriever.invoke(question)
    rag_docs = []
    for doc in rag_docs_lc:
        rag_docs.append({
            "content": doc.page_content,
            "source": doc.metadata.get("source", ""),
            "page": doc.metadata.get("page", None),
            "chunk_index": doc.metadata.get("chunk_index", None),
            "similarity_score": doc.metadata.get("similarity_score"),
            "bm25_score": doc.metadata.get("bm25_score"),
            "rrf_score": doc.metadata.get("rrf_score"),
            "rerank_score": doc.metadata.get("rerank_score"),
        })

    # Build combined context string
    rag_ctx = "\n\n".join(
        f"[Doc: {d['source']}]\n{d['content']}" for d in rag_docs
    ) or "No document context."

    web_ctx = "\n\n".join(
        f"[Web: {w['title']} | {w['url']}]\n{w['content']}" for w in web_sources
    )

    combined = f"=== Document context ===\n{rag_ctx}\n\n=== Web search results ===\n{web_ctx}"

    config = load_config()
    llm = _create_llm(config.get("llm", {}))

    # Build messages: system + history + current turn
    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    history = memory.load_memory_variables({}).get("chat_history", [])
    for msg in history:
        if hasattr(msg, "type"):
            if msg.type == "human":
                messages.append(HumanMessage(content=msg.content))
            else:
                messages.append(AIMessage(content=msg.content))

    messages.append(
        HumanMessage(content=f"Context:\n{combined}\n\nQuestion: {question}\n\nAnswer:")
    )

    response = llm.invoke(messages)
    answer = response.content.strip()

    # Save turn to memory so follow-up questions have context
    memory.save_context({"input": question}, {"answer": answer})

    logger.info("run_query_with_web | rag=%d web=%d history=%d", len(rag_docs), len(web_sources), len(history))

    return {
        "answer": answer,
        "source_documents": rag_docs,
        "question": question,
        "retrieval_method": "hybrid+rerank+web",
    }


def _get_api_key() -> str:
    """Load Groq API key from environment."""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        logger.warning("GROQ_API_KEY not set in environment")
    return key
