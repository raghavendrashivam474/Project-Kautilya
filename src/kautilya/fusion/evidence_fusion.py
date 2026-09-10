"""Evidence Fusion module for Project Kautilya.

Consumes Semantic (RAG), Structural (KAG), and optionally Reasoning
RetrievalResults, deduplicates by chunk_id, applies rank-based
normalization, combines scores with an agreement bonus, and returns a
deterministically-ranked unified RetrievalResult.

Fusion algorithm (S4 baseline, S6 three-way extension):

    normalized_score(rank, k) = (k - rank + 1) / k

    fusion_score =
          semantic_weight   * normalized_semantic_score
        + structural_weight * normalized_structural_score
        + reasoning_weight  * normalized_reasoning_score   (S6, 0 when absent)
        + agreement_bonus   * (1 if found by 2+ sources else 0)

    sort_key = (-fusion_score, -agreement, best_rank, chunk_id)

When reasoning_result is None or empty, behavior is identical to S4.
No cross-source raw-score comparison. No randomization. No hash-order dependence.
"""

from __future__ import annotations

from typing import Any

from kautilya.contracts.retrieval import Evidence, RetrievalResult


def _rank_normalize(rank: int, k: int) -> float:
    """Convert a 1-indexed rank into a monotonic [0, 1] score.

    rank 1 -> 1.0, rank 2 -> (k-1)/k, ..., rank k -> 1/k.
    Ranks outside [1, k] map to 0.0.
    """
    if rank < 1 or rank > k or k <= 0:
        return 0.0
    return (k - rank + 1) / k


