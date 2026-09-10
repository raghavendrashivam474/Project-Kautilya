"""Unit tests for the KnowledgePath contract."""

from dataclasses import FrozenInstanceError

import pytest

from kautilya.contracts.entity import Entity
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.relation import Provenance, Relation


def test_knowledge_path_creation():
    e1 = Entity(id="ent_001", name="Nova Systems", entity_type="Company")
    e2 = Entity(id="ent_002", name="Vector Labs", entity_type="Company")
    r = Relation(
        id="rel_030",
        source_entity_id="ent_001",
        relation_type="ACQUIRED",
        target_entity_id="ent_002",
        provenance=Provenance(document_id="doc_005", chunk_id="chunk_005_001"),
    )

    path = KnowledgePath(
        entities=(e1, e2),
        relations=(r,),
        directions=("outgoing",),
    )

    assert path.hops == 1
    assert path.document_ids == ["doc_005"]
    assert path.chunk_ids == ["chunk_005_001"]
    assert path.format_path() == "Nova Systems --ACQUIRED--> Vector Labs"

    d = path.to_dict()
    assert d["hops"] == 1
    assert d["entities"] == ["Nova Systems", "Vector Labs"]
    assert d["relations"] == ["ACQUIRED"]


def test_knowledge_path_immutability():
    e1 = Entity(id="ent_001", name="Nova Systems", entity_type="Company")
    path = KnowledgePath(entities=(e1,))

    with pytest.raises(FrozenInstanceError):
        path.entities = ()  # type: ignore[misc]


def test_0_hop_path():
    e = Entity(id="ent_020", name="HelixDB", entity_type="Technology")
    path = KnowledgePath(entities=(e,))
    assert path.hops == 0
    assert path.relations == ()
    assert path.format_path() == "HelixDB"
