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
        3. If INSUFFICIENT: ESCALATE to HYBRID.
        4. If AMBIGUOUS: ESCALATE to HYBRID (needs structural/semantic disambiguation).
        5. If initial_strategy is REASONING and reasoning_trace is not successful: ESCALATE to HYBRID.
        6. If CONSISTENT and evidence/claims are adequate: STOP with SUFFICIENT.
        """
        meta = dict(metadata or {})
        
        # Calculate total evidence from supporting and conflicting lists
        supporting_count = len(resolution_result.supporting_evidence)
        conflicting_count = len(resolution_result.conflicting_evidence)
        evidence_count = supporting_count + conflicting_count
        
        claim_count = len(resolution_result.claims)
        reasoning_completed = reasoning_trace.is_success if reasoning_trace is not None else None

        # Rule 1: Highest tier already reached
        if initial_strategy == RetrievalStrategy.HYBRID:
            return SufficiencyAssessment(
                status=SufficiencyStatus.SUFFICIENT
                if resolution_result.status == ResolutionStatus.CONSISTENT
                else SufficiencyStatus(resolution_result.status.value.lower()),
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

        # Rule 3: Resolution explicitly marked INSUFFICIENT
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

        # Rule 4: Ambiguous candidate answers
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

        # Rule 5: Incomplete reasoning trace
        if initial_strategy == RetrievalStrategy.REASONING and reasoning_trace is not None and not reasoning_trace.is_success:
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

        # Rule 6: Safe Consistent Stop
        return SufficiencyAssessment(
            status=SufficiencyStatus.SUFFICIENT,
            escalation_required=False,
            escalation_strategy=None,
            reason="Initial execution evidence is consistent and sufficient to safely stop.",
            evidence_count=evidence_count,
            claim_count=claim_count,
            reasoning_completed=reasoning_completed,
            metadata=meta,
        )
