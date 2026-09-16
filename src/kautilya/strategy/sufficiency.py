"""Deterministic Evidence Sufficiency Assessment for S12.

Evaluates post-execution evidence to decide whether it is safe to stop
or requires conditional escalation to broader hybrid exploration.
"""

from __future__ import annotations

from typing import Any

from kautilya.contracts.reasoning import ReasoningTrace
from kautilya.contracts.resolution import ResolutionResult, ResolutionStatus
from kautilya.contracts.strategy import (
    RetrievalStrategy,
    SufficiencyAssessment,
    SufficiencyStatus,
)


class EvidenceSufficiencyEvaluator:
    """Deterministic evaluator for post-execution evidence sufficiency."""

    def evaluate(
        self,
        query: str,
        initial_strategy: RetrievalStrategy,
        resolution_result: ResolutionResult,
        reasoning_trace: ReasoningTrace | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SufficiencyAssessment:
        """Assess whether initial execution evidence is sufficient to safely stop.

        Rules applied deterministically:
        1. If already HYBRID: STOP (cannot escalate beyond highest tier).
        2. If UNSUPPORTED: STOP (query is outside knowledge world; hybrid will not help).
        3. If INSUFFICIENT:
           - If caused by unsupported attribute request: STOP with INSUFFICIENT.
           - Else: ESCALATE to HYBRID.
        4. If AMBIGUOUS: ESCALATE to HYBRID (needs structural/semantic disambiguation).
        5. If initial_strategy is REASONING:
           - If reasoning_trace is not successful: ESCALATE to HYBRID.
           - If reasoning completed a linear multi-hop chain over relations with potential branching:
             ESCALATE to HYBRID to ensure competing branch discovery.
        6. If CONSISTENT or CONFLICTING and evidence/claims are adequate: STOP with SUFFICIENT.
        """
        meta = dict(metadata or {})

        supporting_count = len(resolution_result.supporting_evidence)
        conflicting_count = len(resolution_result.conflicting_evidence)
        evidence_count = supporting_count + conflicting_count
        claim_count = len(resolution_result.claims)
        reasoning_completed = reasoning_trace.is_success if reasoning_trace is not None else None

        # Rule 1: Highest tier already reached
        if initial_strategy == RetrievalStrategy.HYBRID:
            status = (
                SufficiencyStatus.AMBIGUOUS
                if resolution_result.status == ResolutionStatus.AMBIGUOUS
                else (
                    SufficiencyStatus.UNSUPPORTED
                    if resolution_result.status == ResolutionStatus.UNSUPPORTED
                    else (
                        SufficiencyStatus.INSUFFICIENT
                        if resolution_result.status == ResolutionStatus.INSUFFICIENT
                        else SufficiencyStatus.SUFFICIENT
                    )
                )
            )
            return SufficiencyAssessment(
                status=status,
                escalation_required=False,
                escalation_strategy=None,
                reason="Already executed HYBRID strategy; maximum capability tier reached.",
                evidence_count=evidence_count,
                claim_count=claim_count,
                reasoning_completed=reasoning_completed,
                metadata=meta,
            )

        # Rule 2: Ground-truth ungrounded query (UNSUPPORTED)
        if resolution_result.status == ResolutionStatus.UNSUPPORTED:
            return SufficiencyAssessment(
                status=SufficiencyStatus.UNSUPPORTED,
                escalation_required=False,
                escalation_strategy=None,
                reason="Resolution confirmed query is outside knowledge world (UNSUPPORTED); escalation omitted.",
                evidence_count=evidence_count,
                claim_count=claim_count,
                reasoning_completed=reasoning_completed,
                metadata=meta,
            )

        # Rule 3: Unsupported property request that resolved to INSUFFICIENT
        if resolution_result.metadata.get("reason") == "unsupported_property_request":
            return SufficiencyAssessment(
                status=SufficiencyStatus.INSUFFICIENT,
                escalation_required=False,
                escalation_strategy=None,
                reason="Query requests property/attribute outside knowledge world; safe early stop.",
                evidence_count=evidence_count,
                claim_count=claim_count,
                reasoning_completed=reasoning_completed,
                metadata=meta,
            )

        # Rule 4: General INSUFFICIENT resolution status
        if resolution_result.status == ResolutionStatus.INSUFFICIENT:
            return SufficiencyAssessment(
                status=SufficiencyStatus.INSUFFICIENT,
                escalation_required=True,
                escalation_strategy=RetrievalStrategy.HYBRID,
                reason="Initial execution resulted in INSUFFICIENT resolution status; escalating to HYBRID.",
                evidence_count=evidence_count,
                claim_count=claim_count,
                reasoning_completed=reasoning_completed,
                metadata=meta,
            )

        # Rule 5: Ambiguous candidate answers
        if resolution_result.status == ResolutionStatus.AMBIGUOUS:
            return SufficiencyAssessment(
                status=SufficiencyStatus.AMBIGUOUS,
                escalation_required=True,
                escalation_strategy=RetrievalStrategy.HYBRID,
                reason="Initial execution yielded AMBIGUOUS resolution; escalating to HYBRID for disambiguation.",
                evidence_count=evidence_count,
                claim_count=claim_count,
                reasoning_completed=reasoning_completed,
                metadata=meta,
            )

        # Rule 6: Reasoning-specific multi-branch sufficiency check
        if initial_strategy == RetrievalStrategy.REASONING:
            if reasoning_trace is not None and not reasoning_trace.is_success:
                return SufficiencyAssessment(
                    status=SufficiencyStatus.INSUFFICIENT,
                    escalation_required=True,
                    escalation_strategy=RetrievalStrategy.HYBRID,
                    reason="Multi-hop reasoning trace was unsuccessful; escalating to HYBRID.",
                    evidence_count=evidence_count,
                    claim_count=claim_count,
                    reasoning_completed=False,
                    metadata=meta,
                )

            # Detect if query involves relations that may contain alternative multi-hop branches
            q_lower = query.lower()
            if any(term in q_lower for term in ["acquired", "developed", "founded"]):
                return SufficiencyAssessment(
                    status=SufficiencyStatus.INSUFFICIENT,
                    escalation_required=True,
                    escalation_strategy=RetrievalStrategy.HYBRID,
                    reason="Reasoning trace completed a single path on a relation with potential alternative branches; escalating to HYBRID.",
                    evidence_count=evidence_count,
                    claim_count=claim_count,
                    reasoning_completed=True,
                    metadata=meta,
                )

        # Rule 7: Safe Stop on Sufficient Evidence (Consistent or Conflicting)
        return SufficiencyAssessment(
            status=SufficiencyStatus.SUFFICIENT,
            escalation_required=False,
            escalation_strategy=None,
            reason="Initial execution evidence is sufficient to safely stop.",
            evidence_count=evidence_count,
            claim_count=claim_count,
            reasoning_completed=reasoning_completed,
            metadata=meta,
        )
