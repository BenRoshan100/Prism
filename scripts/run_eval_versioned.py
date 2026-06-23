"""
Versioned eval script for Prism. Writes timestamped JSON to eval-dashboard/public/data/runs/
and updates eval-dashboard/public/data/index.json.

Metrics:
  answer_correctness  — LLM judge (8B): generated answer vs ground_truth, 0–1
  answer_relevancy    — RAGAS: does answer address the question?
  context_recall      — RAGAS: did retrieval surface all needed chunks?
  precision_at_5      — (relevant chunks in top-5) / 5, source + keyword match
  latency_p50/p95/p99 — per-query end-to-end timing (retrieval + LLM, no Tavily)

Usage:
    python scripts/run_eval_versioned.py --version v2.0 --tag "baseline" --n 50
    python scripts/run_eval_versioned.py --version v2.1 --tag "HyDE enabled" --n 50

Prerequisites:
    pip install 'ragas>=0.2.0,<0.3.0' datasets
    .env with GROQ_API_KEY + EURON_API_KEY
    scripts/run_ingest.py run first (ChromaDB populated)
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv()

EVAL_PAIRS_PATH = Path(__file__).resolve().parent.parent / "data" / "ground_truth" / "eval_pairs.json"
DASHBOARD_RUNS_DIR = Path(__file__).resolve().parent.parent / "eval-dashboard" / "public" / "data" / "runs"
DASHBOARD_INDEX_PATH = Path(__file__).resolve().parent.parent / "eval-dashboard" / "public" / "data" / "index.json"

CORRECTNESS_PROMPT = """\
You are an evaluation judge. Score the generated answer against the reference answer.

Use a 1–5 integer scale:
5 — All key facts present and correct
4 — Most key facts correct, minor omissions or imprecision
3 — Some key facts correct, moderate gaps
2 — Few facts correct, significant errors or hallucinations
1 — Completely wrong, irrelevant, or contradicts reference

Reference answer: {ground_truth}

Generated answer: {answer}

