"""Unit tests for S11 Deterministic Strategy Selector."""

import pytest

from kautilya.contracts.strategy import RetrievalStrategy
from kautilya.knowledge.corpus import Corpus, load_corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.strategy.selector import StrategySelector


@pytest.fixture
def corpus() -> Corpus:
    """Load default corpus for test fixture."""
    return load_corpus()


@pytest.fixture
def graph(corpus: Corpus) -> KnowledgeGraph:
    """Construct KnowledgeGraph from default corpus."""
    return KnowledgeGraph.from_corpus(corpus)


@pytest.fixture
def selector(graph: KnowledgeGraph) -> StrategySelector:
    """Create StrategySelector instance."""
    return StrategySelector(graph=graph)


def test_selects_reasoning_for_multihop_queries(selector: StrategySelector):
    """Multi-hop / compositional queries should route to REASONING."""
    query = "Who founded the company that acquired Vector Labs?"
    decision = selector.select(query)

    assert decision.selected_strategy == RetrievalStrategy.REASONING
    assert decision.query == query
    assert "compositional" in decision.reason.lower() or "reasoning" in decision.reason.lower()
    assert decision.metadata.get("has_reasoning_plan") is True


def test_selects_structural_for_explicit_entity_relation_queries(selector: StrategySelector):
    """Direct entity-relation queries should route to STRUCTURAL."""
    query = "Where is Orion Analytics headquartered?"
    decision = selector.select(query)

    assert decision.selected_strategy == RetrievalStrategy.STRUCTURAL
    assert decision.query == query
    assert "structural" in decision.reason.lower() or "entity" in decision.reason.lower()
    assert len(decision.metadata.get("seed_entities", [])) > 0


def test_selects_structural_for_entity_pair_queries(selector: StrategySelector):
    """Queries linking two known entities should route to STRUCTURAL."""
    query = "What is the connection between Mira Sharma and Nova Systems?"
    decision = selector.select(query)

    assert decision.selected_strategy == RetrievalStrategy.STRUCTURAL
    assert len(decision.metadata.get("seed_entities", [])) >= 2


def test_selects_semantic_for_conceptual_or_entity_free_queries(selector: StrategySelector):
    """Conceptual or entity-free queries should route to SEMANTIC."""
    query = "What is modern artificial intelligence and deep neural network architecture?"
    decision = selector.select(query)

    assert decision.selected_strategy == RetrievalStrategy.SEMANTIC
    assert "semantic" in decision.reason.lower() or "no structural" in decision.reason.lower()
    assert len(decision.metadata.get("seed_entities", [])) == 0


def test_selects_hybrid_for_ambiguous_or_complex_queries(selector: StrategySelector):
    """Queries with ambiguity or multiple competing signals should route to HYBRID."""
    query = "What is the relationship between the founder of Nova and the analytics firm?"
    decision = selector.select(query)

    assert decision.selected_strategy == RetrievalStrategy.HYBRID
    assert "hybrid" in decision.reason.lower() or "ambiguous" in decision.reason.lower()


def test_deterministic_strategy_selection(selector: StrategySelector):
    """Repeated selection on the same query must produce identical decisions."""
    query = "Who founded Nova AI Division?"
    d1 = selector.select(query)
    d2 = selector.select(query)

    assert d1 == d2
    assert d1.to_dict() == d2.to_dict()
