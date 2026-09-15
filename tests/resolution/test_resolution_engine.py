"""Unit tests for KnowledgeResolutionEngine."""

import pytest

from kautilya.contracts.entity import Entity
from kautilya.contracts.exploration import ExplorationResult
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.relation import Provenance, Relation
from kautilya.contracts.resolution import ResolutionStatus
from kautilya.contracts.retrieval import Evidence
from kautilya.resolution.resolution_engine import KnowledgeResolutionEngine


@pytest.fixture
def resolution_engine():
    return KnowledgeResolutionEngine()


def test_resolution_unsupported_boundary(resolution_engine):
    """Verify that an unsupported exploration result resolves to UNSUPPORTED without guessing."""
    unsupported_exploration = ExplorationResult(
        query="What is the GDP of Mars?",
        objective="No seed entities or semantic evidence found for the query.",
        seed_entities=(),
        explored_paths=(),
        evidence=(),
        status="UNSUPPORTED",
    )

    result = resolution_engine.resolve(unsupported_exploration)
    assert result.status == ResolutionStatus.UNSUPPORTED
    assert len(result.claims) == 0
    assert len(result.supporting_evidence) == 0
    assert len(result.conflicting_evidence) == 0


def test_resolution_insufficient_evidence(resolution_engine):
    """Verify that unformed claims result in INSUFFICIENT status."""
    ev = Evidence(
        chunk_id="chunk_999_001",
        document_id="doc_999",
        text="Vague mention of tech companies.",
        score=0.3,
    )
    insufficient_exploration = ExplorationResult(
        query="Tell me about unknown rumors",
        objective="Found partial semantic matches.",
        seed_entities=(),
        explored_paths=(),
        evidence=(ev,),
        status="PARTIAL",
    )

    result = resolution_engine.resolve(insufficient_exploration)
    assert result.status == ResolutionStatus.INSUFFICIENT
    assert len(result.claims) == 0
    assert len(result.supporting_evidence) == 1


def test_resolution_consistent_claims(resolution_engine):
    """Verify that corroborating claims result in CONSISTENT status."""
    e1 = Entity(id="ent_001", name="Nova Systems", entity_type="company")
    e2 = Entity(id="ent_012", name="Rohan Kapoor", entity_type="person")

    r1 = Relation(
        id="rel_001",
        source_entity_id="ent_001",
        relation_type="FOUNDED",
        target_entity_id="ent_012",
        provenance=Provenance(document_id="doc_001", chunk_id="chunk_001_001"),
    )

    path1 = KnowledgePath(
        entities=(e1, e2),
        relations=(r1,),
        directions=("outgoing",),
    )

    ev1 = Evidence(
        chunk_id="chunk_001_001",
        document_id="doc_001",
        text="Nova Systems was founded by Rohan Kapoor.",
        score=0.95,
    )

    exploration = ExplorationResult(
        query="Who founded Nova Systems?",
        objective="Found founder path.",
        seed_entities=(e1,),
        explored_paths=(path1,),
        evidence=(ev1,),
        status="SUCCESS",
    )

    result = resolution_engine.resolve(exploration)
    assert result.status == ResolutionStatus.CONSISTENT
    assert len(result.claims) == 1
    assert result.claims[0].subject == "Nova Systems"
    assert result.claims[0].predicate == "FOUNDED"
    assert result.claims[0].object == "Rohan Kapoor"
    assert len(result.supporting_evidence) == 1
    assert len(result.conflicting_evidence) == 0


def test_resolution_conflicting_claims(resolution_engine):
    """Verify that contradictory single-valued claims result in CONFLICTING status with provenance."""
    e1 = Entity(id="ent_001", name="Nova Systems", entity_type="company")
    e2 = Entity(id="ent_012", name="Rohan Kapoor", entity_type="person")
    e3 = Entity(id="ent_099", name="Alice Smith", entity_type="person")

    r1 = Relation(
        id="rel_001",
        source_entity_id="ent_001",
        relation_type="FOUNDED",
        target_entity_id="ent_012",
        provenance=Provenance(document_id="doc_001", chunk_id="chunk_001_001"),
    )

    r2 = Relation(
        id="rel_999",
        source_entity_id="ent_001",
        relation_type="FOUNDED",
        target_entity_id="ent_099",
        provenance=Provenance(document_id="doc_099", chunk_id="chunk_099_001"),
    )

    path1 = KnowledgePath(entities=(e1, e2), relations=(r1,), directions=("outgoing",))
    path2 = KnowledgePath(entities=(e1, e3), relations=(r2,), directions=("outgoing",))

    ev1 = Evidence(
        chunk_id="chunk_001_001",
        document_id="doc_001",
        text="Nova Systems was founded by Rohan Kapoor.",
        score=0.95,
    )
    ev2 = Evidence(
        chunk_id="chunk_099_001",
        document_id="doc_099",
        text="Nova Systems was founded by Alice Smith.",
        score=0.90,
    )

    exploration = ExplorationResult(
        query="Who founded Nova Systems?",
        objective="Explored multiple paths.",
        seed_entities=(e1,),
        explored_paths=(path1, path2),
        evidence=(ev1, ev2),
        status="SUCCESS",
    )

    result = resolution_engine.resolve(exploration)
    assert result.status == ResolutionStatus.CONFLICTING
    assert len(result.claims) == 2
    assert len(result.conflicting_evidence) == 2
    assert "Conflicting claims detected" in result.rationale
    assert result.metadata["conflict_count"] == 1


def test_resolution_determinism(resolution_engine):
    """Verify that resolution is completely deterministic over 20 repeated runs."""
    e1 = Entity(id="ent_001", name="Nova Systems", entity_type="company")
    e2 = Entity(id="ent_012", name="Rohan Kapoor", entity_type="person")

    r1 = Relation(
        id="rel_001",
        source_entity_id="ent_001",
        relation_type="FOUNDED",
        target_entity_id="ent_012",
        provenance=Provenance(document_id="doc_001", chunk_id="chunk_001_001"),
    )
    path1 = KnowledgePath(entities=(e1, e2), relations=(r1,), directions=("outgoing",))
    ev1 = Evidence(
        chunk_id="chunk_001_001",
        document_id="doc_001",
        text="Nova Systems was founded by Rohan Kapoor.",
        score=0.95,
    )

    exploration = ExplorationResult(
        query="Who founded Nova Systems?",
        objective="Found founder path.",
        seed_entities=(e1,),
        explored_paths=(path1,),
        evidence=(ev1,),
        status="SUCCESS",
    )

    first_dict = resolution_engine.resolve(exploration).to_dict()
    for _ in range(20):
        current_dict = resolution_engine.resolve(exploration).to_dict()
        assert current_dict == first_dict
