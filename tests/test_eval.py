from server.eval.precision import compute_precision_at_k, run_batch_precision_eval_multi_k
from server.eval.faithfulness import score_faithfulness


def test_precision_at_k_returns_float_between_0_and_1():
    chunks = [
        {"source": "npci_upi_report_2024.txt", "content": "UPI volume was 131 billion"},
        {"source": "npci_upi_report_2024.txt", "content": "UPI Lite launched"},
        {"source": "rbi_annual_report_2024.txt", "content": "GDP growth was 7.6%"},
        {"source": "npci_upi_report_2024.txt", "content": "PhonePe 47% market share"},
        {"source": "bajaj_finance_q3_2024_transcript.txt", "content": "AUM grew 35%"},
    ]
    ground_truth = {
        "relevant_sources": ["npci_upi_report_2024.txt"],
        "relevant_chunk_keywords": ["131 billion", "UPI volume"],
    }
    precision = compute_precision_at_k("UPI volume", chunks, ground_truth, k=5)
    assert isinstance(precision, float)
    assert 0.0 <= precision <= 1.0


def test_precision_perfect_score():
    chunks = [
        {"source": "a.txt", "content": "relevant keyword here"},
        {"source": "a.txt", "content": "another relevant keyword"},
    ]
    ground_truth = {
        "relevant_sources": ["a.txt"],
        "relevant_chunk_keywords": ["keyword"],
    }
    precision = compute_precision_at_k("test", chunks, ground_truth, k=2)
    assert precision == 1.0


def test_precision_zero_score():
    chunks = [
        {"source": "wrong.txt", "content": "nothing relevant"},
        {"source": "wrong.txt", "content": "still nothing"},
    ]
    ground_truth = {
        "relevant_sources": ["correct.txt"],
        "relevant_chunk_keywords": ["specific term"],
    }
    precision = compute_precision_at_k("test", chunks, ground_truth, k=2)
    assert precision == 0.0


def test_multi_k_eval_returns_one_result_per_k(monkeypatch):
    def fake_single(eval_pairs_path, k=5):
        return {"mean_precision_at_k": round(k / 10, 4), "per_query_results": []}

    monkeypatch.setattr("server.eval.precision.run_batch_precision_eval", fake_single)

    results = run_batch_precision_eval_multi_k("dummy.json", ks=[1, 3, 5])

    assert list(results.keys()) == ["precision@1", "precision@3", "precision@5"]
    assert results["precision@1"]["mean_precision_at_k"] == 0.1
    assert results["precision@3"]["mean_precision_at_k"] == 0.3
    assert results["precision@5"]["mean_precision_at_k"] == 0.5


def test_faithfulness_returns_dict_with_score():
    chunks = [{"content": "UPI processed 131 billion transactions in FY2024."}]
    answer = "UPI processed 131 billion transactions in FY2024."
    result = score_faithfulness(answer, chunks)
    assert isinstance(result, dict)
    assert "score" in result
    assert "reason" in result
    assert "raw_response" in result


def test_faithfulness_handles_empty_chunks():
    result = score_faithfulness("Some answer", [])
    assert isinstance(result, dict)
    assert "score" in result
