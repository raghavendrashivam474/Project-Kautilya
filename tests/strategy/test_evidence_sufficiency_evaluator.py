"""Unit tests for EvidenceSufficiencyEvaluator with correct S1-S11 contract signatures."""

from __future__ import annotations

import pytest

from kautilya.contracts.reasoning import (
    Direction,
    HopResult,
    ReasoningPlan,
    ReasoningStatus,
    ReasoningStep,
    ReasoningTrace,
)
from kautilya.contracts.resolution import Claim, ResolutionResult, ResolutionStatus
from kautilya.contracts.retrieval import Evidence
from kautilya.contracts.strategy import (
    RetrievalStrategy,
    StrategyDecision,
    SufficiencyStatus,
)
from kautilya.strategy.sufficiency import EvidenceSufficiencyEvaluator


@pytest.fixture
def evaluator() -> EvidenceSufficiencyEvaluator:
    return EvidenceSufficiencyEvaluator()


def test_evaluator_stops_on_hybrid_strategy(evaluator: EvidenceSufficiencyEvaluator) -> None:
    """HYBRID strategy should never escalate further."""
    decision = StrategyDecision(
        query="What is the relation between A and B?",
        selected_strategy=RetrievalStrategy.HYBRID,
        reason="Hybrid query",
    )
    resolution = ResolutionResult(
        query="What is the relation between A and B?",
        status=ResolutionStatus.INSUFFICIENT,
        claims=(),
        supporting_evidence=(),
        conflicting_evidence=(),
    )
    assessment = evaluator.evaluate(
        query=decision.query,
        initial_strategy=decision.selected_strategy,
        resolution_result=resolution,
    )
    assert not assessment.escalation_required
    assert assessment.status == SufficiencyStatus.INSUFFICIENT
    assert "already executed hybrid" in assessment.reason.lower()


def test_evaluator_stops_on_unsupported(evaluator: EvidenceSufficiencyEvaluator) -> None:
    """UNSUPPORTED queries should stop early without wasting hybrid escalation."""
    decision = StrategyDecision(
        query="Who is the CEO of Acme Corp?",
        selected_strategy=RetrievalStrategy.STRUCTURAL,
        reason="Entity attribute",
    )
    resolution = ResolutionResult(
        query="Who is the CEO of Acme Corp?",
        status=ResolutionStatus.UNSUPPORTED,
        claims=(),
        supporting_evidence=(),
        conflicting_evidence=(),
    )
    assessment = evaluator.evaluate(
        query=decision.query,
        initial_strategy=decision.selected_strategy,
        resolution_result=resolution,
    )
    assert not assessment.escalation_required
    assert assessment.status == SufficiencyStatus.UNSUPPORTED
    assert "outside knowledge world" in assessment.reason.lower()


def test_evaluator_escalates_on_insufficient_status(evaluator: EvidenceSufficiencyEvaluator) -> None:
    """INSUFFICIENT resolution status must trigger escalation to HYBRID."""
    decision = StrategyDecision(
        query="What connects Alpha and Gamma?",
        selected_strategy=RetrievalStrategy.SEMANTIC,
        reason="Semantic probe",
    )
    resolution = ResolutionResult(
        query="What connects Alpha and Gamma?",
        status=ResolutionStatus.INSUFFICIENT,
        claims=(),
        supporting_evidence=(),
        conflicting_evidence=(),
    )
    assessment = evaluator.evaluate(
        query=decision.query,
        initial_strategy=decision.selected_strategy,
        resolution_result=resolution,
    )
    assert assessment.escalation_required
    assert assessment.status == SufficiencyStatus.INSUFFICIENT
    assert assessment.escalation_strategy == RetrievalStrategy.HYBRID


