"""Tests for the deterministic query decomposer across compositional patterns."""

from kautilya.contracts.reasoning import Direction
from kautilya.reasoning.decomposer import QueryDecomposer


def _d() -> QueryDecomposer:
    return QueryDecomposer()


# --- Pattern A ---
def test_pattern_a_q22():
    plan = _d().decompose(
        "Who founded the company that acquired Vector Labs?"
    )
    assert plan is not None
    assert "Vector Labs" in plan.seed_entity_name
    assert plan.num_hops == 2
    assert plan.steps[0].relation_type == "ACQUIRED"
    assert plan.steps[0].direction == Direction.INCOMING
    assert plan.steps[1].relation_type == "FOUNDED"
    assert plan.steps[1].direction == Direction.INCOMING


# --- Pattern B ---
def test_pattern_b_q24():
    plan = _d().decompose(
        "Who co-founded the company that Nova Systems acquired?"
    )
    assert plan is not None
    assert "Nova Systems" in plan.seed_entity_name
    assert plan.num_hops == 2
    assert plan.steps[0].relation_type == "ACQUIRED"
    assert plan.steps[0].direction == Direction.OUTGOING
    assert plan.steps[1].relation_type == "CO_FOUNDED"
    assert plan.steps[1].direction == Direction.INCOMING


# --- Pattern C ---
def test_pattern_c_q21():
    plan = _d().decompose(
        "Who acquired the company that developed HelixDB?"
    )
    assert plan is not None
    assert "HelixDB" in plan.seed_entity_name
    assert plan.num_hops == 2
    assert plan.steps[0].relation_type == "DEVELOPED"
    assert plan.steps[0].direction == Direction.INCOMING
    assert plan.steps[1].relation_type == "ACQUIRED"
    assert plan.steps[1].direction == Direction.INCOMING


# --- Pattern D ---
def test_pattern_d_q23():
    plan = _d().decompose(
        "Which cloud provider works with the company that built HelixDB?"
    )
    assert plan is not None
    assert "HelixDB" in plan.seed_entity_name
    assert plan.num_hops == 2
    assert plan.steps[0].relation_type == "DEVELOPED"
    assert plan.steps[0].direction == Direction.INCOMING
    assert plan.steps[1].relation_type == "PARTNERED_WITH"
    assert plan.steps[1].direction == Direction.INCOMING


# --- Pattern E ---
def test_pattern_e():
    plan = _d().decompose(
        "What technology was developed by the company that Nova Systems acquired?"
    )
    assert plan is not None
    assert "Nova Systems" in plan.seed_entity_name
    assert plan.num_hops == 2
    assert plan.steps[0].relation_type == "ACQUIRED"
    assert plan.steps[0].direction == Direction.OUTGOING
    assert plan.steps[1].relation_type == "DEVELOPED"
    assert plan.steps[1].direction == Direction.OUTGOING


# --- Failures & Determinism ---
def test_unrelated_question_returns_none():
    assert _d().decompose("What is the capital of France?") is None


def test_simple_entity_question_returns_none():
    assert _d().decompose("Who founded Vector Labs?") is None


def test_decomposition_is_deterministic():
    q = "Who founded the company that acquired Vector Labs?"
    results = [_d().decompose(q) for _ in range(10)]
    assert all(r == results[0] for r in results)
