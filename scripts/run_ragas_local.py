"""
Run RAGAS evaluation locally and write results to frontend/src/data/ragas_benchmark.json.

Usage:
    python scripts/run_ragas_local.py
    python scripts/run_ragas_local.py --n 10

Prerequisites:
    1. pip install ragas>=0.2.0,<0.3.0 datasets  (not in requirements.txt — server doesn't need it)
    2. .env with GROQ_API_KEY + EURON_API_KEY
    3. Run scripts/run_ingest.py first so ChromaDB is populated

RAGAS works locally because Python uses the default asyncio event loop (not uvloop).
On Render (Linux uvicorn), nest_asyncio can't patch uvloop — that's why it's removed from prod.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import os

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "ragas_benchmark.json"
EVAL_PAIRS_PATH = Path(__file__).resolve().parent.parent / "data" / "ground_truth" / "eval_pairs.json"


def _build_retriever_and_llm():
    from server.bm25_index import build_from_vectorstore
    from server.reranker import load_reranker
    from server.retriever import HybridRetriever
    from server.utils import load_config, setup_logger
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings
    import os

    config = load_config()
    print("Loading vectorstore...")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.getenv("EURON_API_KEY", ""),
        openai_api_base="https://api.euron.one/api/v1/euri",
    )
    vectorstore = Chroma(
        collection_name="prism",
        embedding_function=embeddings,
        persist_directory="./chroma_db",
    )
    if vectorstore._collection.count() == 0:
        print("ERROR: ChromaDB empty. Run scripts/run_ingest.py first.")
        sys.exit(1)

    print("Building BM25 index...")
    build_from_vectorstore(vectorstore)

    print("Loading reranker...")
    load_reranker()

    retriever = HybridRetriever(
        vectorstore=vectorstore,
        dense_weight=config.get("retrieval", {}).get("dense_weight", 0.7),
        sparse_weight=config.get("retrieval", {}).get("sparse_weight", 0.3),
        retrieve_k=config.get("retrieval", {}).get("retrieve_k", 10),
        rerank_k=config.get("retrieval", {}).get("rerank_k", 5),
    )
    return retriever, config


def _build_llm(config):
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=config["llm"]["model"],
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=0.1,
        max_tokens=500,
    )


def _answer_query(llm, retriever, query: str) -> tuple[str, list[str]]:
    """Retrieve context + generate answer. Returns (answer, [context_strings])."""
    from langchain_core.messages import HumanMessage, SystemMessage

    docs = retriever.invoke(query)
    contexts = [d.page_content for d in docs]
    ctx_text = "\n\n".join(f"[Doc {i+1}]\n{c}" for i, c in enumerate(contexts))

    messages = [
        SystemMessage(content=(
            "You are a fintech research assistant. Answer using only the provided context. "
            "Be concise. Cite which doc supports your answer."
        )),
        HumanMessage(content=f"Context:\n{ctx_text}\n\nQuestion: {query}\n\nAnswer:"),
    ]
    response = llm.invoke(messages)
    return response.content.strip(), contexts


def main():
    parser = argparse.ArgumentParser(description="Run RAGAS eval locally and save to JSON")
    parser.add_argument("--n", type=int, default=10, help="Number of eval pairs to run (default 10)")
    parser.add_argument("--full", action="store_true", help="Run all 4 metrics incl. context_precision + context_recall")
    parser.add_argument("--eval-model", default="llama-3.1-8b-instant",
                        help="Groq model used as RAGAS judge (default: llama-3.1-8b-instant, 500k TPD). "
                             "Separate from answer-generation model to avoid burning 70B token quota.")
    args = parser.parse_args()

    print("=== Prism RAGAS Local Benchmark ===\n")

    # Verify required API keys are set
    missing = [k for k in ("GROQ_API_KEY", "EURON_API_KEY") if not os.getenv(k)]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("Check your .env file exists at project root with these keys set.")
        sys.exit(1)

    # Check ragas installed
    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
        from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_openai import OpenAIEmbeddings
    except ImportError as e:
        print(f"ERROR: {e}")
        print("Install with: pip install 'ragas>=0.2.0,<0.3.0' datasets")
        sys.exit(1)

    retriever, config = _build_retriever_and_llm()
    llm = _build_llm(config)

    with open(EVAL_PAIRS_PATH) as f:
        eval_pairs = json.load(f)

    pairs = eval_pairs[:args.n]
    print(f"Running {len(pairs)} queries...\n")

    samples = []
    for i, pair in enumerate(pairs):
        query = pair["query"]
        ground_truth = pair.get("ground_truth")
        print(f"[{i+1}/{len(pairs)}] {query[:70]}")
        try:
            answer, contexts = _answer_query(llm, retriever, query)
            samples.append(SingleTurnSample(
                user_input=query,
                response=answer,
                retrieved_contexts=contexts,
                reference=ground_truth,  # enables context_precision + context_recall
            ))
        except Exception as e:
            print(f"  SKIP (error): {e}")

    if not samples:
        print("No samples collected. Exiting.")
        sys.exit(1)

    print(f"\nCollected {len(samples)} samples. Running RAGAS evaluate()...")

    print(f"RAGAS judge model: {args.eval_model} (answer generation: {config['llm']['model']})")
    from langchain_groq import ChatGroq as _ChatGroq
    ragas_llm = LangchainLLMWrapper(
        _ChatGroq(
            model=args.eval_model,
            api_key=os.getenv("GROQ_API_KEY", ""),
            temperature=0.0,
        )
    )
    ragas_emb = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=os.getenv("EURON_API_KEY", ""),
            openai_api_base="https://api.euron.one/api/v1/euri",
        )
    )

    metrics_to_run = [
        Faithfulness(llm=ragas_llm),
        AnswerRelevancy(llm=ragas_llm, embeddings=ragas_emb),
    ]
    if args.full:
        metrics_to_run += [
            ContextPrecision(llm=ragas_llm),
            ContextRecall(llm=ragas_llm),
        ]
        print("Mode: FULL (4 metrics — faithfulness + answer_relevancy + context_precision + context_recall)")
    else:
        print("Mode: FAST (2 metrics — faithfulness + answer_relevancy). Use --full for context metrics.")

    dataset = EvaluationDataset(samples=samples)
    results = evaluate(dataset=dataset, metrics=metrics_to_run)

    def safe_mean(series):
        try:
            v = series.dropna().mean()
            return round(float(v), 4) if v == v else None  # nan check
        except Exception:
            return None

    scores_df = results.to_pandas()
    print(f"\nDataFrame columns: {list(scores_df.columns)}")
    metric_cols = [c for c in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"] if c in scores_df.columns]
    print("\nPer-sample scores:")
    print(scores_df[metric_cols].to_string())

    output = {
        "faithfulness": safe_mean(scores_df["faithfulness"]) if "faithfulness" in scores_df.columns else None,
        "answer_relevancy": safe_mean(scores_df["answer_relevancy"]) if "answer_relevancy" in scores_df.columns else None,
        "context_precision": safe_mean(scores_df["context_precision"]) if "context_precision" in scores_df.columns else None,
        "context_recall": safe_mean(scores_df["context_recall"]) if "context_recall" in scores_df.columns else None,
        "sample_count": len(samples),
        "computed_at": datetime.now().isoformat(timespec="seconds"),
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n=== Results ===")
    for k in ("faithfulness", "answer_relevancy", "context_precision", "context_recall"):
        print(f"{k:25s}: {output[k]}")
    print(f"{'sample_count':25s}: {output['sample_count']}")
    print(f"\nSaved to: {OUTPUT_PATH}")
    print("Commit frontend/src/data/ragas_benchmark.json to update the dashboard.")


if __name__ == "__main__":
    main()
