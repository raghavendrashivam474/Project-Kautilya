"""Unit tests for retrieval contracts."""

from dataclasses import FrozenInstanceError

import pytest

from kautilya.contracts.retrieval import Evidence, RetrievalResult


def test_evidence_creation_and_immutability():
    ev = Evidence(
        chunk_id="chunk_001_001",
        document_id="doc_001",
        text="Sample evidence text.",
        score=0.92,
        retrieval_method="semantic",
        evidence_origin="document/chunk",
        provenance={"source_document": "doc_001.txt"},
    )
    assert ev.chunk_id == "chunk_001_001"
    assert ev.score == 0.92
    assert ev.retrieval_method == "semantic"
    assert ev.evidence_origin == "document/chunk"

    # Verify frozen immutability raises dataclasses.FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        ev.score = 0.5  # type: ignore[misc]


def test_retrieval_result_properties():
    ev1 = Evidence(chunk_id="c1", document_id="d1", text="text 1", score=0.9)
    ev2 = Evidence(chunk_id="c2", document_id="d2", text="text 2", score=0.7)

    res = RetrievalResult(
        query="What is X?",
        evidence=[ev1, ev2],
        retrieval_method="semantic",
        metadata={"model": "test-model", "top_k": 2},
    )

    assert res.query == "What is X?"
    assert res.top_chunk_ids == ["c1", "c2"]
    assert res.scores == [0.9, 0.7]
    assert len(res.evidence) == 2

    d = res.to_dict()
    assert d["query"] == "What is X?"
    assert len(d["evidence"]) == 2
    assert d["evidence"][0]["chunk_id"] == "c1"
    assert d["metadata"]["model"] == "test-model"