"""Unit tests for EvidenceSufficiencyEvaluator."""

from __future__ import annotations

import pytest

from kautilya.contracts.reasoning import HopResult, ReasoningPlan, ReasoningTrace
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
        claims=[],
        conflicts=[],
        evidence=[],
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
        claims=[],
        conflicts=[],
        evidence=[],
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
        claims=[],
        conflicts=[],
        evidence=[],
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
        statement="Framework A provides graph search",
        confidence=0.8,
        source_evidence=[Evidence(id="e1", content="text1", score=0.8, source="doc1")],
    )
    claim2 = Claim(
        statement="Framework B provides graph search",
        confidence=0.8,
        source_evidence=[Evidence(id="e2", content="text2", score=0.8, source="doc2")],
    )
    resolution = ResolutionResult(
        query="Which framework provides both graph and vector search?",
        status=ResolutionStatus.AMBIGUOUS,
        claims=[claim1, claim2],
        conflicts=[],
        evidence=[claim1.source_evidence[0], claim2.source_evidence[0]],
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
    plan = ReasoningPlan(query="Find path from X to Z", target_relation="connects", max_hops=2)
    hop = HopResult(
        hop_index=0,
        source_entity="X",
        relation="connects",
        target_entity="Y",
        confidence=0.9,
        evidence_ids=["e1"],
    )
    trace = ReasoningTrace(plan=plan, hops=[hop], completed=False, confidence=0.45)
    
    resolution = ResolutionResult(
        query="Find path from X to Z",
        status=ResolutionStatus.CONSISTENT,
        claims=[Claim(statement="X connects Y", confidence=0.9, source_evidence=[])],
        conflicts=[],
        evidence=[],
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
    assert "reasoning trace incomplete" in assessment.reason.lower()


def test_evaluator_stops_on_consistent_sufficient(
    evaluator: EvidenceSufficiencyEvaluator,
) -> None:
    """CONSISTENT resolution with evidence and complete reasoning stops safely."""
    plan = ReasoningPlan(query="Find path from A to B", target_relation="acquired", max_hops=1)
    hop = HopResult(
        hop_index=0,
        source_entity="A",
        relation="acquired",
        target_entity="B",
        confidence=0.95,
        evidence_ids=["e1"],
    )
    trace = ReasoningTrace(plan=plan, hops=[hop], completed=True, confidence=0.95)
    ev = Evidence(id="e1", content="A acquired B", score=0.95, source="doc1")
    claim = Claim(statement="A acquired B", confidence=0.95, source_evidence=[ev])
    
    resolution = ResolutionResult(
        query="Did A acquire B?",
        status=ResolutionStatus.CONSISTENT,
        claims=[claim],
        conflicts=[],
        evidence=[ev],
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
