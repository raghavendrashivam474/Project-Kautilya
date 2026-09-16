"""Unit tests for S11 Strategy Selection contracts."""

from dataclasses import FrozenInstanceError

import pytest

from kautilya.contracts.strategy import RetrievalStrategy, StrategyDecision


def test_retrieval_strategy_enum_values():
    """Ensure all required strategy enum variants exist with expected string values."""
    assert RetrievalStrategy.SEMANTIC.value == "semantic"
    assert RetrievalStrategy.STRUCTURAL.value == "structural"
    assert RetrievalStrategy.REASONING.value == "reasoning"
    assert RetrievalStrategy.HYBRID.value == "hybrid"


def test_strategy_decision_creation_and_immutability():
    """Ensure StrategyDecision is frozen and holds correct fields."""
    decision = StrategyDecision(
        query="Who founded Nova AI?",
        selected_strategy=RetrievalStrategy.STRUCTURAL,
        reason="Explicit single-entity relation query",
        metadata={"seed_entities": ["Nova AI"], "matched_relation": "FOUNDER"},
    )

    assert decision.query == "Who founded Nova AI?"
    assert decision.selected_strategy == RetrievalStrategy.STRUCTURAL
    assert decision.reason == "Explicit single-entity relation query"
    assert decision.metadata["seed_entities"] == ["Nova AI"]

    # Verify immutability
    with pytest.raises(FrozenInstanceError):
        decision.selected_strategy = RetrievalStrategy.SEMANTIC  # type: ignore[misc]


def test_strategy_decision_serialization():
    """Ensure StrategyDecision converts deterministically to dictionary representation."""
    decision = StrategyDecision(
        query="What is machine learning?",
        selected_strategy=RetrievalStrategy.SEMANTIC,
        reason="Direct conceptual query with no structural entities",
        metadata={"confidence": 1.0},
    )

    d = decision.to_dict()
    assert d == {
        "query": "What is machine learning?",
        "selected_strategy": "semantic",
        "reason": "Direct conceptual query with no structural entities",
        "metadata": {"confidence": 1.0},
    }
