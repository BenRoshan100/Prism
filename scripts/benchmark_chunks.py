"""
Benchmark Precision@K across different chunk sizes.
Wipes ChromaDB, re-ingests at each chunk size, runs eval, plots results.

Usage:
  python scripts/benchmark_chunks.py
  python scripts/benchmark_chunks.py --sizes 200 300 500 750 1000
  python scripts/benchmark_chunks.py --data-dir data/raw --k 5
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from server.ingest import load_documents, chunk_documents, embed_and_store
from server.eval.precision import run_batch_precision_eval
from server.utils import load_config


CHROMA_DIR = Path("./chroma_db")


def run_at_chunk_size(data_dir: str, chunk_size: int, chunk_overlap: int, eval_path: str, k: int):
    """Wipe ChromaDB, re-ingest at given chunk_size, run Precision@K."""
    # Wipe
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)

    # Ingest
    documents = load_documents(data_dir)
    chunks = chunk_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    embed_and_store(chunks)

    chunk_count = len(chunks)

    # Eval
    results = run_batch_precision_eval(eval_path, k=k)

    return {
        "chunk_size": chunk_size,
        "chunk_count": chunk_count,
        "mean_precision": results["mean_precision_at_k"],
        "per_query": results["per_query_results"],
    }


def plot_results(results: list[dict], output_path: str):
    """Generate a PNG chart showing Precision@K vs chunk size."""
    sizes = [r["chunk_size"] for r in results]
    precisions = [r["mean_precision"] for r in results]
    chunk_counts = [r["chunk_count"] for r in results]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Precision bars
    bars = ax1.bar(
        [str(s) for s in sizes],
        precisions,
        color=["#22c55e" if p >= 0.7 else "#eab308" if p >= 0.5 else "#ef4444" for p in precisions],
        edgecolor="white",
        linewidth=1.5,
    )
    ax1.set_xlabel("Chunk Size (characters)", fontsize=12)
    ax1.set_ylabel("Mean Precision@K", fontsize=12, color="#1f2937")
    ax1.set_ylim(0, 1.05)
    ax1.tick_params(axis="y", labelcolor="#1f2937")

    # Add value labels on bars
    for bar, p, cc in zip(bars, precisions, chunk_counts):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{p:.2f}\n({cc} chunks)",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    # Chunk count line on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(
        [str(s) for s in sizes],
        chunk_counts,
        color="#6366f1",
        marker="o",
        linewidth=2,
        label="Chunk count",
    )
    ax2.set_ylabel("Total Chunks", fontsize=12, color="#6366f1")
    ax2.tick_params(axis="y", labelcolor="#6366f1")

    ax1.set_title("Precision@K vs Chunk Size — FinRAG Benchmark", fontsize=14, fontweight="bold", pad=15)
    ax2.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nChart saved to: {output_path}")


def main():
    config = load_config()
    eval_config = config.get("eval", {})
    default_eval_path = eval_config.get("ground_truth_path", "data/ground_truth/eval_pairs.json")
    default_k = eval_config.get("precision_k", 5)

    parser = argparse.ArgumentParser(description="Benchmark Precision@K across chunk sizes")
    parser.add_argument("--sizes", nargs="+", type=int, default=[200, 300, 500, 750, 1000],
                        help="Chunk sizes to test")
    parser.add_argument("--overlap-ratio", type=float, default=0.1,
                        help="Overlap as fraction of chunk size (default 0.1)")
    parser.add_argument("--data-dir", type=str, default="data/raw",
                        help="Directory containing documents")
    parser.add_argument("--eval-path", type=str, default=default_eval_path,
                        help="Path to eval_pairs.json")
    parser.add_argument("--k", type=int, default=default_k, help="K for Precision@K")
    args = parser.parse_args()

    print(f"Benchmarking chunk sizes: {args.sizes}")
    print(f"Data: {args.data_dir} | Eval: {args.eval_path} | K={args.k}")
    print("=" * 60)

    results = []
    for size in args.sizes:
        overlap = int(size * args.overlap_ratio)
        print(f"\n--- Chunk size: {size} (overlap: {overlap}) ---")
        result = run_at_chunk_size(args.data_dir, size, overlap, args.eval_path, args.k)
        results.append(result)
        print(f"  Chunks: {result['chunk_count']} | Mean P@{args.k}: {result['mean_precision']:.4f}")

    # Summary table
    print("\n" + "=" * 60)
    print(f"{'Chunk Size':>12} | {'Chunks':>8} | {'Mean P@K':>10}")
    print("-" * 40)
    for r in results:
        print(f"{r['chunk_size']:>12} | {r['chunk_count']:>8} | {r['mean_precision']:>10.4f}")

    # Best
    best = max(results, key=lambda r: r["mean_precision"])
    print(f"\nBest: chunk_size={best['chunk_size']} with P@{args.k}={best['mean_precision']:.4f}")

    # Save chart
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"benchmark_precision_{timestamp}.png"
    plot_results(results, output_path)

    # Restore original chunk size
    original_size = config.get("chunking", {}).get("chunk_size", 500)
    original_overlap = config.get("chunking", {}).get("chunk_overlap", 50)
    print(f"\nRestoring original config: chunk_size={original_size}, overlap={original_overlap}")
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    documents = load_documents(args.data_dir)
    chunks = chunk_documents(documents, chunk_size=original_size, chunk_overlap=original_overlap)
    embed_and_store(chunks)
    print(f"ChromaDB restored with {len(chunks)} chunks")


if __name__ == "__main__":
    main()
