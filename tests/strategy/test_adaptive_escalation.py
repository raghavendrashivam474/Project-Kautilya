"""Unit and integration tests for S12 Two-Phase Adaptive Escalation."""

from __future__ import annotations

import pytest

from kautilya.contracts.resolution import ResolutionStatus
from kautilya.contracts.strategy import RetrievalStrategy, SufficiencyStatus
from kautilya.infrastructure.embeddings.provider import SentenceTransformerProvider
from kautilya.knowledge.corpus import Corpus, load_corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.strategy.orchestrator import AdaptiveOrchestrator


@pytest.fixture
def corpus() -> Corpus:
    return load_corpus()


@pytest.fixture
def graph(corpus: Corpus) -> KnowledgeGraph:
    return KnowledgeGraph.from_corpus(corpus)


@pytest.fixture
def embedding_provider() -> SentenceTransformerProvider:
    return SentenceTransformerProvider()


@pytest.fixture
def orchestrator(
    corpus: Corpus, graph: KnowledgeGraph, embedding_provider: SentenceTransformerProvider
) -> AdaptiveOrchestrator:
    return AdaptiveOrchestrator(
        corpus=corpus,
        graph=graph,
        embedding_provider=embedding_provider,
    )


def test_resolve_adaptive_sufficient_stops_without_escalation(
    orchestrator: AdaptiveOrchestrator,
) -> None:
    """A direct factual query with clear structural evidence should stop at Phase 1."""
    query = "Who founded Vector Labs?"
    res_result, decision, assessment, metrics = orchestrator.resolve_adaptive(query)

    assert decision.selected_strategy == RetrievalStrategy.STRUCTURAL
    assert not assessment.escalation_required
    assert assessment.status == SufficiencyStatus.SUFFICIENT
    assert metrics["escalated"] is False
    assert metrics["final_strategy"] == "structural"
    assert metrics["phase1_invocations"] == 1
    assert metrics["phase2_invocations"] == 0
    assert metrics["total_invocations"] == 1
    assert res_result.status == ResolutionStatus.CONSISTENT


def test_resolve_adaptive_insufficient_escalates_to_hybrid(
    orchestrator: AdaptiveOrchestrator,
) -> None:
    """Queries that produce INSUFFICIENT in Phase 1 should escalate to HYBRID."""
    query = "Who acquired DeepMind?"
    _res_result, _decision, assessment, metrics = orchestrator.resolve_adaptive(query)

    assert assessment.escalation_required is True
    assert assessment.status == SufficiencyStatus.INSUFFICIENT
    assert metrics["escalated"] is True
    assert metrics["final_strategy"] == "hybrid"
    assert metrics["phase2_invocations"] > 0
    assert metrics["total_invocations"] > metrics["phase1_invocations"]


def test_resolve_adaptive_hybrid_never_escalates(
    orchestrator: AdaptiveOrchestrator,
) -> None:
    """A query routed initially to HYBRID should execute once and never escalate."""
    query = "What is the relationship between the founder of Nova and the analytics firm?"
    _res_result, decision, assessment, metrics = orchestrator.resolve_adaptive(query)

    assert decision.selected_strategy == RetrievalStrategy.HYBRID
    assert not assessment.escalation_required
    assert metrics["escalated"] is False
    assert metrics["final_strategy"] == "hybrid"
    assert metrics["phase2_invocations"] == 0
