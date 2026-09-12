"""Tests for S8 Knowledge Exploration Engine."""

from pathlib import Path

import pytest

from kautilya.contracts.exploration import ExplorationResult
from kautilya.exploration.exploration_engine import KnowledgeExplorationEngine
from kautilya.knowledge.corpus import load_corpus
from kautilya.knowledge.graph import KnowledgeGraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def engine():
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    graph = KnowledgeGraph.from_corpus(corpus)
    return KnowledgeExplorationEngine(corpus=corpus, graph=graph)


def test_exploration_multi_hop_vertical_slice(engine):
    """Test multi-hop exploration on 'Who founded the company that acquired Vector Labs?'"""
    query = "Who founded the company that acquired Vector Labs?"
    result = engine.explore(query)

    assert isinstance(result, ExplorationResult)
    assert result.status == "SUCCESS"
    assert "Nova Systems" in [e.name for e in result.seed_entities] or "Vector Labs" in [
        e.name for e in result.seed_entities
    ]
    assert len(result.evidence) > 0
    assert result.trace is not None
    assert result.trace.is_success
    assert result.trace.terminal_entity_name == "Rohan Kapoor"

    # Terminal hop evidence should be present in fused evidence
    chunk_ids = [ev.chunk_id for ev in result.evidence]
    assert "chunk_001_001" in chunk_ids or "chunk_012_001" in chunk_ids


def test_exploration_structural_hub(engine):
    """Test hub exploration on an entity."""
    query = "What are all the entities and partnerships connected to Nova Systems?"
    result = engine.explore(query)

    assert isinstance(result, ExplorationResult)
    assert result.status == "SUCCESS"
    assert any(e.name == "Nova Systems" for e in result.seed_entities)
    assert len(result.explored_paths) > 0
    assert len(result.evidence) > 0


def test_exploration_unsupported_boundary(engine):
    """Test exploration on an unsupported query outside corpus scope."""
    query = "Who founded Cyberdyne Systems?"
    result = engine.explore(query)

    assert isinstance(result, ExplorationResult)
    assert result.status == "UNSUPPORTED"
    assert len(result.seed_entities) == 0
    assert len(result.explored_paths) == 0
    assert len(result.evidence) == 0


def test_exploration_determinism(engine):
    """Verify that multiple exploration runs for identical queries produce identical results."""
    query = "Who co-founded the company that Nova Systems acquired?"
    res1 = engine.explore(query)
    res2 = engine.explore(query)

    assert res1.status == res2.status
    assert res1.objective == res2.objective
    assert [e.id for e in res1.seed_entities] == [e.id for e in res2.seed_entities]
    assert [ev.chunk_id for ev in res1.evidence] == [ev.chunk_id for ev in res2.evidence]
    assert res1.to_dict() == res2.to_dict()


def test_exploration_to_dict_inspectability(engine):
    """Verify that ExplorationResult serializes cleanly to a dictionary."""
    query = "Who founded Vector Labs?"
    result = engine.explore(query)

    d = result.to_dict()
    assert isinstance(d, dict)
    assert "query" in d
    assert "objective" in d
    assert "seed_entities" in d
    assert "explored_paths" in d
    assert "evidence" in d
    assert "status" in d
    assert "metadata" in d
