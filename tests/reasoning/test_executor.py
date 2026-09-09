"""Tests for the reasoning executor against the real knowledge graph."""

from pathlib import Path

import pytest

from kautilya.contracts.reasoning import (
    Direction,
    ReasoningPlan,
    ReasoningStatus,
    ReasoningStep,
)
from kautilya.knowledge.corpus import load_corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.reasoning.decomposer import QueryDecomposer
from kautilya.reasoning.executor import ReasoningExecutor

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def graph() -> KnowledgeGraph:
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
    corpus = load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)
    return KnowledgeGraph.from_corpus(corpus)


@pytest.fixture()
def executor(graph: KnowledgeGraph) -> ReasoningExecutor:
    return ReasoningExecutor(graph, max_hops=2)


# --- Q22: Pattern A ---
def test_q22_full_chain(executor: ReasoningExecutor):
    """Vector Labs -> ACQUIRED(incoming) -> Nova Systems -> FOUNDED(incoming) -> Rohan Kapoor."""
    plan = QueryDecomposer().decompose(
        "Who founded the company that acquired Vector Labs?"
    )
    assert plan is not None

    trace = executor.execute(plan)

    assert trace.is_success, f"Trace failed: {trace.to_dict()}"
    assert trace.terminal_entity_name is not None
    assert "rohan" in trace.terminal_entity_name.lower()
    assert len(trace.hops) == 2

    # Hop 1: Vector Labs <--ACQUIRED-- Nova Systems
    assert trace.hops[0].source_entity_name == "Vector Labs"
    assert trace.hops[0].relation_type == "ACQUIRED"
    assert trace.hops[0].target_entity_name is not None
    assert "nova" in trace.hops[0].target_entity_name.lower()
    assert "chunk_005_001" in trace.hops[0].chunk_ids

    # Hop 2: Nova Systems <--FOUNDED-- Rohan Kapoor
    assert trace.hops[1].relation_type == "FOUNDED"
    assert trace.hops[1].target_entity_name is not None
    assert "rohan" in trace.hops[1].target_entity_name.lower()
    assert len(trace.hops[1].chunk_ids) > 0


# --- Q24: Pattern B ---
def test_q24_full_chain(executor: ReasoningExecutor):
    """Nova Systems -> ACQUIRED(outgoing) -> Vector Labs -> CO_FOUNDED(incoming) -> Mira Sharma / Anand Iyer."""
    plan = QueryDecomposer().decompose(
        "Who co-founded the company that Nova Systems acquired?"
    )
    assert plan is not None

    trace = executor.execute(plan)

    assert trace.is_success, f"Trace failed: {trace.to_dict()}"
    assert trace.terminal_entity_name is not None
    assert len(trace.hops) == 2

    # Hop 1: Nova Systems --ACQUIRED--> Vector Labs
    assert "nova" in trace.hops[0].source_entity_name.lower()
    assert trace.hops[0].target_entity_name is not None
    assert "vector" in trace.hops[0].target_entity_name.lower()

    # Hop 2: Vector Labs <--CO_FOUNDED-- co-founder
    assert trace.hops[1].relation_type == "CO_FOUNDED"
    assert trace.hops[1].target_entity_name is not None
    assert "chunk_002_001" in trace.hops[1].chunk_ids


# --- Q21: Pattern C ---
def test_q21_full_chain(executor: ReasoningExecutor):
    """HelixDB -> DEVELOPED(incoming) -> Vector Labs -> ACQUIRED(incoming) -> Nova Systems."""
    plan = QueryDecomposer().decompose(
        "Who acquired the company that developed HelixDB?"
    )
    assert plan is not None

    trace = executor.execute(plan)
    assert trace.is_success, f"Trace failed: {trace.to_dict()}"
    assert "nova" in trace.terminal_entity_name.lower()
    assert len(trace.hops) == 2
    assert "chunk_005_001" in trace.hops[1].chunk_ids


# --- Q23: Pattern D ---
def test_q23_full_chain(executor: ReasoningExecutor):
    """HelixDB -> DEVELOPED(incoming) -> Vector Labs -> PARTNERED_WITH(incoming) -> Meridian Cloud."""
    plan = QueryDecomposer().decompose(
        "Which cloud provider works with the company that built HelixDB?"
    )
    assert plan is not None

    trace = executor.execute(plan)
    assert trace.is_success, f"Trace failed: {trace.to_dict()}"
    assert "meridian" in trace.terminal_entity_name.lower()
    assert len(trace.hops) == 2
    assert "chunk_011_001" in trace.hops[1].chunk_ids


# --- Failure modes ---
def test_entity_resolution_failure(executor: ReasoningExecutor):
    plan = ReasoningPlan(
        query="test",
        seed_entity_name="NonexistentCorp",
        steps=(
            ReasoningStep("ACQUIRED", Direction.INCOMING, 1),
        ),
    )
    trace = executor.execute(plan)
    assert trace.status == ReasoningStatus.ENTITY_RESOLUTION_FAILURE
    assert trace.hops == ()


def test_relation_failure(executor: ReasoningExecutor):
    plan = ReasoningPlan(
        query="test",
        seed_entity_name="Vector Labs",
        steps=(
            ReasoningStep("MANUFACTURED_BY", Direction.INCOMING, 1),
        ),
    )
    trace = executor.execute(plan)
    assert trace.status == ReasoningStatus.RELATION_FAILURE
    assert len(trace.hops) == 1
    assert trace.hops[0].target_entity_id is None


def test_max_hops_exceeded(graph: KnowledgeGraph):
    executor = ReasoningExecutor(graph, max_hops=1)
    plan = ReasoningPlan(
        query="test",
        seed_entity_name="Vector Labs",
        steps=(
            ReasoningStep("ACQUIRED", Direction.INCOMING, 1),
            ReasoningStep("FOUNDED", Direction.INCOMING, 2),
        ),
    )
    trace = executor.execute(plan)
    assert trace.status == ReasoningStatus.TRAVERSAL_FAILURE


# --- Determinism ---
def test_execution_is_deterministic(executor: ReasoningExecutor):
    plan = QueryDecomposer().decompose(
        "Who founded the company that acquired Vector Labs?"
    )
    assert plan is not None
    traces = [executor.execute(plan) for _ in range(10)]
    assert all(t == traces[0] for t in traces)
