"""Unit tests for EvidenceFusion — dedup, normalization, scoring, determinism, edge cases."""

from __future__ import annotations

import pytest

from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.fusion.evidence_fusion import EvidenceFusion, _rank_normalize


def _mk_ev(
    chunk_id: str,
    score: float,
    method: str = "semantic",
    doc_id: str | None = None,
    provenance: dict | None = None,
    metadata: dict | None = None,
) -> Evidence:
    origin = "document/chunk" if method == "semantic" else "entity/relation"
    return Evidence(
        chunk_id=chunk_id,
        document_id=doc_id or f"doc_{chunk_id.split('_')[1]}",
        text=f"text for {chunk_id} from {method}",
        score=score,
        retrieval_method=method,
        evidence_origin=origin,
        provenance=provenance or {"source_chunk": chunk_id},
        metadata=metadata or {},
    )


def _mk_result(query: str, method: str, evidence: list[Evidence]) -> RetrievalResult:
    return RetrievalResult(
        query=query,
        evidence=evidence,
        retrieval_method=method,
        metadata={},
    )


# ── _rank_normalize ────────────────────────────────────────────


class TestRankNormalize:
    def test_rank_one_of_five(self):
        assert _rank_normalize(1, 5) == 1.0

    def test_rank_five_of_five(self):
        assert _rank_normalize(5, 5) == pytest.approx(0.2)

    def test_rank_three_of_five(self):
        assert _rank_normalize(3, 5) == pytest.approx(0.6)

    def test_out_of_range_returns_zero(self):
        assert _rank_normalize(0, 5) == 0.0
        assert _rank_normalize(6, 5) == 0.0
        assert _rank_normalize(-1, 5) == 0.0

    def test_zero_k_returns_zero(self):
        assert _rank_normalize(1, 0) == 0.0

    def test_monotonically_decreasing(self):
        vals = [_rank_normalize(r, 5) for r in range(1, 6)]
        assert vals == sorted(vals, reverse=True)


# ── Smoke ──────────────────────────────────────────────────────


class TestFusionSmoke:
    def test_returns_retrieval_result_with_hybrid_method(self):
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_001_001", 0.9)])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_002_001", 0.8, "structural")])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert isinstance(result, RetrievalResult)
        assert result.retrieval_method == "hybrid"
        assert result.query == "q"

    def test_preserves_query(self):
        sem = _mk_result("what is x?", "semantic", [])
        kag = _mk_result("what is x?", "structural", [])
        result = EvidenceFusion().fuse(sem, kag)
        assert result.query == "what is x?"

    def test_mismatched_queries_raises(self):
        sem = _mk_result("q1", "semantic", [])
        kag = _mk_result("q2", "structural", [])
        with pytest.raises(AssertionError):
            EvidenceFusion().fuse(sem, kag)


# ── Deduplication ──────────────────────────────────────────────


class TestDeduplication:
    def test_same_chunk_from_both_dedupes_to_one(self):
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_001_001", 0.9)])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_001_001", 0.8, "structural")])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        chunk_ids = [ev.chunk_id for ev in result.evidence]
        assert chunk_ids == ["chunk_001_001"]
        assert result.metadata["unique_chunks"] == 1
        assert result.metadata["agreement_count"] == 1

    def test_disjoint_chunks_are_all_kept(self):
        sem = _mk_result(
            "q",
            "semantic",
            [
                _mk_ev("chunk_001_001", 0.9),
                _mk_ev("chunk_002_001", 0.7),
            ],
        )
        kag = _mk_result(
            "q",
            "structural",
            [
                _mk_ev("chunk_003_001", 0.85, "structural"),
                _mk_ev("chunk_004_001", 0.75, "structural"),
            ],
        )
        result = EvidenceFusion().fuse(sem, kag, top_k=10)
        chunk_ids = {ev.chunk_id for ev in result.evidence}
        assert chunk_ids == {"chunk_001_001", "chunk_002_001", "chunk_003_001", "chunk_004_001"}
        assert result.metadata["unique_chunks"] == 4
        assert result.metadata["agreement_count"] == 0

    def test_dedup_rate_calculation(self):
        # 2 sem + 2 kag = 4 total; 1 overlap => 3 unique => dedup = 1 - 3/4 = 0.25
        sem = _mk_result(
            "q",
            "semantic",
            [
                _mk_ev("chunk_001_001", 0.9),
                _mk_ev("chunk_002_001", 0.7),
            ],
        )
        kag = _mk_result(
            "q",
            "structural",
            [
                _mk_ev("chunk_002_001", 0.85, "structural"),
                _mk_ev("chunk_003_001", 0.75, "structural"),
            ],
        )
        result = EvidenceFusion().fuse(sem, kag, top_k=10)
        assert result.metadata["dedup_rate"] == 0.25


