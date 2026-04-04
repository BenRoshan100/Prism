import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.eval.precision import run_batch_precision_eval
from server.utils import load_config


def main():
    config = load_config()
    default_path = config.get("eval", {}).get("ground_truth_path", "data/ground_truth/eval_pairs.json")
    default_k = config.get("eval", {}).get("precision_k", 5)

    parser = argparse.ArgumentParser(description="Run batch Precision@K evaluation")
    parser.add_argument("--queries", type=str, default=default_path, help="Path to eval_pairs.json")
    parser.add_argument("--k", type=int, default=default_k, help="K for Precision@K")
    args = parser.parse_args()

    print(f"Running Precision@{args.k} eval on queries from {args.queries}...")
    results = run_batch_precision_eval(args.queries, k=args.k)

    print(f"\nMean Precision@{args.k}: {results['mean_precision_at_k']}")
    print(f"\nPer-query breakdown:")
    for r in results["per_query_results"]:
        print(f"  P@{args.k}={r['precision_at_k']:.2f} | {r['query'][:70]}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"eval_results_{timestamp}.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
