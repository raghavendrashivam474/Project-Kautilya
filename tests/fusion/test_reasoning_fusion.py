"""Unit tests for S6 reasoning-aware evidence fusion.

Tests three-way fusion (semantic + structural + reasoning), safe degradation
when reasoning fails or is empty, agreement bonus logic across 3 sources,
provenance preservation, and deterministic tie-breaking.
"""

from __future__ import annotations

import pytest

from kautilya.contracts.reasoning import (
    Direction,
    ReasoningPlan,
    ReasoningStatus,
    ReasoningStep,
    ReasoningTrace,
)
from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.fusion.evidence_fusion import EvidenceFusion
from kautilya.reasoning.evidence_adapter import trace_to_retrieval_result


def _make_evidence(
    chunk_id: str,
    score: float,
    method: str = "semantic",
    origin: str = "document/chunk",
    doc_id: str = "doc_001",
    prov: dict | None = None,
    meta: dict | None = None,
) -> Evidence:
    return Evidence(
        chunk_id=chunk_id,
        document_id=doc_id,
        text=f"Text for {chunk_id}",
        score=score,
        retrieval_method=method,
        evidence_origin=origin,
        provenance=prov or {"chunk_id": chunk_id, "document_id": doc_id},
        metadata=meta or {},
    )


class TestThreeWayFusion:
    """Core S6 3-way fusion behavior."""

    @pytest.fixture
    def query(self) -> str:
        return "Who founded the company that acquired Vector Labs?"

    @pytest.fixture
    def sem_result(self, query: str) -> RetrievalResult:
        return RetrievalResult(
            query=query,
            retrieval_method="semantic",
            evidence=[
                _make_evidence("chunk_001_001", 0.85, method="semantic", doc_id="doc_001"),
                _make_evidence("chunk_005_001", 0.70, method="semantic", doc_id="doc_005"),
                _make_evidence("chunk_002_001", 0.60, method="semantic", doc_id="doc_002"),
            ],
        )

    @pytest.fixture
    def kag_result(self, query: str) -> RetrievalResult:
        return RetrievalResult(
            query=query,
            retrieval_method="structural",
            evidence=[
                _make_evidence("chunk_005_001", 0.833, method="structural", origin="entity/relation", doc_id="doc_005"),
                _make_evidence("chunk_002_001", 0.833, method="structural", origin="entity/relation", doc_id="doc_002"),
            ],
        )

    @pytest.fixture
    def reasoning_result(self, query: str) -> RetrievalResult:
        return RetrievalResult(
            query=query,
            retrieval_method="reasoning",
            evidence=[
                _make_evidence(
                    "chunk_001_001",
                    0.95,
                    method="reasoning",
                    origin="graph/reasoning",
                    doc_id="doc_001",
                    prov={"reasoning_hop": 2, "relation": "FOUNDED"},
                ),
                _make_evidence(
                    "chunk_005_001",
                    0.95,
                    method="reasoning",
                    origin="graph/reasoning",
                    doc_id="doc_005",
                    prov={"reasoning_hop": 1, "relation": "ACQUIRED"},
                ),
            ],
        )

    def test_three_way_fusion_elevates_multi_source_hit(
        self,
        sem_result: RetrievalResult,
        kag_result: RetrievalResult,
        reasoning_result: RetrievalResult,
    ) -> None:
        fusion = EvidenceFusion(
            semantic_weight=1.0,
            structural_weight=1.0,
            reasoning_weight=1.0,
            agreement_bonus=0.5,
        )
        fused = fusion.fuse(sem_result, kag_result, reasoning_result, top_k=5)

        assert fused.retrieval_method == "hybrid"
        assert len(fused.evidence) == 3
        assert fused.metadata["reasoning_participated"] is True
        assert fused.metadata["reasoning_count"] == 2

        top_chunks = fused.top_chunk_ids
        assert "chunk_005_001" in top_chunks
        assert "chunk_001_001" in top_chunks

    def test_fusion_sources_tracked_correctly(
        self,
        sem_result: RetrievalResult,
        kag_result: RetrievalResult,
        reasoning_result: RetrievalResult,
    ) -> None:
        fusion = EvidenceFusion()
        fused = fusion.fuse(sem_result, kag_result, reasoning_result)

        by_chunk = {ev.chunk_id: ev for ev in fused.evidence}

        assert set(by_chunk["chunk_005_001"].metadata["fusion_sources"]) == {
            "semantic",
            "structural",
            "reasoning",
        }
        assert set(by_chunk["chunk_001_001"].metadata["fusion_sources"]) == {
            "semantic",
            "reasoning",
        }
        assert set(by_chunk["chunk_002_001"].metadata["fusion_sources"]) == {
            "semantic",
            "structural",
        }

    def test_reasoning_provenance_preserved(
        self,
        sem_result: RetrievalResult,
        kag_result: RetrievalResult,
        reasoning_result: RetrievalResult,
    ) -> None:
        fusion = EvidenceFusion()
        fused = fusion.fuse(sem_result, kag_result, reasoning_result)

        by_chunk = {ev.chunk_id: ev for ev in fused.evidence}
        ev_001 = by_chunk["chunk_001_001"]

        assert "reasoning_hop" in ev_001.provenance or "reasoning_reasoning_hop" in ev_001.provenance or ev_001.provenance.get("reasoning_hop") == 2