# ── Fusion scoring ─────────────────────────────────────────────


class TestFusionScoring:
    def test_agreement_bonus_applied_when_both_sources_hit(self):
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_001_001", 0.9)])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_001_001", 0.8, "structural")])
        fusion = EvidenceFusion(semantic_weight=1.0, structural_weight=1.0, agreement_bonus=0.5)
        result = fusion.fuse(sem, kag, top_k=5)
        # rank 1 of 1 for both => norm=1.0 each; +0.5 bonus => 2.5
        assert result.evidence[0].score == pytest.approx(2.5)
        assert result.evidence[0].metadata["agreement"] is True

    def test_no_bonus_when_only_one_source(self):
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_001_001", 0.9)])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_002_001", 0.8, "structural")])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        for ev in result.evidence:
            assert ev.metadata["agreement"] is False
            assert ev.score == pytest.approx(1.0)

    def test_weight_scaling(self):
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_001_001", 0.9)])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_002_001", 0.8, "structural")])
        fusion = EvidenceFusion(semantic_weight=2.0, structural_weight=0.5, agreement_bonus=0.0)
        result = fusion.fuse(sem, kag, top_k=5)
        by_chunk = {ev.chunk_id: ev.score for ev in result.evidence}
        assert by_chunk["chunk_001_001"] == pytest.approx(2.0)  # 2.0 * 1.0
        assert by_chunk["chunk_002_001"] == pytest.approx(0.5)  # 0.5 * 1.0

    def test_metadata_captures_ranks_and_norm_scores(self):
        sem = _mk_result(
            "q",
            "semantic",
            [
                _mk_ev("chunk_001_001", 0.9),
                _mk_ev("chunk_002_001", 0.7),
            ],
        )
        kag = _mk_result(
            "q",
            "structural",
            [
                _mk_ev("chunk_002_001", 0.85, "structural"),
            ],
        )
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        by_chunk = {ev.chunk_id: ev for ev in result.evidence}

        ev1 = by_chunk["chunk_001_001"]
        assert ev1.metadata["semantic_rank"] == 1
        assert ev1.metadata["structural_rank"] is None
        assert ev1.metadata["fusion_sources"] == ["semantic"]

        ev2 = by_chunk["chunk_002_001"]
        assert ev2.metadata["semantic_rank"] == 2
        assert ev2.metadata["structural_rank"] == 1
        assert ev2.metadata["fusion_sources"] == ["semantic", "structural"]
        assert ev2.metadata["agreement"] is True


# ── Ranking & tie-breaking ─────────────────────────────────────


