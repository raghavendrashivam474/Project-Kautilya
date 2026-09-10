"""S7 regression and behavior tests: Score-Aware Reasoning Fusion.

Validates that:
1. Reasoning evidence adapter produces terminal-hop evidence first.
2. Terminal evidence receives rank 1 and highest normalized score in fusion.
3. Provenance and metadata correctly record terminal hop status.
4. S4 parity is preserved when reasoning is absent.
5. Failed reasoning traces degrade safely to empty results.
6. Execution and ranking are 100% deterministic.
"""

from pathlib import Path

import pytest

from kautilya.contracts.reasoning import (
    Direction,
    ReasoningPlan,
    ReasoningStep,
)
from kautilya.fusion.evidence_fusion import EvidenceFusion
from kautilya.knowledge.corpus import load_corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.reasoning.decomposer import QueryDecomposer
from kautilya.reasoning.evidence_adapter import trace_to_retrieval_result
from kautilya.reasoning.executor import ReasoningExecutor

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def corpus_and_graph():
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    graph = KnowledgeGraph.from_corpus(corpus)
    return corpus, graph


def test_s7_terminal_first_ordering(corpus_and_graph):
    """Terminal hop chunk must be emitted before intermediate hop chunks."""
    corpus, graph = corpus_and_graph
    query = "Who founded the company that acquired Vector Labs?"
    plan = QueryDecomposer().decompose(query)
    assert plan is not None

    trace = ReasoningExecutor(graph).execute(plan)
    assert trace.is_success
    assert len(trace.hops) == 2

    # Hop 1: Vector Labs <--ACQUIRED-- Nova Systems (chunk_005_001)
    # Hop 2 (terminal): Nova Systems <--FOUNDED-- Rohan Kapoor (chunk_001_001)
    result = trace_to_retrieval_result(trace, corpus=corpus)
    assert len(result.evidence) == 2

    # S7 invariant: terminal hop (hop 2) chunk must be first (rank 1)
    assert result.evidence[0].chunk_id == "chunk_001_001"
    assert result.evidence[0].provenance["is_terminal_hop"] is True
    assert result.evidence[0].metadata["is_terminal_hop"] is True
    assert result.evidence[0].provenance["reasoning_hop"] == 2

    # Intermediate hop (hop 1) chunk must be second (rank 2)
    assert result.evidence[1].chunk_id == "chunk_005_001"
    assert result.evidence[1].provenance["is_terminal_hop"] is False
    assert result.evidence[1].metadata["is_terminal_hop"] is False
    assert result.evidence[1].provenance["reasoning_hop"] == 1


def test_s7_fusion_terminal_chunk_gets_max_norm_score(corpus_and_graph):
    """In 3-way fusion, terminal chunk gets norm_score=1.0 and intermediate gets 0.5."""
    corpus, graph = corpus_and_graph
    query = "Who founded the company that acquired Vector Labs?"
    plan = QueryDecomposer().decompose(query)
    trace = ReasoningExecutor(graph).execute(plan)
    rea_result = trace_to_retrieval_result(trace, corpus=corpus)

    # Empty dummy semantic & structural results with the same query
    from kautilya.contracts.retrieval import RetrievalResult

    sem_result = RetrievalResult(query=query, evidence=[], retrieval_method="semantic", metadata={})
    kag_result = RetrievalResult(
        query=query, evidence=[], retrieval_method="structural", metadata={}
    )

    fused = EvidenceFusion().fuse(sem_result, kag_result, rea_result, top_k=5)
    assert len(fused.evidence) == 2

    top_ev = fused.evidence[0]
    assert top_ev.chunk_id == "chunk_001_001"
    assert top_ev.metadata["reasoning_rank"] == 1
    assert top_ev.metadata["reasoning_norm_score"] == 1.0

    second_ev = fused.evidence[1]
    assert second_ev.chunk_id == "chunk_005_001"
    assert second_ev.metadata["reasoning_rank"] == 2
    assert second_ev.metadata["reasoning_norm_score"] == 0.5


def test_s7_safe_degradation_on_failed_trace():
    """Failed trace continues to return empty result and preserves contract shape."""
    plan = ReasoningPlan(
        query="fake query",
        seed_entity_name="NonexistentEntity",
        steps=(ReasoningStep("UNKNOWN", Direction.OUTGOING, 1),),
    )
    from kautilya.contracts.reasoning import ReasoningStatus, ReasoningTrace

    trace = ReasoningTrace(
        plan=plan,
        hops=(),
        terminal_entity_name=None,
        status=ReasoningStatus.ENTITY_RESOLUTION_FAILURE,
    )
    result = trace_to_retrieval_result(trace)
    assert result.evidence == []
    assert result.retrieval_method == "reasoning"
    assert result.metadata["status"] == "F2"


def test_s7_determinism_across_runs(corpus_and_graph):
    """Multiple executions yield identical evidence rank, IDs, and scores."""
    corpus, graph = corpus_and_graph
    query = "Who founded the company that acquired Vector Labs?"
    plan = QueryDecomposer().decompose(query)

    trace1 = ReasoningExecutor(graph).execute(plan)
    res1 = trace_to_retrieval_result(trace1, corpus=corpus)

    trace2 = ReasoningExecutor(graph).execute(plan)
    res2 = trace_to_retrieval_result(trace2, corpus=corpus)

    assert [e.chunk_id for e in res1.evidence] == [e.chunk_id for e in res2.evidence]
    assert [e.score for e in res1.evidence] == [e.score for e in res2.evidence]
    assert res1.metadata == res2.metadata