class EvidenceFusion:
    """Deterministic fusion layer for semantic, structural, and reasoning evidence."""

    def __init__(
        self,
        semantic_weight: float = 1.0,
        structural_weight: float = 1.0,
        reasoning_weight: float = 1.0,
        agreement_bonus: float = 0.5,
    ) -> None:
        self.semantic_weight = semantic_weight
        self.structural_weight = structural_weight
        self.reasoning_weight = reasoning_weight
        self.agreement_bonus = agreement_bonus

    # ── Public API ────────────────────────────────────────────

    def fuse(
        self,
        semantic_result: RetrievalResult,
        structural_result: RetrievalResult,
        reasoning_result: RetrievalResult | None = None,
        top_k: int = 5,
    ) -> RetrievalResult:
        """Fuse semantic, structural, and optionally reasoning results.

        When reasoning_result is None or has empty evidence, this method
        produces output identical to the S4 two-way fusion baseline.
        """
        assert semantic_result.query == structural_result.query, (
            f"Queries must match for fusion. "
            f"Got: '{semantic_result.query}' and '{structural_result.query}'"
        )

        # S6: reasoning participates only when it produced evidence
        has_reasoning = reasoning_result is not None and len(reasoning_result.evidence) > 0
        if has_reasoning:
            assert reasoning_result.query == semantic_result.query, (
                f"Reasoning query must match. "
                f"Got: '{reasoning_result.query}' and '{semantic_result.query}'"
            )

        sem_k = len(semantic_result.evidence)
        kag_k = len(structural_result.evidence)
        rea_k = len(reasoning_result.evidence) if has_reasoning else 0

        # Build per-source rank tables keyed by chunk_id (1-indexed).
        sem_by_chunk: dict[str, tuple[int, Evidence]] = {}
        for rank, ev in enumerate(semantic_result.evidence, start=1):
            if ev.chunk_id not in sem_by_chunk:
                sem_by_chunk[ev.chunk_id] = (rank, ev)

        kag_by_chunk: dict[str, tuple[int, Evidence]] = {}
        for rank, ev in enumerate(structural_result.evidence, start=1):
            if ev.chunk_id not in kag_by_chunk:
                kag_by_chunk[ev.chunk_id] = (rank, ev)

        rea_by_chunk: dict[str, tuple[int, Evidence]] = {}
        if has_reasoning:
            for rank, ev in enumerate(reasoning_result.evidence, start=1):
                if ev.chunk_id not in rea_by_chunk:
                    rea_by_chunk[ev.chunk_id] = (rank, ev)

        # Union of chunk IDs.
        all_chunk_ids = set(sem_by_chunk.keys()) | set(kag_by_chunk.keys())
        if has_reasoning:
            all_chunk_ids |= set(rea_by_chunk.keys())

        # Build fused evidence, one per unique chunk_id.
        candidates: list[tuple[float, int, int, str, Evidence]] = []
        agreement_count = 0

        for chunk_id in all_chunk_ids:
            sem_hit = sem_by_chunk.get(chunk_id)
            kag_hit = kag_by_chunk.get(chunk_id)
            rea_hit = rea_by_chunk.get(chunk_id) if has_reasoning else None

            sem_rank = sem_hit[0] if sem_hit else None
            kag_rank = kag_hit[0] if kag_hit else None
            rea_rank = rea_hit[0] if rea_hit else None

            sem_norm = _rank_normalize(sem_rank, sem_k) if sem_rank else 0.0
            kag_norm = _rank_normalize(kag_rank, kag_k) if kag_rank else 0.0
            rea_norm = _rank_normalize(rea_rank, rea_k) if rea_rank else 0.0

            # Agreement: found by 2+ sources (generalizes S4 binary check)
            source_count = sum(1 for h in (sem_hit, kag_hit, rea_hit) if h is not None)
            agreement = 1 if source_count >= 2 else 0
            if agreement:
                agreement_count += 1

            fusion_score = (
                self.semantic_weight * sem_norm
                + self.structural_weight * kag_norm
                + self.reasoning_weight * rea_norm
                + self.agreement_bonus * agreement
            )

            best_rank = min(r for r in (sem_rank, kag_rank, rea_rank) if r is not None)

            fused_ev = self._build_fused_evidence(
                chunk_id=chunk_id,
                sem_hit=sem_hit,
                kag_hit=kag_hit,
                rea_hit=rea_hit,
                sem_rank=sem_rank,
                kag_rank=kag_rank,
                rea_rank=rea_rank,
                sem_norm=sem_norm,
                kag_norm=kag_norm,
                rea_norm=rea_norm,
                fusion_score=fusion_score,
                agreement=bool(agreement),
                source_count=source_count,
            )

            candidates.append((fusion_score, agreement, best_rank, chunk_id, fused_ev))

        # Deterministic sort: (-fusion_score, -agreement, best_rank, chunk_id)
        candidates.sort(key=lambda t: (-t[0], -t[1], t[2], t[3]))

        fused_evidence = [c[4] for c in candidates[:top_k]]

        unique_chunks = len(all_chunk_ids)
        total_input = sem_k + kag_k + rea_k
        dedup_rate = round(1.0 - (unique_chunks / total_input), 4) if total_input > 0 else 0.0

        fusion_weights: dict[str, float] = {
            "semantic": self.semantic_weight,
            "structural": self.structural_weight,
            "agreement_bonus": self.agreement_bonus,
        }
        if has_reasoning:
            fusion_weights["reasoning"] = self.reasoning_weight

        return RetrievalResult(
            query=semantic_result.query,
            evidence=fused_evidence,
            retrieval_method="hybrid",
            metadata={
                "semantic_count": sem_k,
                "structural_count": kag_k,
                "reasoning_count": rea_k,
                "reasoning_participated": has_reasoning,
                "unique_chunks": unique_chunks,
                "agreement_count": agreement_count,
                "dedup_rate": dedup_rate,
                "fused_count": len(fused_evidence),
                "top_k": top_k,
                "fusion_weights": fusion_weights,
                "normalization": "rank_based",
            },
        )

    # ── Internal helpers ──────────────────────────────────────

    def _build_fused_evidence(
        self,
        *,
        chunk_id: str,
        sem_hit: tuple[int, Evidence] | None,
        kag_hit: tuple[int, Evidence] | None,
        rea_hit: tuple[int, Evidence] | None,
        sem_rank: int | None,
        kag_rank: int | None,
        rea_rank: int | None,
        sem_norm: float,
        kag_norm: float,
        rea_norm: float,
        fusion_score: float,
        agreement: bool,
        source_count: int,
    ) -> Evidence:
        """Build a fused Evidence, preferring structural as the provenance base."""
        # Decide method label (same priority as S4, reasoning added)
        if agreement:
            method_label = "hybrid"
            origin_label = "hybrid"
        elif kag_hit:
            method_label = "structural"
            origin_label = "entity/relation"
        elif rea_hit:
            method_label = "reasoning"
            origin_label = "graph/reasoning"
        else:
            method_label = "semantic"
            origin_label = "document/chunk"

        # Structural > reasoning > semantic as provenance base
        base_ev = kag_hit[1] if kag_hit else rea_hit[1] if rea_hit else sem_hit[1]

        # Prefer the longest non-empty text
        texts = []
        if sem_hit:
            texts.append(sem_hit[1].text)
        if kag_hit:
            texts.append(kag_hit[1].text)
        if rea_hit:
            texts.append(rea_hit[1].text)
        text = max(texts, key=len) if texts else ""

        # Merge provenance without silent overwrite (S4 order preserved)
        merged_provenance: dict[str, Any] = {}
        if kag_hit:
            merged_provenance.update(kag_hit[1].provenance)
        if rea_hit:
            for k, v in rea_hit[1].provenance.items():
                if k in merged_provenance and merged_provenance[k] != v:
                    merged_provenance[f"reasoning_{k}"] = v
                else:
                    merged_provenance.setdefault(k, v)
        if sem_hit:
            for k, v in sem_hit[1].provenance.items():
                if k in merged_provenance and merged_provenance[k] != v:
                    merged_provenance[f"semantic_{k}"] = v
                else:
                    merged_provenance.setdefault(k, v)

        # Build merged metadata (S4 structure preserved)
        merged_metadata: dict[str, Any] = {}
        if kag_hit:
            merged_metadata.update(kag_hit[1].metadata)
        if rea_hit:
            for k, v in rea_hit[1].metadata.items():
                if k not in merged_metadata:
                    merged_metadata[f"reasoning_{k}"] = v
        if sem_hit:
            merged_metadata["semantic_provenance"] = dict(sem_hit[1].provenance)

        # Fusion bookkeeping
        fusion_sources: list[str] = []
        if sem_hit:
            fusion_sources.append("semantic")
        if kag_hit:
            fusion_sources.append("structural")
        if rea_hit:
            fusion_sources.append("reasoning")

        merged_metadata.update(
            {
                "fusion_sources": fusion_sources,
                "semantic_rank": sem_rank,
                "structural_rank": kag_rank,
                "reasoning_rank": rea_rank,
                "semantic_score": (round(sem_hit[1].score, 4) if sem_hit else None),
                "structural_score": (round(kag_hit[1].score, 4) if kag_hit else None),
                "reasoning_score": (round(rea_hit[1].score, 4) if rea_hit else None),
                "semantic_norm_score": round(sem_norm, 4),
                "structural_norm_score": round(kag_norm, 4),
                "reasoning_norm_score": round(rea_norm, 4),
                "fusion_score": round(fusion_score, 4),
                "agreement": agreement,
                "source_count": source_count,
            }
        )

        return Evidence(
            chunk_id=chunk_id,
            document_id=base_ev.document_id,
            text=text,
            score=round(fusion_score, 4),
            retrieval_method=method_label,
            evidence_origin=origin_label,
            provenance=merged_provenance,
            metadata=merged_metadata,
        )