def test_evaluator_escalates_on_ambiguous_status(evaluator: EvidenceSufficiencyEvaluator) -> None:
    """AMBIGUOUS resolution status must trigger escalation to HYBRID for disambiguation."""
    claim1 = Claim(
        subject="Framework A",
        predicate="provides",
        object="graph search",
        evidence_chunk_ids=("e1",),
    )
    claim2 = Claim(
        subject="Framework B",
        predicate="provides",
        object="graph search",
        evidence_chunk_ids=("e2",),
    )
    ev1 = Evidence(chunk_id="e1", document_id="doc1", text="text1", score=0.8)
    ev2 = Evidence(chunk_id="e2", document_id="doc2", text="text2", score=0.8)
    
    resolution = ResolutionResult(
        query="Which framework provides both graph and vector search?",
        status=ResolutionStatus.AMBIGUOUS,
        claims=(claim1, claim2),
        supporting_evidence=(ev1, ev2),
        conflicting_evidence=(),
    )
    assessment = evaluator.evaluate(
        query=resolution.query,
        initial_strategy=RetrievalStrategy.SEMANTIC,
        resolution_result=resolution,
    )
    assert assessment.escalation_required
    assert assessment.status == SufficiencyStatus.AMBIGUOUS
    assert assessment.escalation_strategy == RetrievalStrategy.HYBRID


def test_evaluator_escalates_on_incomplete_reasoning_trace(
    evaluator: EvidenceSufficiencyEvaluator,
) -> None:
    """Incomplete reasoning trace must trigger escalation even if resolution was partial."""
    step = ReasoningStep(relation_type="connects", direction=Direction.OUTGOING, hop_index=0)
    plan = ReasoningPlan(query="Find path from X to Z", seed_entity_name="X", steps=(step,))
    hop = HopResult(
        hop_index=0,
        source_entity_id="x1",
        source_entity_name="X",
        relation_type="connects",
        direction=Direction.OUTGOING,
        target_entity_id=None,
        target_entity_name=None,
        chunk_ids=(),
        status=ReasoningStatus.TRAVERSAL_FAILURE,
    )
    trace = ReasoningTrace(
        plan=plan,
        hops=(hop,),
        terminal_entity_name=None,
        status=ReasoningStatus.TRAVERSAL_FAILURE,
    )
    
    claim = Claim(subject="X", predicate="connects", object="Y")
    resolution = ResolutionResult(
        query="Find path from X to Z",
        status=ResolutionStatus.CONSISTENT,
        claims=(claim,),
        supporting_evidence=(),
        conflicting_evidence=(),
    )
    assessment = evaluator.evaluate(
        query=resolution.query,
        initial_strategy=RetrievalStrategy.REASONING,
        resolution_result=resolution,
        reasoning_trace=trace,
    )
    assert assessment.escalation_required
    assert assessment.reasoning_completed is False
    assert assessment.escalation_strategy == RetrievalStrategy.HYBRID
    assert "unsuccessful" in assessment.reason.lower()


def test_evaluator_stops_on_consistent_sufficient(
    evaluator: EvidenceSufficiencyEvaluator,
) -> None:
    """CONSISTENT resolution with evidence and complete reasoning stops safely."""
    step = ReasoningStep(relation_type="acquired", direction=Direction.OUTGOING, hop_index=0)
    plan = ReasoningPlan(query="Did A acquire B?", seed_entity_name="A", steps=(step,))
    hop = HopResult(
        hop_index=0,
        source_entity_id="a1",
        source_entity_name="A",
        relation_type="acquired",
        direction=Direction.OUTGOING,
        target_entity_id="b1",
        target_entity_name="B",
        chunk_ids=("e1",),
        status=ReasoningStatus.SUCCESS,
    )
    trace = ReasoningTrace(
        plan=plan,
        hops=(hop,),
        terminal_entity_name="B",
        status=ReasoningStatus.SUCCESS,
    )
    ev = Evidence(chunk_id="e1", document_id="doc1", text="A acquired B", score=0.95)
    claim = Claim(subject="A", predicate="acquired", object="B", evidence_chunk_ids=("e1",))
    
    resolution = ResolutionResult(
        query="Did A acquire B?",
        status=ResolutionStatus.CONSISTENT,
        claims=(claim,),
        supporting_evidence=(ev,),
        conflicting_evidence=(),
    )
    assessment = evaluator.evaluate(
        query=resolution.query,
        initial_strategy=RetrievalStrategy.REASONING,
        resolution_result=resolution,
        reasoning_trace=trace,
    )
    assert not assessment.escalation_required
    assert assessment.status == SufficiencyStatus.SUFFICIENT
    assert assessment.escalation_strategy is None
    assert assessment.evidence_count == 1
    assert assessment.claim_count == 1
    assert assessment.reasoning_completed is True
