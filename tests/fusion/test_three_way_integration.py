"""Integration tests for S6 reasoning-aware fusion against the real corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from kautilya.contracts.reasoning import ReasoningPlan, ReasoningStatus, ReasoningTrace
from kautilya.fusion.evidence_fusion import EvidenceFusion
from kautilya.infrastructure.embeddings import SentenceTransformerProvider
from kautilya.knowledge.corpus import load_corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.reasoning.decomposer import QueryDecomposer
from kautilya.reasoning.evidence_adapter import trace_to_retrieval_result
from kautilya.reasoning.executor import ReasoningExecutor
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
def semantic_retriever(corpus):
    provider = SentenceTransformerProvider("all-MiniLM-L6-v2")
    return SemanticRetriever(corpus=corpus, embedding_provider=provider, top_k=5)


@pytest.fixture(scope="module")
def kag_retriever(corpus):
    return KAGRetriever(corpus=corpus, max_hops=2, top_k=5)


@pytest.fixture(scope="module")
def reasoning_pipeline(corpus):
    graph = KnowledgeGraph.from_corpus(corpus)
    decomposer = QueryDecomposer()
    executor = ReasoningExecutor(graph, max_hops=2)
    return decomposer, executor, corpus


class TestReasoningHybridIntegration:
    """End-to-end integration tests using the real corpus and retrievers."""

    def test_three_way_fusion_end_to_end_on_multi_hop_query(
        self,
        semantic_retriever,
        kag_retriever,
        reasoning_pipeline,
    ) -> None:
        query = "Who founded the company that acquired Vector Labs?"
        decomposer, executor, corpus_ref = reasoning_pipeline

        sem_res = semantic_retriever.retrieve(query, top_k=5)
        kag_res = kag_retriever.retrieve(query, top_k=5)

        plan = decomposer.decompose(query)
        assert plan is not None
        trace = executor.execute(plan)
        assert trace.is_success
        rea_res = trace_to_retrieval_result(trace, corpus=corpus_ref)

        fusion = EvidenceFusion()
        fused = fusion.fuse(sem_res, kag_res, rea_res, top_k=5)

        # Acquisition chunk chunk_005_001 must be rank 1 with 3-source agreement
        assert fused.top_chunk_ids[0] == "chunk_005_001"
        assert fused.evidence[0].metadata["agreement"] is True
        assert set(fused.evidence[0].metadata["fusion_sources"]) == {
            "semantic",
            "structural",
            "reasoning",
        }
        assert fused.metadata["reasoning_participated"] is True

    def test_q24_recovers_ground_truth_chunk_in_top_k(
        self,
        semantic_retriever,
        kag_retriever,
        reasoning_pipeline,
    ) -> None:
        query = "Who co-founded the company that Nova Systems acquired?"
        decomposer, executor, corpus_ref = reasoning_pipeline

        sem_res = semantic_retriever.retrieve(query, top_k=5)
        kag_res = kag_retriever.retrieve(query, top_k=5)

        plan = decomposer.decompose(query)
        assert plan is not None
        trace = executor.execute(plan)
        assert trace.is_success
        rea_res = trace_to_retrieval_result(trace, corpus=corpus_ref)

        fusion = EvidenceFusion()
        fused = fusion.fuse(sem_res, kag_res, rea_res, top_k=5)

        # chunk_002_001 (Mira Sharma & Anand Iyer founding Vector Labs) is recovered into top 4
        assert "chunk_002_001" in fused.top_chunk_ids

    def test_semantic_friendly_query_safe_from_reasoning_interference(
        self,
        semantic_retriever,
        kag_retriever,
        reasoning_pipeline,
    ) -> None:
        query = "What distributed database engine specializes in high-throughput vector search?"
        decomposer, _executor, corpus_ref = reasoning_pipeline

        sem_res = semantic_retriever.retrieve(query, top_k=5)
        kag_res = kag_retriever.retrieve(query, top_k=5)

        plan = decomposer.decompose(query)
        assert plan is None  # Safe decomposition failure

        trace = ReasoningTrace(
            plan=ReasoningPlan(query=query, seed_entity_name="", steps=()),
            hops=(),
            terminal_entity_name=None,
            status=ReasoningStatus.DECOMPOSITION_FAILURE,
        )
        rea_res = trace_to_retrieval_result(trace, corpus=corpus_ref)

        fusion = EvidenceFusion()
        fused = fusion.fuse(sem_res, kag_res, rea_res, top_k=5)

        # When reasoning fails, fused output matches standard 2-way fusion
        fused_s4 = fusion.fuse(sem_res, kag_res, top_k=5)
        assert fused.top_chunk_ids == fused_s4.top_chunk_ids
        assert fused.scores == fused_s4.scores
        assert fused.metadata["reasoning_participated"] is False

    def test_deterministic_output_across_repeated_runs(
        self,
        semantic_retriever,
        kag_retriever,
        reasoning_pipeline,
    ) -> None:
        query = "Who co-founded the company that Nova Systems acquired?"
        decomposer, executor, corpus_ref = reasoning_pipeline

        sem_res = semantic_retriever.retrieve(query, top_k=5)
        kag_res = kag_retriever.retrieve(query, top_k=5)
        plan = decomposer.decompose(query)
        trace = executor.execute(plan)
        rea_res = trace_to_retrieval_result(trace, corpus=corpus_ref)

        fusion = EvidenceFusion()
        run1 = fusion.fuse(sem_res, kag_res, rea_res, top_k=5)
        run2 = fusion.fuse(sem_res, kag_res, rea_res, top_k=5)

        assert run1.top_chunk_ids == run2.top_chunk_ids
        assert run1.scores == run2.scores