Respond with JSON only — a single object, nothing else:
{{"score": 4, "reason": "one sentence"}}"""


def _build_retriever(config, workspace_id="default"):
    from server.bm25_index import build_from_vectorstore
    from server.reranker import load_reranker
    from server.retriever import HybridRetriever
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    print("Loading vectorstore...")
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=os.getenv("EURON_API_KEY", ""),
        openai_api_base="https://api.euron.one/api/v1/euri",
    )
    vectorstore = Chroma(
        collection_name=workspace_id,
        embedding_function=embeddings,
        persist_directory="./chroma_db",
    )
    if vectorstore._collection.count() == 0:
        print(f"ERROR: ChromaDB collection '{workspace_id}' empty. Run scripts/run_ingest.py first.")
        sys.exit(1)

    print("Building BM25 index...")
    build_from_vectorstore(vectorstore, workspace_id=workspace_id)

    print("Loading reranker...")
    load_reranker()

    retrieval_cfg = config.get("retrieval", {})
    retriever = HybridRetriever(
        vectorstore=vectorstore,
        dense_weight=retrieval_cfg.get("dense_weight", 0.7),
        sparse_weight=retrieval_cfg.get("sparse_weight", 0.3),
        retrieve_k=retrieval_cfg.get("retrieve_k", 10),
        rerank_k=retrieval_cfg.get("rerank_k", 5),
        workspace_id=workspace_id,
        use_hyde=retrieval_cfg.get("hyde_enabled", False),
    )
    return retriever


def _make_llm(model: str, temperature: float = 0.1, max_tokens: int = 500):
    from langchain_groq import ChatGroq
    return ChatGroq(
        model=model,
        api_key=os.getenv("GROQ_API_KEY", ""),
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _answer_query(llm, retriever, query: str) -> tuple[str, list, list[dict]]:
    """Returns (answer, lc_docs, chunk_dicts)."""
    from langchain_core.messages import HumanMessage, SystemMessage

    docs = retriever.invoke(query)
    contexts = [d.page_content for d in docs]
    chunk_dicts = [
        {"content": d.page_content, "source": d.metadata.get("source", "")}
        for d in docs
    ]
    ctx_text = "\n\n".join(f"[Doc {i+1}]\n{c}" for i, c in enumerate(contexts))
    messages = [
        SystemMessage(content=(
            "You are a research assistant. Answer using only the provided context. "
            "Be concise and precise. State which document supports your answer."
        )),
        HumanMessage(content=f"Context:\n{ctx_text}\n\nQuestion: {query}\n\nAnswer:"),
    ]
    response = llm.invoke(messages)
    return response.content.strip(), docs, chunk_dicts


def _score_correctness(judge_llm, answer: str, ground_truth: str) -> tuple[float, str]:
    """Returns (score 0–1, reason). Judge uses 1–5 integer scale normalized to 0–1."""
    from langchain_core.messages import HumanMessage
    import re
    prompt = CORRECTNESS_PROMPT.format(ground_truth=ground_truth, answer=answer)
    try:
        resp = judge_llm.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        # extract JSON block
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1:
            raise ValueError(f"No JSON in response: {raw[:120]}")
        parsed = json.loads(raw[start:end])
        raw_score = float(parsed["score"])
        # normalize 1–5 → 0–1; if model returns 0–1 directly, keep as-is
        score = (raw_score - 1) / 4 if raw_score > 1 else raw_score
        score = max(0.0, min(1.0, score))
        return round(score, 4), parsed.get("reason", "")
    except json.JSONDecodeError:
        # fallback: find first integer 1–5 in response
        m = re.search(r'\b([1-5])\b', raw)
        if m:
            raw_score = int(m.group(1))
            score = (raw_score - 1) / 4
            return round(score, 4), f"fallback parse from: {raw[:80]}"
        print(f"    correctness judge parse failed: {raw[:120]}")
        return None, f"parse error: {raw[:80]}"
    except Exception as e:
        print(f"    correctness judge error: {e}")
        return None, f"error: {e}"


def _compute_percentile(values: list[float], p: int) -> int:
    if not values:
        return 0
    return int(np.percentile(values, p))


def _ingest_contextual(data_dir: str, ctx_model: str) -> None:
    """Clear eval_ctx ChromaDB collection and re-ingest with LLM context prefixes."""
    import chromadb
    from server.ingest import load_documents, chunk_documents, contextualize_chunks, embed_and_store

    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        client.delete_collection("eval_ctx")
        print("  Cleared existing eval_ctx collection.")
    except Exception:
        pass

    documents = load_documents(data_dir)
    chunks = chunk_documents(documents)
    print(f"  Contextualizing {len(chunks)} chunks with {ctx_model}...")
    chunks = contextualize_chunks(chunks, documents, model=ctx_model, sleep_between_calls=0.1)
    embed_and_store(chunks, collection_name="eval_ctx")
    print(f"  Done. eval_ctx collection ready ({len(chunks)} chunks).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="Version tag e.g. v2.1")
    parser.add_argument("--tag", required=True, help="Short description e.g. 'HyDE enabled'")
    parser.add_argument("--n", type=int, default=50, help="Number of eval pairs (default 50)")
    parser.add_argument("--workspace", default="default", help="ChromaDB workspace collection name")
    parser.add_argument("--judge-model", default="llama-3.1-8b-instant",
                        help="Groq judge model for correctness + RAGAS (default: llama-3.1-8b-instant)")
    parser.add_argument("--contextual", action="store_true",
                        help="Ingest corpus with LLM context prefixes into eval_ctx before eval")
    parser.add_argument("--data-dir", default="data/raw",
                        help="Source documents dir for --contextual ingest (default: data/raw)")
    args = parser.parse_args()

    print(f"=== Prism Eval — {args.version} | {args.tag} ===\n")

    missing = [k for k in ("GROQ_API_KEY", "EURON_API_KEY") if not os.getenv(k)]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample, RunConfig
        from ragas.metrics import AnswerRelevancy, ContextRecall
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_openai import OpenAIEmbeddings as _OAIEmb
    except ImportError as e:
        print(f"ERROR: {e}\nInstall: pip install 'ragas>=0.2.0,<0.3.0' datasets")
        sys.exit(1)

    from server.utils import load_config
    from server.eval.precision import compute_precision_at_k

    config = load_config()
    workspace_id = "eval_ctx" if args.contextual else args.workspace

    if args.contextual:
        ctx_cfg = config.get("contextual_retrieval", {})
        ctx_model = ctx_cfg.get("model", args.judge_model)
        print(f"Contextual retrieval: ingesting {args.data_dir} → eval_ctx ({ctx_model})...")
        _ingest_contextual(args.data_dir, ctx_model=ctx_model)

    retriever = _build_retriever(config, workspace_id=workspace_id)
    answer_llm = _make_llm(config["llm"]["model"], temperature=0.1, max_tokens=500)
    judge_llm = _make_llm(args.judge_model, temperature=0.0, max_tokens=200)

    ragas_llm = LangchainLLMWrapper(_make_llm(args.judge_model, temperature=0.0, max_tokens=2048))
    ragas_emb = LangchainEmbeddingsWrapper(
        _OAIEmb(
            model="text-embedding-3-small",
            openai_api_key=os.getenv("EURON_API_KEY", ""),
            openai_api_base="https://api.euron.one/api/v1/euri",
        )
    )

    with open(EVAL_PAIRS_PATH) as f:
        all_pairs = json.load(f)
    pairs = all_pairs[:args.n]
    print(f"Evaluating {len(pairs)} pairs with judge={args.judge_model}\n")

    per_query = []
    ragas_samples = []
    latencies = []

    for i, pair in enumerate(pairs):
        query = pair["query"]
        ground_truth = pair.get("ground_truth", "")
        print(f"[{i+1:02d}/{len(pairs)}] {query[:70]}")

        try:
            t0 = time.time()
            answer, lc_docs, chunk_dicts = _answer_query(answer_llm, retriever, query)
            latency_ms = int((time.time() - t0) * 1000)
            latencies.append(latency_ms)

            correctness, correctness_reason = _score_correctness(judge_llm, answer, ground_truth)
            precision = compute_precision_at_k(query, chunk_dicts, pair, k=5)

            print(f"       correctness={correctness:.2f} p@5={precision:.2f} latency={latency_ms}ms")

            ragas_samples.append(SingleTurnSample(
                user_input=query,
                response=answer,
                retrieved_contexts=[d.page_content for d in lc_docs],
                reference=ground_truth,
            ))

            per_query.append({
                "query": query,
                "answer": answer,
                "ground_truth": ground_truth,
                "answer_correctness": round(correctness, 4) if correctness is not None else None,
                "correctness_reason": correctness_reason,
                "answer_relevancy": None,   # filled after RAGAS run
                "context_recall": None,     # filled after RAGAS run
                "precision_at_5": precision,
                "latency_ms": latency_ms,
                "retrieved_sources": [c["source"] for c in chunk_dicts],
            })

        except Exception as e:
            print(f"       SKIP: {e}")

    # RAGAS batch eval — max_workers=2 to avoid Groq free-tier rate limit timeouts
    print(f"\nRunning RAGAS on {len(ragas_samples)} samples (answer_relevancy + context_recall)...")
    print(f"Using max_workers=1 to avoid Groq rate limits — will take ~{len(ragas_samples) // 2}-{len(ragas_samples)} min for {len(ragas_samples)} samples")
    dataset = EvaluationDataset(samples=ragas_samples)
    ragas_cfg = RunConfig(timeout=180, max_workers=1, max_retries=10)
    results = evaluate(
        dataset=dataset,
        metrics=[
            AnswerRelevancy(llm=ragas_llm, embeddings=ragas_emb),
            ContextRecall(llm=ragas_llm),
        ],
        run_config=ragas_cfg,
    )
    scores_df = results.to_pandas()
    print(f"RAGAS columns: {list(scores_df.columns)}")

    def _safe_float(val):
        """Return float or None — never NaN."""
        try:
            f = float(val)
            return None if math.isnan(f) else round(f, 4)
        except (TypeError, ValueError):
            return None

    # patch per_query with RAGAS per-sample scores
    ragas_idx = 0
    for item in per_query:
        if ragas_idx < len(scores_df):
            row = scores_df.iloc[ragas_idx]
            item["answer_relevancy"] = _safe_float(row.get("answer_relevancy"))
            item["context_recall"] = _safe_float(row.get("context_recall"))
            ragas_idx += 1

    def safe_mean(key):
        vals = [r[key] for r in per_query if r.get(key) is not None]
        return round(float(np.mean(vals)), 4) if vals else None

    metrics = {
        "answer_correctness": safe_mean("answer_correctness"),
        "answer_relevancy": safe_mean("answer_relevancy"),
        "context_recall": safe_mean("context_recall"),
        "precision_at_5": safe_mean("precision_at_5"),
        "latency_p50_ms": _compute_percentile(latencies, 50),
        "latency_p95_ms": _compute_percentile(latencies, 95),
        "latency_p99_ms": _compute_percentile(latencies, 99),
    }

    retrieval_cfg = config.get("retrieval", {})
    run_data = {
        "version": args.version,
        "tag": args.tag,
        "computed_at": datetime.now().isoformat(timespec="seconds"),
        "sample_count": len(per_query),
        "config": {
            "hyde_enabled": retrieval_cfg.get("hyde_enabled", False),
            "multi_query_enabled": retrieval_cfg.get("multi_query_enabled", False),
            "contextual_retrieval": args.contextual,
            "retrieve_k": retrieval_cfg.get("retrieve_k", 10),
            "rerank_k": retrieval_cfg.get("rerank_k", 5),
            "llm": config.get("llm", {}).get("model", "unknown"),
            "judge_model": args.judge_model,
            "workspace": workspace_id,
        },
        "metrics": metrics,
        "per_query": per_query,
    }

    # Write run file
    DASHBOARD_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_filename = f"{args.version}_{date.today().strftime('%Y%m%d')}.json"
    run_path = DASHBOARD_RUNS_DIR / run_filename
    with open(run_path, "w") as f:
        json.dump(run_data, f, indent=2)
    print(f"\nRun written to: {run_path}")

    # Update index
    if DASHBOARD_INDEX_PATH.exists():
        with open(DASHBOARD_INDEX_PATH) as f:
            index = json.load(f)
    else:
        index = []

    # Replace existing entry for same version, else append
    entry = {"version": args.version, "tag": args.tag, "date": str(date.today()), "file": run_filename}
    index = [e for e in index if e["version"] != args.version]
    index.append(entry)
    index.sort(key=lambda e: e["date"])

    with open(DASHBOARD_INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)
    print(f"Index updated: {DASHBOARD_INDEX_PATH}")

    print(f"\n=== Results — {args.version} ===")
    for k, v in metrics.items():
        print(f"  {k:25s}: {v}")
    print(f"\nCommit eval-dashboard/public/data/ to update the live dashboard.")


if __name__ == "__main__":
    main()
