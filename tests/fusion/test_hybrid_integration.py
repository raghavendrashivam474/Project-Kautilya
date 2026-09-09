"""Integration test for hybrid fusion against the real S1 corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.fusion.evidence_fusion import EvidenceFusion
from kautilya.infrastructure.embeddings import SentenceTransformerProvider
from kautilya.knowledge.corpus import load_corpus
from kautilya.retrieval.semantic import SemanticRetriever
from kautilya.retrieval.structural import KAGRetriever


@pytest.fixture(scope="module")
def corpus():
    root = Path(__file__).resolve().parents[2]
    return load_corpus(
        corpus_dir=root / "data" / "corpus",
        knowledge_dir=root / "data" / "knowledge",
    )


@pytest.fixture(scope="module")
def sem_retriever(corpus):
    provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
    return SemanticRetriever(corpus=corpus, embedding_provider=provider, top_k=5)


@pytest.fixture(scope="module")
def kag_retriever(corpus):
    return KAGRetriever(corpus=corpus, max_hops=2, top_k=5)


class TestHybridIntegration:
    def test_hybrid_returns_valid_result(self, sem_retriever, kag_retriever):
        query = "What technology did Vector Labs develop?"
        sem = sem_retriever.retrieve(query)
        kag = kag_retriever.retrieve(query)
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        assert isinstance(result, RetrievalResult)
        assert result.retrieval_method == "hybrid"
        assert len(result.evidence) > 0
        for ev in result.evidence:
            assert isinstance(ev, Evidence)
            assert ev.chunk_id
            assert ev.document_id

    def test_hybrid_promotes_agreed_evidence(self, sem_retriever, kag_retriever):
        """chunk_005_001 (contains 'HelixDB' + 'acquired') should surface at top for Vector Labs query."""
        query = "What technology did Vector Labs develop?"
        sem = sem_retriever.retrieve(query)
        kag = kag_retriever.retrieve(query)
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        top_chunk = result.evidence[0].chunk_id
        assert top_chunk == "chunk_005_001", (
            f"Expected chunk_005_001 (the acquisition/HelixDB chunk) at #1; got {top_chunk}"
        )
        assert result.evidence[0].metadata["agreement"] is True

    def test_hybrid_deterministic_end_to_end(self, sem_retriever, kag_retriever):
        query = "Who acquired Vector Labs?"
        sem = sem_retriever.retrieve(query)
        kag = kag_retriever.retrieve(query)
        fusion = EvidenceFusion()
        r1 = fusion.fuse(sem, kag, top_k=5)
        r2 = fusion.fuse(sem, kag, top_k=5)
        assert [ev.chunk_id for ev in r1.evidence] == [ev.chunk_id for ev in r2.evidence]
        assert [ev.score for ev in r1.evidence] == [ev.score for ev in r2.evidence]

    def test_hybrid_metadata_populated(self, sem_retriever, kag_retriever):
        query = "Who founded Nova Systems?"
        sem = sem_retriever.retrieve(query)
        kag = kag_retriever.retrieve(query)
        result = EvidenceFusion().fuse(sem, kag, top_k=5)
        md = result.metadata
        assert md["semantic_count"] > 0
        assert md["structural_count"] > 0
        assert md["unique_chunks"] >= 1
        assert "fusion_weights" in md
        assert md["normalization"] == "rank_based"
