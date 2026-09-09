"""Tests for S5 reasoning contracts — immutability, equality, determinism."""

from kautilya.contracts.reasoning import (
    Direction,
    HopResult,
    ReasoningPlan,
    ReasoningStatus,
    ReasoningStep,
    ReasoningTrace,
)


def _sample_plan() -> ReasoningPlan:
    return ReasoningPlan(
        query="Who founded the company that acquired Vector Labs?",
        seed_entity_name="Vector Labs",
        steps=(
            ReasoningStep("ACQUIRED", Direction.INCOMING, 1),
            ReasoningStep("FOUNDED", Direction.INCOMING, 2),
        ),
    )


def test_plan_is_frozen():
    plan = _sample_plan()
    import pytest

    with pytest.raises(AttributeError):
        plan.query = "changed"  # type: ignore[misc]


def test_plan_num_hops():
    assert _sample_plan().num_hops == 2


def test_plan_deterministic_equality():
    assert _sample_plan() == _sample_plan()


def test_plan_to_dict_roundtrip():
    d = _sample_plan().to_dict()
    assert d["seed_entity_name"] == "Vector Labs"
    assert len(d["steps"]) == 2
    assert d["steps"][0]["relation_type"] == "ACQUIRED"
    assert d["steps"][0]["direction"] == "incoming"


def test_hop_result_frozen():
    hop = HopResult(
        hop_index=1,
        source_entity_id="e1",
        source_entity_name="Vector Labs",
        relation_type="ACQUIRED",
        direction=Direction.INCOMING,
        target_entity_id="e2",
        target_entity_name="Nova Systems",
        chunk_ids=("chunk_005_001",),
        status=ReasoningStatus.SUCCESS,
    )
    import pytest

    with pytest.raises(AttributeError):
        hop.target_entity_name = "changed"  # type: ignore[misc]


def test_trace_is_success():
    plan = _sample_plan()
    trace = ReasoningTrace(
        plan=plan,
        hops=(),
        terminal_entity_name="Rohan Kapoor",
        status=ReasoningStatus.SUCCESS,
    )
    assert trace.is_success is True

    trace_fail = ReasoningTrace(
        plan=plan,
        hops=(),
        terminal_entity_name=None,
        status=ReasoningStatus.RELATION_FAILURE,
    )
    assert trace_fail.is_success is False


def test_trace_to_dict():
    plan = _sample_plan()
    trace = ReasoningTrace(
        plan=plan,
        hops=(
            HopResult(
                hop_index=1,
                source_entity_id="e1",
                source_entity_name="Vector Labs",
                relation_type="ACQUIRED",
                direction=Direction.INCOMING,
                target_entity_id="e2",
                target_entity_name="Nova Systems",
                chunk_ids=("chunk_005_001",),
                status=ReasoningStatus.SUCCESS,
            ),
        ),
        terminal_entity_name="Nova Systems",
        status=ReasoningStatus.SUCCESS,
    )
    d = trace.to_dict()
    assert d["status"] == "success"
    assert d["hops"][0]["target"] == "Nova Systems"