class TestRanking:
    def test_higher_fusion_score_ranks_first(self):
        # chunk_A: both sources rank 1  => 1.0+1.0+0.5 = 2.5
        # chunk_B: sem rank 2, no kag   => 0.5+0+0 = 0.5
        sem = _mk_result(
            "q",
            "semantic",
            [
                _mk_ev("chunk_A_001", 0.9),
                _mk_ev("chunk_B_001", 0.7),
            ],
        )
        kag = _mk_result(
            "q",
            "structural",
            [
                _mk_ev("chunk_A_001", 0.8, "structural"),
            ],
        )
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert result.evidence[0].chunk_id == "chunk_A_001"
        assert result.evidence[1].chunk_id == "chunk_B_001"

    def test_agreement_wins_tie_at_same_score(self):
        # Craft an exact score tie where one item agrees and the other does not.
        # chunk_AGREE: sem_r=1 (k=1 => 1.0) + kag_r=5 (k=5 => 0.2) + 0.5 bonus = 1.7
        # chunk_SOLO : sem_r=1 (k=1 => 1.0) only, no bonus (fill with disjoint kag noise) = 1.7?
        # Not achievable symmetrically without weights. Use custom weights instead:
        # w_sem=1, w_kag=0, bonus=0 => everything reduces to sem_norm only.
        # We want two items with sem_norm identical. Impossible within one sem list.
        # Cleanest tie: same fusion_score via different-source rank 1 with agreement flag flipped.
        # Use bonus=0 so no agreement lift; force tie by identical sem_norm=1.0 items.
        # chunk_X: only sem (rank 1 of 1, sem_norm=1.0) => 1.0
        # chunk_Y: only kag (rank 1 of 1, kag_norm=1.0) => 1.0
        # Neither agrees. Test degrades to chunk_id tiebreak. So instead, we test the
        # agreement-priority path via a hand-constructed scenario using bonus that
        # produces exact equality:
        # chunk_AGREE: sem_r=1 of 2 (0.5*1) + kag_r=1 of 2 (0.5*1) + 0.5 bonus = 1.5? -> 1.5
        # actually 1.0/2 = 0.5 each, so 0.5+0.5+0.5 = 1.5.
        # chunk_SOLO : sem_r=1 of 1 (1.0) only = 1.0. Not equal.
        # Symmetric equality with agreement vs no-agreement is only achievable with
        # asymmetric weights. Verified in test_ranking_uses_agreement_when_scores_equal below.
        # Here we simply assert deterministic ordering for a natural agreement scenario:
        sem = _mk_result(
            "q",
            "semantic",
            [
                _mk_ev("chunk_A_001", 0.9),
                _mk_ev("chunk_B_001", 0.7),
            ],
        )
        kag = _mk_result(
            "q",
            "structural",
            [
                _mk_ev("chunk_A_001", 0.8, "structural"),
                _mk_ev("chunk_B_001", 0.6, "structural"),
            ],
        )
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        # chunk_A: sem_r=1 (1.0) + kag_r=1 (1.0) + 0.5 = 2.5
        # chunk_B: sem_r=2 (0.5) + kag_r=2 (0.5) + 0.5 = 1.5
        assert result.evidence[0].chunk_id == "chunk_A_001"
        assert result.evidence[1].chunk_id == "chunk_B_001"

    def test_ranking_uses_agreement_when_scores_equal(self):
        # Construct exact score tie between an agreed item and a solo item.
        # Use weights: w_sem=1.0, w_kag=0.0, bonus=0.5.
        # chunk_AGREE: sem_r=1 of 1 (1.0)*1 + kag_r=1 of 1 (1.0)*0 + 0.5 = 1.5
        # chunk_SOLO : sem_r=1 of 1 (1.0)*1 only, no bonus = 1.0
        # Not equal. To force equality, use:
        # chunk_AGREE: sem_r=2 of 2 (0.5)*1 + kag_r=* (weight 0) + 0.5 = 1.0
        # chunk_SOLO : sem_r=1 of 2 (1.0)*1 only = 1.0  → tied at 1.0, agreement should win.
        sem = _mk_result(
            "q",
            "semantic",
            [
                _mk_ev("chunk_SOLO_001", 0.9),
                _mk_ev("chunk_AGREE_001", 0.7),
            ],
        )
        kag = _mk_result(
            "q",
            "structural",
            [
                _mk_ev("chunk_AGREE_001", 0.8, "structural"),
            ],
        )
        fusion = EvidenceFusion(semantic_weight=1.0, structural_weight=0.0, agreement_bonus=0.5)
        result = fusion.fuse(sem, kag, top_k=5)
        # Both score exactly 1.0; agreement should win tiebreak.
        assert result.evidence[0].score == pytest.approx(1.0)
        assert result.evidence[1].score == pytest.approx(1.0)
        assert result.evidence[0].chunk_id == "chunk_AGREE_001"
        assert result.evidence[1].chunk_id == "chunk_SOLO_001"

    def test_chunk_id_tiebreak_is_alphabetical(self):
        # Two disjoint singletons, both sem_r=1/k=1 or kag_r=1/k=1 → both score 1.0,
        # neither agrees, same best_rank=1 → chunk_id ascending decides.
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_Z_001", 0.5)])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_A_001", 0.5, "structural")])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert result.evidence[0].chunk_id == "chunk_A_001"
        assert result.evidence[1].chunk_id == "chunk_Z_001"

    def test_top_k_truncation(self):
        sem_evs = [_mk_ev(f"chunk_{i:03d}_001", 0.9 - i * 0.1) for i in range(1, 6)]
        sem = _mk_result("q", "semantic", sem_evs)
        kag = _mk_result("q", "structural", [])
        result = EvidenceFusion().fuse(sem, kag, top_k=2)
        assert len(result.evidence) == 2
        assert result.metadata["fused_count"] == 2

    def test_deterministic_across_runs(self):
        sem = _mk_result(
            "q",
            "semantic",
            [
                _mk_ev("chunk_001_001", 0.9),
                _mk_ev("chunk_002_001", 0.7),
                _mk_ev("chunk_003_001", 0.5),
            ],
        )
        kag = _mk_result(
            "q",
            "structural",
            [
                _mk_ev("chunk_002_001", 0.85, "structural"),
                _mk_ev("chunk_004_001", 0.75, "structural"),
            ],
        )
        fusion = EvidenceFusion()
        r1 = fusion.fuse(sem, kag, top_k=5)
        r2 = fusion.fuse(sem, kag, top_k=5)
        assert [ev.chunk_id for ev in r1.evidence] == [ev.chunk_id for ev in r2.evidence]
        assert [ev.score for ev in r1.evidence] == [ev.score for ev in r2.evidence]


