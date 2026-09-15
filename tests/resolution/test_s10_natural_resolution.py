"""Unit and integration tests for S10 Natural Conflict Resolution."""

from pathlib import Path

import pytest

from kautilya.contracts.resolution import ResolutionStatus
from kautilya.exploration.exploration_engine import KnowledgeExplorationEngine
from kautilya.knowledge.corpus import load_corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.resolution.resolution_engine import KnowledgeResolutionEngine

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def explorer_and_resolver():
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    graph = KnowledgeGraph.from_corpus(corpus)
    explorer = KnowledgeExplorationEngine(corpus=corpus, graph=graph, max_hops=2, top_k=5)
    resolver = KnowledgeResolutionEngine(corpus=corpus, graph=graph)
    return explorer, resolver


def test_s10_natural_founder_conflict(explorer_and_resolver):
    """Corpus documents doc_001 (Rohan Kapoor) and doc_013 (Mira Sharma) conflict on Nova Systems founder."""
    explorer, resolver = explorer_and_resolver
    exp_res = explorer.explore("Who founded Nova Systems?")
    res = resolver.resolve(exp_res)

    assert res.status == ResolutionStatus.CONFLICTING
    assert len(res.conflicting_evidence) >= 2
    conflicting_docs = {e.document_id for e in res.conflicting_evidence}
    assert "doc_013" in conflicting_docs
    assert "doc_001" in conflicting_docs or "doc_012" in conflicting_docs


def test_s10_natural_headquarters_conflict(explorer_and_resolver):
    """Corpus documents doc_004 (Hyderabad) and doc_014 (Pune) conflict on Orion Analytics HQ."""
    explorer, resolver = explorer_and_resolver
    exp_res = explorer.explore("Where is Orion Analytics headquartered?")
    res = resolver.resolve(exp_res)

    assert res.status == ResolutionStatus.CONFLICTING
    conflicting_docs = {e.document_id for e in res.conflicting_evidence}
    assert "doc_004" in conflicting_docs
    assert "doc_014" in conflicting_docs


def test_s10_natural_inverse_acquisition_conflict(explorer_and_resolver):
    """Corpus documents doc_005 (Nova Systems) and doc_015 (Orion Analytics) conflict on who acquired Vector Labs."""
    explorer, resolver = explorer_and_resolver
    exp_res = explorer.explore("Who acquired Vector Labs?")
    res = resolver.resolve(exp_res)

    assert res.status == ResolutionStatus.CONFLICTING
    conflicting_docs = {e.document_id for e in res.conflicting_evidence}
    assert "doc_005" in conflicting_docs
    assert "doc_015" in conflicting_docs


def test_s10_query_scoped_consistency_despite_neighborhood_divergence(explorer_and_resolver):
    """ADR-0010: Query asking about founder of Orion Analytics must resolve as CONSISTENT despite HQ divergence."""
    explorer, resolver = explorer_and_resolver
    exp_res = explorer.explore("Who founded Orion Analytics?")
    res = resolver.resolve(exp_res)

    assert res.status == ResolutionStatus.CONSISTENT
    assert res.metadata.get("neighborhood_conflicts", 0) >= 1
    assert len(res.conflicting_evidence) == 0


def test_s10_multivalued_non_conflict(explorer_and_resolver):
    """Mira Sharma leading multiple entities is not a conflict."""
    explorer, resolver = explorer_and_resolver
    exp_res = explorer.explore("What organizations does Mira Sharma lead?")
    res = resolver.resolve(exp_res)

    assert res.status == ResolutionStatus.CONSISTENT
    assert len(res.conflicting_evidence) == 0


def test_s10_determinism(explorer_and_resolver):
    """Repeated exploration and resolution on natural conflicts must produce identical results."""
    explorer, resolver = explorer_and_resolver
    query = "Who founded Nova Systems?"

    res1 = resolver.resolve(explorer.explore(query))
    res2 = resolver.resolve(explorer.explore(query))

    assert res1.to_dict() == res2.to_dict()