class TestReasoningSafeDegradation:
    """Invariant 7: Reasoning failure must never break ordinary retrieval."""

    def test_none_reasoning_gives_s4_equivalence(self) -> None:
        sem = RetrievalResult(
            query="test query",
            evidence=[_make_evidence("c1", 0.9), _make_evidence("c2", 0.5)],
        )
        kag = RetrievalResult(
            query="test query",
            evidence=[_make_evidence("c2", 0.8), _make_evidence("c3", 0.4)],
        )
        fusion = EvidenceFusion()

        fused_s4 = fusion.fuse(sem, kag, reasoning_result=None)
        fused_implicit = fusion.fuse(sem, kag)

        assert fused_s4.top_chunk_ids == fused_implicit.top_chunk_ids
        assert fused_s4.scores == fused_implicit.scores
        assert fused_s4.metadata["reasoning_participated"] is False

    def test_empty_reasoning_gives_s4_equivalence(self) -> None:
        sem = RetrievalResult(
            query="test query",
            evidence=[_make_evidence("c1", 0.9), _make_evidence("c2", 0.5)],
        )
        kag = RetrievalResult(
            query="test query",
            evidence=[_make_evidence("c2", 0.8), _make_evidence("c3", 0.4)],
        )
        empty_rea = RetrievalResult(
            query="test query",
            evidence=[],
            retrieval_method="reasoning",
        )
        fusion = EvidenceFusion()

        fused_s4 = fusion.fuse(sem, kag, reasoning_result=None)
        fused_empty = fusion.fuse(sem, kag, reasoning_result=empty_rea)

        assert fused_s4.top_chunk_ids == fused_empty.top_chunk_ids
        assert fused_s4.scores == fused_empty.scores
        assert fused_empty.metadata["reasoning_participated"] is False

    def test_failed_trace_adapter_degrades_safely(self) -> None:
        plan = ReasoningPlan(
            query="Unknown entity query?",
            seed_entity_name="Nonexistent",
            steps=(
                ReasoningStep(
                    relation_type="ACQUIRED",
                    direction=Direction.OUTGOING,
                    hop_index=1,
                ),
            ),
        )
        failed_trace = ReasoningTrace(
            plan=plan,
            hops=(),
            terminal_entity_name=None,
            status=ReasoningStatus.ENTITY_RESOLUTION_FAILURE,
        )
        rea_result = trace_to_retrieval_result(failed_trace)
        assert len(rea_result.evidence) == 0

        sem = RetrievalResult(
            query="Unknown entity query?",
            evidence=[_make_evidence("c1", 0.9)],
        )
        kag = RetrievalResult(
            query="Unknown entity query?",
            evidence=[_make_evidence("c1", 0.8)],
        )

        fusion = EvidenceFusion()
        fused = fusion.fuse(sem, kag, rea_result)

        assert len(fused.evidence) == 1
        assert fused.top_chunk_ids == ["c1"]
        assert fused.metadata["reasoning_participated"] is False


class TestThreeWayTieBreaking:
    """Deterministic tie-breaking across 3 sources."""

    def test_sort_key_determinism(self) -> None:
        sem = RetrievalResult(
            query="deterministic test",
            evidence=[_make_evidence("chunk_b", 0.8), _make_evidence("chunk_a", 0.8)],
        )
        kag = RetrievalResult(
            query="deterministic test",
            evidence=[_make_evidence("chunk_b", 0.8), _make_evidence("chunk_a", 0.8)],
        )
        rea = RetrievalResult(
            query="deterministic test",
            evidence=[_make_evidence("chunk_b", 0.8), _make_evidence("chunk_a", 0.8)],
        )

        fusion = EvidenceFusion()
        fused1 = fusion.fuse(sem, kag, rea)
        fused2 = fusion.fuse(sem, kag, rea)

        assert fused1.top_chunk_ids == fused2.top_chunk_ids
        assert fused1.scores == fused2.scores