# ── Provenance preservation ────────────────────────────────────


class TestProvenance:
    def test_structural_provenance_preserved_when_kag_only(self):
        kag_ev = _mk_ev(
            "chunk_001_001",
            0.8,
            "structural",
            provenance={"relation_id": "rel_001", "relation_type": "ACQUIRED"},
        )
        sem = _mk_result("q", "semantic", [])
        kag = _mk_result("q", "structural", [kag_ev])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert result.evidence[0].provenance.get("relation_id") == "rel_001"
        assert result.evidence[0].provenance.get("relation_type") == "ACQUIRED"

    def test_semantic_provenance_preserved_under_metadata_when_agreement(self):
        sem_ev = _mk_ev(
            "chunk_001_001",
            0.9,
            "semantic",
            provenance={"source_chunk": "chunk_001_001", "source_document": "doc_001"},
        )
        kag_ev = _mk_ev("chunk_001_001", 0.8, "structural", provenance={"relation_id": "rel_001"})
        sem = _mk_result("q", "semantic", [sem_ev])
        kag = _mk_result("q", "structural", [kag_ev])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        ev = result.evidence[0]
        assert ev.provenance.get("relation_id") == "rel_001"
        assert ev.metadata.get("semantic_provenance", {}).get("source_document") == "doc_001"

    def test_kag_path_metadata_preserved(self):
        kag_ev = _mk_ev(
            "chunk_001_001",
            0.8,
            "structural",
            metadata={"path_formatted": "A --REL--> B", "path_hops": 1},
        )
        sem = _mk_result("q", "semantic", [])
        kag = _mk_result("q", "structural", [kag_ev])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert result.evidence[0].metadata.get("path_formatted") == "A --REL--> B"
        assert result.evidence[0].metadata.get("path_hops") == 1


# ── Edge cases ─────────────────────────────────────────────────


class TestEdgeCases:
    def test_both_empty_returns_empty(self):
        sem = _mk_result("q", "semantic", [])
        kag = _mk_result("q", "structural", [])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert result.evidence == []
        assert result.metadata["unique_chunks"] == 0
        assert result.metadata["agreement_count"] == 0
        assert result.metadata["dedup_rate"] == 0.0

    def test_semantic_only(self):
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_001_001", 0.9)])
        kag = _mk_result("q", "structural", [])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert len(result.evidence) == 1
        assert result.evidence[0].chunk_id == "chunk_001_001"
        assert result.evidence[0].metadata["fusion_sources"] == ["semantic"]

    def test_structural_only(self):
        sem = _mk_result("q", "semantic", [])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_001_001", 0.8, "structural")])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert len(result.evidence) == 1
        assert result.evidence[0].metadata["fusion_sources"] == ["structural"]

    def test_result_contract_shape(self):
        sem = _mk_result("q", "semantic", [_mk_ev("chunk_001_001", 0.9)])
        kag = _mk_result("q", "structural", [_mk_ev("chunk_002_001", 0.8, "structural")])
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert isinstance(result, RetrievalResult)
        for ev in result.evidence:
            assert isinstance(ev, Evidence)
            assert isinstance(ev.chunk_id, str)
            assert isinstance(ev.score, float)
