"""Unit tests for S11 Adaptive Execution Orchestrator."""

import pytest

from kautilya.contracts.retrieval import RetrievalResult
from kautilya.contracts.strategy import RetrievalStrategy
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


def test_adaptive_retrieves_semantic_only_for_entity_free_query(
    orchestrator: AdaptiveOrchestrator,
):
    """Ensure entity-free queries invoke ONLY semantic retrieval."""
    query = "What is modern artificial intelligence and deep neural network architecture?"
    result, decision, metrics = orchestrator.retrieve(query)

    assert isinstance(result, RetrievalResult)
    assert decision.selected_strategy == RetrievalStrategy.SEMANTIC
    assert metrics["semantic_invoked"] is True
    assert metrics["kag_invoked"] is False
    assert metrics["reasoning_invoked"] is False
    assert metrics["fusion_invoked"] is False
    assert metrics["total_invocations"] == 1


def test_adaptive_retrieves_structural_only_for_direct_relation_query(
    orchestrator: AdaptiveOrchestrator,
):
    """Ensure direct entity relation query invokes ONLY structural KAG retrieval."""
    query = "Where is Orion Analytics headquartered?"
    result, decision, metrics = orchestrator.retrieve(query)

    assert isinstance(result, RetrievalResult)
    assert decision.selected_strategy == RetrievalStrategy.STRUCTURAL
    assert metrics["semantic_invoked"] is False
    assert metrics["kag_invoked"] is True
    assert metrics["reasoning_invoked"] is False
    assert metrics["fusion_invoked"] is False
    assert metrics["total_invocations"] == 1
    assert len(result.evidence) > 0


def test_adaptive_retrieves_reasoning_for_multihop_query(
    orchestrator: AdaptiveOrchestrator,
):
    """Ensure compositional queries invoke reasoning."""
    query = "Who founded the company that acquired Vector Labs?"
    result, decision, metrics = orchestrator.retrieve(query)

    assert isinstance(result, RetrievalResult)
    assert decision.selected_strategy == RetrievalStrategy.REASONING
    assert metrics["reasoning_invoked"] is True
    assert metrics["semantic_invoked"] is False
    assert metrics["kag_invoked"] is False
    assert metrics["total_invocations"] == 1
    assert len(result.evidence) > 0


def test_adaptive_retrieves_hybrid_for_ambiguous_query(
    orchestrator: AdaptiveOrchestrator,
):
    """Ensure ambiguous queries invoke hybrid fusion."""
    query = "What is the relationship between the founder of Nova and the analytics firm?"
    result, decision, metrics = orchestrator.retrieve(query)

    assert isinstance(result, RetrievalResult)
    assert decision.selected_strategy == RetrievalStrategy.HYBRID
    assert metrics["semantic_invoked"] is True
    assert metrics["kag_invoked"] is True
    assert metrics["fusion_invoked"] is True
    assert metrics["total_invocations"] >= 3


def test_adaptive_exploration_and_resolution_compatibility(
    orchestrator: AdaptiveOrchestrator,
):
    """Ensure adaptive exploration produces a valid ExplorationResult that resolves cleanly."""
    from kautilya.resolution.resolution_engine import KnowledgeResolutionEngine

    query = "Where is Orion Analytics headquartered?"
    exp_res, decision, metrics = orchestrator.explore(query)

    assert exp_res.query == query
    assert len(exp_res.evidence) > 0
    assert decision.selected_strategy == RetrievalStrategy.STRUCTURAL
    assert metrics["total_invocations"] == 1

    res_engine = KnowledgeResolutionEngine(corpus=orchestrator.corpus, graph=orchestrator.graph)
    res_res = res_engine.resolve(exp_res)

    assert res_res.status.value in ("CONSISTENT", "CONFLICTING", "INSUFFICIENT", "UNSUPPORTED", "AMBIGUOUS")
    assert res_res.query == query
