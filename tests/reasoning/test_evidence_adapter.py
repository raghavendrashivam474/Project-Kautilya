"""Tests for the evidence adapter — trace to RetrievalResult."""

from pathlib import Path

import pytest

from kautilya.contracts.reasoning import (
    Direction,
    ReasoningPlan,
    ReasoningStep,
)
from kautilya.knowledge.corpus import load_corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.reasoning.decomposer import QueryDecomposer
from kautilya.reasoning.evidence_adapter import _chunk_to_doc_id, trace_to_retrieval_result
from kautilya.reasoning.executor import ReasoningExecutor

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def graph() -> KnowledgeGraph:
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    return KnowledgeGraph.from_corpus(corpus)


def test_q22_end_to_end(graph: KnowledgeGraph):
    """Decompose -> Execute -> Adapt -> RetrievalResult with chunks."""
    plan = QueryDecomposer().decompose(
        "Who founded the company that acquired Vector Labs?"
    )
    assert plan is not None

    trace = ReasoningExecutor(graph).execute(plan)
    assert trace.is_success

    result = trace_to_retrieval_result(trace)
    assert result.retrieval_method == "reasoning"

    chunk_ids = result.top_chunk_ids
    assert len(chunk_ids) >= 2
    assert "chunk_005_001" in chunk_ids

    assert result.metadata["terminal_entity"] is not None
    assert "rohan" in result.metadata["terminal_entity"].lower()


def test_failed_trace_produces_empty_result(graph: KnowledgeGraph):
    plan = ReasoningPlan(
        query="test",
        seed_entity_name="NonexistentCorp",
        steps=(ReasoningStep("ACQUIRED", Direction.INCOMING, 1),),
    )
    trace = ReasoningExecutor(graph).execute(plan)
    result = trace_to_retrieval_result(trace)
    assert result.retrieval_method == "reasoning"
    assert result.top_chunk_ids == []
    assert result.metadata["status"] == "F2"


def test_chunk_to_doc_id():
    assert _chunk_to_doc_id("chunk_005_001") == "doc_005"
    assert _chunk_to_doc_id("chunk_012_001") == "doc_012"
