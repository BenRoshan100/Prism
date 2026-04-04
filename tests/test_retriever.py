from server.retriever import retrieve_with_scores


REQUIRED_KEYS = {"content", "source", "similarity_score"}


def test_retrieve_returns_k_results():
    results = retrieve_with_scores("What is UPI?", k=5)
    assert len(results) == 5


def test_retrieve_results_have_required_keys():
    results = retrieve_with_scores("RBI repo rate", k=3)
    for r in results:
        for key in REQUIRED_KEYS:
            assert key in r, f"Missing key: {key}"


def test_similarity_scores_are_floats():
    results = retrieve_with_scores("Bajaj Finance AUM", k=3)
    for r in results:
        assert isinstance(r["similarity_score"], float)
