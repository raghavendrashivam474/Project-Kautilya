"""Unit tests for the vector index."""

from kautilya.retrieval.index import NumpyVectorIndex


def test_empty_index_returns_no_results():
    idx = NumpyVectorIndex()
    results = idx.search([1.0, 0.0, 0.0], top_k=3)
    assert results == []


def test_add_and_search():
    idx = NumpyVectorIndex()
    ids = ["a", "b", "c"]
    vectors = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.7071, 0.7071, 0.0],
    ]
    idx.add(ids, vectors)
    assert idx.size == 3

    results = idx.search([1.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0][0] == "a"
    assert results[0][1] > results[1][1]


def test_top_k_exceeds_index_size():
    idx = NumpyVectorIndex()
    idx.add(["x"], [[1.0, 0.0]])
    results = idx.search([1.0, 0.0], top_k=10)
    assert len(results) == 1


def test_deterministic_results():
    idx = NumpyVectorIndex()
    ids = ["a", "b", "c"]
    vectors = [[1.0, 0.0], [0.0, 1.0], [0.707, 0.707]]
    idx.add(ids, vectors)

    r1 = idx.search([1.0, 0.0], top_k=3)
    r2 = idx.search([1.0, 0.0], top_k=3)
    assert r1 == r2