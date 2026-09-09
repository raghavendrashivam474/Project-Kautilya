"""Deterministic query decomposer for compositional questions.

Pattern-based query decomposition into explicit ReasoningPlans.
Returns None when the query does not match any known compositional pattern
(explicit F1 decomposition failure).

Supported compositional chains:
  - Pattern A: "Who founded the company that acquired {X}?"
      Chain: X <--ACQUIRED-- ? <--FOUNDED-- ?
  - Pattern B: "Who co-founded the company that {Y} acquired?"
      Chain: Y --ACQUIRED--> ? <--CO_FOUNDED-- ?
  - Pattern C: "Who acquired the company that developed {X}?"
      Chain: X <--DEVELOPED-- ? <--ACQUIRED-- ?
  - Pattern D: "Which cloud provider / partner works with the company that built/developed {X}?"
      Chain: X <--DEVELOPED-- ? <--PARTNERED_WITH-- ?
  - Pattern E: "What technology / product was developed by the company that {Y} acquired?"
      Chain: Y --ACQUIRED--> ? --DEVELOPED--> ?
"""

from __future__ import annotations

import re

from kautilya.contracts.reasoning import (
    Direction,
    ReasoningPlan,
    ReasoningStep,
)


class QueryDecomposer:
    """Decompose compositional questions into multi-hop reasoning plans."""

    def decompose(self, query: str) -> ReasoningPlan | None:
        q = query.strip().rstrip("?").strip()
        q_lower = q.lower()

        # --- Pattern A: "who founded the company that acquired {X}" ---
        if "founded the company that acquired" in q_lower:
            seed = self._extract_after(q, "acquired")
            if seed:
                return ReasoningPlan(
                    query=query,
                    seed_entity_name=seed,
                    steps=(
                        ReasoningStep("ACQUIRED", Direction.INCOMING, 1),
                        ReasoningStep("FOUNDED", Direction.INCOMING, 2),
                    ),
                )

        # --- Pattern B: "who co-founded the company that {Y} acquired" ---
        if "co-founded the company that" in q_lower and "acquired" in q_lower:
            seed = self._extract_between(q, "that", "acquired")
            if seed:
                return ReasoningPlan(
                    query=query,
                    seed_entity_name=seed,
                    steps=(
                        ReasoningStep("ACQUIRED", Direction.OUTGOING, 1),
                        ReasoningStep("CO_FOUNDED", Direction.INCOMING, 2),
                    ),
                )

        # --- Pattern C: "who acquired the company that developed/built {X}" ---
        if "acquired the company that" in q_lower and any(
            w in q_lower for w in ["developed", "built", "created"]
        ):
            seed = self._extract_after_any(q, ["developed", "built", "created"])
            if seed:
                return ReasoningPlan(
                    query=query,
                    seed_entity_name=seed,
                    steps=(
                        ReasoningStep("DEVELOPED", Direction.INCOMING, 1),
                        ReasoningStep("ACQUIRED", Direction.INCOMING, 2),
                    ),
                )

        # --- Pattern D: "which cloud provider / company works with / partnered with the company that built/developed {X}" ---
        if ("works with" in q_lower or "partnered with" in q_lower) and any(
            w in q_lower for w in ["developed", "built", "created"]
        ):
            seed = self._extract_after_any(q, ["developed", "built", "created"])
            if seed:
                return ReasoningPlan(
                    query=query,
                    seed_entity_name=seed,
                    steps=(
                        ReasoningStep("DEVELOPED", Direction.INCOMING, 1),
                        ReasoningStep("PARTNERED_WITH", Direction.INCOMING, 2),
                    ),
                )

        # --- Pattern E: "what technology was developed by the company that {Y} acquired" ---
        if ("technology" in q_lower or "database" in q_lower or "system" in q_lower) and (
            "acquired" in q_lower and "developed" in q_lower
        ):
            seed = self._extract_between(q, "that", "acquired") or self._extract_after(q, "after")
            if seed:
                return ReasoningPlan(
                    query=query,
                    seed_entity_name=seed,
                    steps=(
                        ReasoningStep("ACQUIRED", Direction.OUTGOING, 1),
                        ReasoningStep("DEVELOPED", Direction.OUTGOING, 2),
                    ),
                )

        return None

    @staticmethod
    def _extract_after(text: str, keyword: str) -> str | None:
        idx = text.lower().rfind(keyword.lower())
        if idx == -1:
            return None
        tail = text[idx + len(keyword):].strip()
        # Clean up punctuation and stop words
        cleaned = re.sub(r"[^\w\s]", "", tail).strip()
        return cleaned if cleaned else None

    @classmethod
    def _extract_after_any(cls, text: str, keywords: list[str]) -> str | None:
        for kw in keywords:
            if kw in text.lower():
                extracted = cls._extract_after(text, kw)
                if extracted:
                    return extracted
        return None

    @staticmethod
    def _extract_between(
        text: str, start_kw: str, end_kw: str
    ) -> str | None:
        t_low = text.lower()
        s = t_low.find(start_kw.lower())
        if s == -1:
            return None
        e = t_low.find(end_kw.lower(), s + len(start_kw))
        if e == -1:
            return None
        middle = text[s + len(start_kw): e].strip()
        cleaned = re.sub(r"[^\w\s]", "", middle).strip()
        return cleaned if cleaned else None
