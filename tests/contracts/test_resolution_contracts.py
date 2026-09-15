"""Unit tests for S9 resolution contracts."""

from dataclasses import FrozenInstanceError

import pytest

from kautilya.contracts.resolution import Claim, ResolutionResult, ResolutionStatus
from kautilya.contracts.retrieval import Evidence


def test_resolution_status_values():
    """Verify all expected enum values exist."""
    assert ResolutionStatus.CONSISTENT == "CONSISTENT"
    assert ResolutionStatus.AMBIGUOUS == "AMBIGUOUS"
    assert ResolutionStatus.CONFLICTING == "CONFLICTING"
    assert ResolutionStatus.INSUFFICIENT == "INSUFFICIENT"
    assert ResolutionStatus.UNSUPPORTED == "UNSUPPORTED"


def test_claim_immutability():
    """Verify Claim is frozen and cannot be mutated."""
    claim = Claim(
        subject="Nova Systems",
        predicate="FOUNDED",
        object="Rohan Kapoor",
        evidence_chunk_ids=("chunk_001_001",),
        source_document_ids=("doc_001",),
    )
    with pytest.raises(FrozenInstanceError):
        claim.subject = "Another Entity"  # type: ignore[misc]


def test_claim_to_dict():
    """Verify Claim.to_dict produces expected structure."""
    claim = Claim(
        subject="Vector Labs",
        predicate="ACQUIRED_BY",
        object="Nova Systems",
        evidence_chunk_ids=("chunk_002_001",),
        source_document_ids=("doc_002",),
        metadata={"confidence": 1.0},
    )
    d = claim.to_dict()
    assert d["subject"] == "Vector Labs"
    assert d["predicate"] == "ACQUIRED_BY"
    assert d["object"] == "Nova Systems"
    assert d["evidence_chunk_ids"] == ["chunk_002_001"]
    assert d["source_document_ids"] == ["doc_002"]
    assert d["metadata"] == {"confidence": 1.0}


def test_resolution_result_immutability():
    """Verify ResolutionResult is frozen."""
    res = ResolutionResult(
        query="Who founded Nova Systems?",
        status=ResolutionStatus.CONSISTENT,
        rationale="Single unambiguous claim found.",
    )
    with pytest.raises(FrozenInstanceError):
        res.status = ResolutionStatus.CONFLICTING  # type: ignore[misc]


def test_resolution_result_to_dict():
    """Verify ResolutionResult.to_dict produces expected structure."""
    ev = Evidence(
        chunk_id="chunk_001_001",
        document_id="doc_001",
        text="Nova Systems was founded by Rohan Kapoor.",
        score=0.95,
        retrieval_method="hybrid",
        evidence_origin="document/chunk",
    )
    claim = Claim(
        subject="Nova Systems",
        predicate="FOUNDED",
        object="Rohan Kapoor",
        evidence_chunk_ids=("chunk_001_001",),
        source_document_ids=("doc_001",),
    )
    res = ResolutionResult(
        query="Who founded Nova Systems?",
        status=ResolutionStatus.CONSISTENT,
        claims=(claim,),
        supporting_evidence=(ev,),
        conflicting_evidence=(),
        rationale="Corroborated by doc_001.",
        metadata={"num_claims": 1},
    )
    d = res.to_dict()
    assert d["query"] == "Who founded Nova Systems?"
    assert d["status"] == "CONSISTENT"
    assert len(d["claims"]) == 1
    assert d["claims"][0]["subject"] == "Nova Systems"
    assert len(d["supporting_evidence"]) == 1
    assert d["supporting_evidence"][0]["chunk_id"] == "chunk_001_001"
    assert len(d["conflicting_evidence"]) == 0
    assert d["rationale"] == "Corroborated by doc_001."
    assert d["metadata"]["num_claims"] == 1
