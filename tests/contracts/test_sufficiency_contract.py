"""Unit tests for S12 Evidence Sufficiency contracts."""

from __future__ import annotations

import pytest

from kautilya.contracts.strategy import (
    RetrievalStrategy,
    SufficiencyAssessment,
    SufficiencyStatus,
)


def test_sufficiency_status_values() -> None:
    """Ensure SufficiencyStatus has expected enum variants."""
    assert SufficiencyStatus.SUFFICIENT.value == "sufficient"
    assert SufficiencyStatus.INSUFFICIENT.value == "insufficient"
    assert SufficiencyStatus.AMBIGUOUS.value == "ambiguous"
    assert SufficiencyStatus.UNSUPPORTED.value == "unsupported"


def test_sufficiency_assessment_creation_sufficient() -> None:
    """Ensure SufficiencyAssessment creates a valid sufficient outcome."""
    assessment = SufficiencyAssessment(
        status=SufficiencyStatus.SUFFICIENT,
        escalation_required=False,
        escalation_strategy=None,
        reason="Evidence directly supports query with complete reasoning.",
        evidence_count=2,
        claim_count=1,
        reasoning_completed=True,
    )
    assert assessment.status == SufficiencyStatus.SUFFICIENT
    assert not assessment.escalation_required
    assert assessment.escalation_strategy is None
    assert assessment.evidence_count == 2
    assert assessment.claim_count == 1
    assert assessment.reasoning_completed is True
    
    d = assessment.to_dict()
    assert d["status"] == "sufficient"
    assert d["escalation_required"] is False
    assert d["escalation_strategy"] is None
    assert d["reason"] == "Evidence directly supports query with complete reasoning."


def test_sufficiency_assessment_creation_escalate() -> None:
    """Ensure SufficiencyAssessment creates a valid escalation outcome."""
    assessment = SufficiencyAssessment(
        status=SufficiencyStatus.INSUFFICIENT,
        escalation_required=True,
        escalation_strategy=RetrievalStrategy.HYBRID,
        reason="Initial structural retrieval yielded insufficient relation coverage.",
        evidence_count=0,
        claim_count=0,
        reasoning_completed=None,
    )
    assert assessment.status == SufficiencyStatus.INSUFFICIENT
    assert assessment.escalation_required is True
    assert assessment.escalation_strategy == RetrievalStrategy.HYBRID
    assert assessment.to_dict()["escalation_strategy"] == "hybrid"


def test_sufficiency_assessment_immutability() -> None:
    """Ensure SufficiencyAssessment is frozen."""
    assessment = SufficiencyAssessment(
        status=SufficiencyStatus.SUFFICIENT,
        escalation_required=False,
        escalation_strategy=None,
        reason="Complete",
        evidence_count=1,
        claim_count=1,
    )
    with pytest.raises((AttributeError, TypeError)):
        assessment.status = SufficiencyStatus.INSUFFICIENT  # type: ignore[misc]
