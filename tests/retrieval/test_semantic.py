"""Integration tests for the semantic retriever.

These tests use a real (small) embedding model and the S1 corpus.
They verify the end-to-end retrieval pipeline.
"""

from pathlib import Path

import pytest

from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.infrastructure.embeddings import SentenceTransformerProvider
from kautilya.knowledge.corpus import load_corpus
from kautilya.retrieval.semantic import SemanticRetriever

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def retriever():
    """Build a retriever once for the test module."""
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
    return SemanticRetriever(corpus=corpus, embedding_provider=provider, top_k=5)


def test_retrieve_returns_retrieval_result(retriever):
    result = retriever.retrieve("What is HelixDB?")
    assert isinstance(result, RetrievalResult)
    assert result.query == "What is HelixDB?"
    assert result.retrieval_method == "semantic"
    assert len(result.evidence) > 0


def test_retrieve_evidence_contract(retriever):
    result = retriever.retrieve("What technology did Vector Labs develop?")
    for ev in result.evidence:
        assert isinstance(ev, Evidence)
        assert ev.chunk_id
        assert ev.document_id
        assert ev.text
        assert isinstance(ev.score, float)
        assert ev.retrieval_method == "semantic"
        assert ev.evidence_origin == "document/chunk"


def test_retrieve_metadata_present(retriever):
    result = retriever.retrieve("What is HelixDB?")
    assert "embedding_model" in result.metadata
    assert "similarity_metric" in result.metadata
    assert result.metadata["similarity_metric"] == "cosine"


def test_retrieve_scores_descending(retriever):
    result = retriever.retrieve("What is HelixDB?", top_k=5)
    scores = result.scores
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1]


def test_retrieve_deterministic(retriever):
    r1 = retriever.retrieve("What is HelixDB?")
    r2 = retriever.retrieve("What is HelixDB?")
    assert r1.top_chunk_ids == r2.top_chunk_ids
    assert r1.scores == r2.scores