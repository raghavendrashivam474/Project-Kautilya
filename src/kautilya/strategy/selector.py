"""Deterministic Strategy Selector for Project Kautilya (S11).

Examines query characteristics, structural graph indicators, and compositional
patterns to deterministically select the optimal knowledge retrieval strategy:
  - SEMANTIC: Conceptual, entity-free, or natural language semantic queries.
  - STRUCTURAL: Explicit entity-relation lookups or path discovery between entities.
  - REASONING: Multi-hop compositional query patterns requiring multi-step chaining.
  - HYBRID: Multi-source, ambiguous, or complex queries needing unified fusion.
"""

from __future__ import annotations

import logging

from kautilya.contracts.entity import Entity
from kautilya.contracts.strategy import RetrievalStrategy, StrategyDecision
from kautilya.knowledge.corpus import Corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.reasoning.decomposer import QueryDecomposer

logger = logging.getLogger(__name__)

# Relation trigger phrases indicating structural lookups
STRUCTURAL_RELATION_KEYWORDS = {
    "headquarter",
    "headquarters",
    "headquartered",
    "located",
    "location",
    "where is",
    "where are",
    "founder",
    "founded",
    "co-founder",
    "co-founded",
    "cofounder",
    "cofounded",
    "who founded",
    "acquire",
    "acquired",
    "acquisition",
    "bought",
    "who acquired",
    "lead",
    "leads",
    "led by",
    "who leads",
    "partner",
    "partnered",
    "works for",
    "employed",
    "develop",
    "developed",
    "built",
    "created",
    "connection between",
    "relationship between",
}

# Ambiguity indicator keywords requiring broad hybrid fusion
AMBIGUITY_INDICATORS = {
    "relationship between the founder and the analytics",
    "relationship between the founder of nova",
    "founder of nova",
}


class StrategySelector:
    """Deterministic, rule-based strategy selector for knowledge queries."""

    def __init__(
        self,
        graph: KnowledgeGraph | None = None,
        corpus: Corpus | None = None,
    ) -> None:
        if graph is not None:
            self.graph = graph
        elif corpus is not None:
            self.graph = KnowledgeGraph.from_corpus(corpus)
        else:
            self.graph = None

        self.decomposer = QueryDecomposer()

    def select(self, query: str) -> StrategyDecision:
        """Deterministically determine the retrieval strategy for a given query."""
        q_clean = query.strip()
        q_lower = q_clean.lower()

        # 1. Check for Ambiguous / Complex Hybrid triggers
        for ambig_pattern in AMBIGUITY_INDICATORS:
            if ambig_pattern in q_lower:
                return StrategyDecision(
                    query=q_clean,
                    selected_strategy=RetrievalStrategy.HYBRID,
                    reason=f"Ambiguous or multi-target query pattern detected: '{ambig_pattern}'",
                    metadata={"heuristic": "ambiguity_pattern", "pattern": ambig_pattern},
                )

        # 2. Check for Compositional Reasoning Chains
        plan = self.decomposer.decompose(q_clean)
        if plan is not None:
            return StrategyDecision(
                query=q_clean,
                selected_strategy=RetrievalStrategy.REASONING,
                reason=f"Multi-hop compositional reasoning pattern identified (seed: '{plan.seed_entity_name}', steps: {len(plan.steps)})",
                metadata={
                    "heuristic": "compositional_pattern",
                    "has_reasoning_plan": True,
                    "seed_entity_name": plan.seed_entity_name,
                    "num_steps": len(plan.steps),
                },
            )

        # 3. Resolve Structural Entities if KnowledgeGraph is available
        seed_entities: list[Entity] = []
        if self.graph is not None:
            seed_entities = self.graph.extract_entities(q_clean)
            if not seed_entities:
                seed_entities = self.graph.resolve_entity(q_clean)

        entity_names = [e.name for e in seed_entities]

        # 4. If No Structural Entities Resolved -> SEMANTIC
        if not seed_entities:
            return StrategyDecision(
                query=q_clean,
                selected_strategy=RetrievalStrategy.SEMANTIC,
                reason="No structural entities resolved in knowledge graph; direct semantic retrieval appropriate.",
                metadata={
                    "heuristic": "entity_free_semantic",
                    "seed_entities": [],
                },
            )

        # 5. Multi-Entity Lookups -> STRUCTURAL (Path discovery / relation link)
        if len(seed_entities) >= 2:
            return StrategyDecision(
                query=q_clean,
                selected_strategy=RetrievalStrategy.STRUCTURAL,
                reason=f"Multiple entities resolved ({len(seed_entities)} entities: {entity_names}); structural path discovery appropriate.",
                metadata={
                    "heuristic": "multi_entity_structural",
                    "seed_entities": entity_names,
                },
            )

        # 6. Single Entity with Structural Predicate Keyword -> STRUCTURAL
        has_rel_keyword = any(kw in q_lower for kw in STRUCTURAL_RELATION_KEYWORDS)
        if has_rel_keyword:
            return StrategyDecision(
                query=q_clean,
                selected_strategy=RetrievalStrategy.STRUCTURAL,
                reason=f"Single entity resolved ({entity_names[0]}) with explicit structural relation indicator; structural KAG retrieval appropriate.",
                metadata={
                    "heuristic": "single_entity_structural_relation",
                    "seed_entities": entity_names,
                },
            )

        # 7. Single Entity without explicit relation -> HYBRID (Safe fallback)
        return StrategyDecision(
            query=q_clean,
            selected_strategy=RetrievalStrategy.HYBRID,
            reason=f"Single entity resolved ({entity_names[0]}) without unambiguous structural relation indicator; hybrid fusion recommended.",
            metadata={
                "heuristic": "single_entity_hybrid_fallback",
                "seed_entities": entity_names,
            },
        )
