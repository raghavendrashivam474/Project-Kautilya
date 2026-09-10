"""Test the actual S1 corpus loads, validates, and is internally consistent."""

import pytest

from kautilya.contracts import Chunk, Document, Entity, Provenance, Relation
from kautilya.knowledge import CorpusValidationError, load_corpus
from kautilya.knowledge.corpus import Corpus, validate_corpus


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def test_corpus_loads(corpus):
    assert len(corpus.documents) >= 10
    assert len(corpus.chunks) >= len(corpus.documents)
    assert len(corpus.entities) >= 10
    assert len(corpus.relations) >= 15


def test_all_ids_unique(corpus):
    for group in (corpus.documents, corpus.chunks, corpus.entities, corpus.relations):
        ids = [x.id for x in group]
        assert len(ids) == len(set(ids))


def test_relations_reference_real_entities(corpus):
    ent_ids = {e.id for e in corpus.entities}
    for r in corpus.relations:
        assert r.source_entity_id in ent_ids
        assert r.target_entity_id in ent_ids


def test_every_relation_has_valid_provenance(corpus):
    doc_ids = {d.id for d in corpus.documents}
    chunk_ids = {c.id for c in corpus.chunks}
    for r in corpus.relations:
        assert r.provenance.document_id in doc_ids
        assert r.provenance.chunk_id in chunk_ids


def test_loading_is_reproducible():
    c1 = load_corpus()
    c2 = load_corpus()
    assert c1 == c2


def test_entity_lookup_by_name(corpus):
    e = corpus.entity("HelixDB")
    assert e is not None
    assert e.entity_type == "Technology"


def test_validation_detects_broken_reference():
    doc = Document(id="doc_x", title="t", source="s", text="hello", metadata={})
    chunk = Chunk(id="chunk_x_001", document_id="doc_x", text="hello", sequence=1)
    e1 = Entity(id="ent_a", name="A", entity_type="Company")
    # Relation points to non-existent ent_b
    rel = Relation(
        id="rel_a",
        source_entity_id="ent_a",
        relation_type="USES",
        target_entity_id="ent_b",
        provenance=Provenance(document_id="doc_x", chunk_id="chunk_x_001"),
    )
    bad = Corpus(
        documents=(doc,),
        chunks=(chunk,),
        entities=(e1,),
        relations=(rel,),
    )
    with pytest.raises(CorpusValidationError):
        validate_corpus(bad)
