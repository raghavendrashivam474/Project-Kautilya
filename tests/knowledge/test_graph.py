"""Tests for the structural knowledge graph index."""

from pathlib import Path

import pytest

from kautilya.knowledge.corpus import load_corpus
from kautilya.knowledge.graph import KnowledgeGraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def graph():
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    return KnowledgeGraph.from_corpus(corpus)


def test_graph_builds_from_corpus(graph):
    assert len(graph.entities) >= 15
    assert len(graph.outgoing) >= 15
    assert len(graph.incoming) >= 15


def test_outgoing_relations(graph):
    rels = graph.get_outgoing("ent_002")
    assert len(rels) >= 2
    rel_types = {r.relation_type for r in rels}
    assert "DEVELOPED" in rel_types
    assert "HEADQUARTERED_IN" in rel_types


def test_incoming_relations(graph):
    rels = graph.get_incoming("ent_020")
    assert len(rels) >= 2
    rel_types = {r.relation_type for r in rels}
    assert "DEVELOPED" in rel_types
    assert "USES" in rel_types


def test_missing_entity_returns_empty(graph):
    assert graph.get_outgoing("ent_999") == ()
    assert graph.get_incoming("ent_999") == ()


def test_resolve_by_exact_name(graph):
    results = graph.resolve_entity("HelixDB")
    assert len(results) == 1
    assert results[0].id == "ent_020"


def test_resolve_by_alias(graph):
    results = graph.resolve_entity("Nova")
    assert len(results) >= 1
    assert any(e.id == "ent_001" for e in results)


def test_resolve_case_insensitive(graph):
    results = graph.resolve_entity("helixdb")
    assert len(results) == 1
    assert results[0].id == "ent_020"


def test_resolve_unknown_entity(graph):
    results = graph.resolve_entity("NonexistentCorp")
    assert results == []


def test_resolve_empty_query(graph):
    results = graph.resolve_entity("")
    assert results == []


def test_deterministic_ordering(graph):
    r1 = graph.get_outgoing("ent_002")
    r2 = graph.get_outgoing("ent_002")
    assert r1 == r2


def test_resolve_by_id(graph):
    results = graph.resolve_entity("ent_020")
    assert len(results) == 1
    assert results[0].name == "HelixDB"


def test_extract_entities_from_text(graph):
    entities = graph.extract_entities("Who developed HelixDB at Vector Labs?")
    names = [e.name for e in entities]
    assert "HelixDB" in names
    assert "Vector Labs" in names


def test_traverse_0_hop(graph):
    paths = graph.traverse("ent_020", max_hops=0)
    assert len(paths) == 1
    assert paths[0].hops == 0
    assert paths[0].entities[0].name == "HelixDB"


def test_traverse_1_hop(graph):
    paths = graph.traverse("ent_002", max_hops=1)
    # ent_002 has outgoing + incoming edges
    assert len(paths) > 1
    hop_counts = {p.hops for p in paths}
    assert 0 in hop_counts
    assert 1 in hop_counts
    assert 2 not in hop_counts


def test_traverse_2_hop_bounded(graph):
    paths = graph.traverse("ent_001", max_hops=2)
    max_observed_hops = max(p.hops for p in paths)
    assert max_observed_hops <= 2


def test_find_paths_between(graph):
    # Nova Systems (ent_001) -> ACQUIRED -> Vector Labs (ent_002) -> DEVELOPED -> HelixDB (ent_020)
    paths = graph.find_paths_between("ent_001", "ent_020", max_hops=2)
    assert len(paths) >= 1
    assert paths[0].entities[0].name == "Nova Systems"
    assert paths[0].entities[-1].name == "HelixDB"
