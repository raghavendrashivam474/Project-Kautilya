"""Test corpus contract dataclasses."""
from kautilya.contracts import Chunk, Document, Entity, Provenance, Relation


def test_document_construction():
    d = Document(id="doc_001", title="t", source="s.txt", text="hello", metadata={"k": "v"})
    assert d.id == "doc_001"
    assert d.metadata["k"] == "v"


def test_chunk_construction():
    c = Chunk(id="chunk_001_001", document_id="doc_001", text="x", sequence=1)
    assert c.sequence == 1


def test_entity_construction():
    e = Entity(id="ent_001", name="Nova", entity_type="Company", aliases=("N",))
    assert "N" in e.aliases


def test_relation_construction():
    r = Relation(
        id="rel_001",
        source_entity_id="ent_001",
        relation_type="FOUNDED",
        target_entity_id="ent_002",
        provenance=Provenance(document_id="doc_001", chunk_id="chunk_001_001"),
    )
    assert r.provenance.document_id == "doc_001"
