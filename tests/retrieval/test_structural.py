"""Integration tests for the KAGRetriever."""

from pathlib import Path

import pytest

from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.knowledge.corpus import load_corpus
from kautilya.retrieval.structural import KAGRetriever

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def retriever():
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    return KAGRetriever(corpus=corpus, max_hops=2, top_k=5)


def test_kag_retrieve_returns_retrieval_result(retriever):
    result = retriever.retrieve("HelixDB")
    assert isinstance(result, RetrievalResult)
    assert result.query == "HelixDB"
    assert result.retrieval_method == "structural"
    assert len(result.evidence) > 0


def test_kag_evidence_conforms_to_contract(retriever):
    result = retriever.retrieve("Vector Labs")
    for ev in result.evidence:
        assert isinstance(ev, Evidence)
        assert ev.chunk_id
        assert ev.document_id
        assert ev.text
        assert isinstance(ev.score, float)
        assert ev.retrieval_method == "structural"
        assert ev.evidence_origin == "entity/relation"
        assert "relation_type" in ev.provenance


def test_kag_multi_hop_discovery(retriever):
    # Nova Systems and HelixDB are separated by: Nova Systems -> ACQUIRED -> Vector Labs -> DEVELOPED -> HelixDB
    result = retriever.retrieve("Nova Systems HelixDB", max_hops=2)
    assert len(result.evidence) > 0
    doc_ids = {ev.document_id for ev in result.evidence}
    # doc_005 (acquisition) or doc_002/doc_003 (HelixDB development) should be present
    assert "doc_005" in doc_ids or "doc_002" in doc_ids


def test_kag_unknown_entity_returns_empty(retriever):
    result = retriever.retrieve("NonExistentCorporationXYZ")
    assert isinstance(result, RetrievalResult)
    assert result.evidence == []
    assert result.metadata["paths_found"] == 0


def test_kag_deterministic_retrieval(retriever):
    r1 = retriever.retrieve("HelixDB")
    r2 = retriever.retrieve("HelixDB")
    assert r1.top_chunk_ids == r2.top_chunk_ids
    assert r1.scores == r2.scores


def test_kag_path_inspectability(retriever):
    result = retriever.retrieve("HelixDB")
    assert "paths" in result.metadata
    assert len(result.metadata["paths"]) > 0
    first_path = result.metadata["paths"][0]
    assert "formatted" in first_path
    assert "provenance" in first_path
