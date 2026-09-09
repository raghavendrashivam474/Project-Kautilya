"""Execute reasoning plans against the KnowledgeGraph.

Walks the graph step-by-step according to the ReasoningPlan,
producing a ReasoningTrace with per-hop outcomes and failure codes.

Deterministic: same plan + same graph = same trace, always.
Bounded: respects max_hops.
Cycle-safe: tracks visited entity IDs.
"""

from __future__ import annotations

from kautilya.contracts.reasoning import (
    Direction,
    HopResult,
    ReasoningPlan,
    ReasoningStatus,
    ReasoningTrace,
)
from kautilya.knowledge.graph import KnowledgeGraph


class ReasoningExecutor:
    """Walk the KnowledgeGraph according to a ReasoningPlan."""

    def __init__(
        self, graph: KnowledgeGraph, max_hops: int = 2
    ) -> None:
        self._graph = graph
        self._max_hops = max_hops

    def execute(self, plan: ReasoningPlan) -> ReasoningTrace:
        if plan.num_hops > self._max_hops:
            return ReasoningTrace(
                plan=plan,
                hops=(),
                terminal_entity_name=None,
                status=ReasoningStatus.TRAVERSAL_FAILURE,
            )

        # --- Resolve seed entity ---
        seeds = self._graph.resolve_entity(plan.seed_entity_name)
        if not seeds:
            return ReasoningTrace(
                plan=plan,
                hops=(),
                terminal_entity_name=None,
                status=ReasoningStatus.ENTITY_RESOLUTION_FAILURE,
            )

        # Deterministic: resolve_entity returns a list; pick first
        current_id = seeds[0].id
        current_name = seeds[0].name
        hops: list[HopResult] = []
        visited: set[str] = {current_id}

        for step in plan.steps:
            # --- Get relations in the requested direction ---
            if step.direction == Direction.OUTGOING:
                relations = self._graph.get_outgoing(current_id)
            else:
                relations = self._graph.get_incoming(current_id)

            # --- Filter by relation type ---
            matching = [
                r
                for r in relations
                if r.relation_type == step.relation_type
            ]

            if not matching:
                hops.append(
                    HopResult(
                        hop_index=step.hop_index,
                        source_entity_id=current_id,
                        source_entity_name=current_name,
                        relation_type=step.relation_type,
                        direction=step.direction,
                        target_entity_id=None,
                        target_entity_name=None,
                        chunk_ids=(),
                        status=ReasoningStatus.RELATION_FAILURE,
                    )
                )
                return ReasoningTrace(
                    plan=plan,
                    hops=tuple(hops),
                    terminal_entity_name=None,
                    status=ReasoningStatus.RELATION_FAILURE,
                )

            # --- Deterministic tie-breaking: sort by target/source ID ---
            if step.direction == Direction.OUTGOING:
                matching.sort(key=lambda r: r.target_entity_id)
                rel = matching[0]
                next_id = rel.target_entity_id
            else:
                matching.sort(key=lambda r: r.source_entity_id)
                rel = matching[0]
                next_id = rel.source_entity_id

            # --- Cycle check ---
            if next_id in visited:
                hops.append(
                    HopResult(
                        hop_index=step.hop_index,
                        source_entity_id=current_id,
                        source_entity_name=current_name,
                        relation_type=step.relation_type,
                        direction=step.direction,
                        target_entity_id=next_id,
                        target_entity_name=None,
                        chunk_ids=(),
                        status=ReasoningStatus.TRAVERSAL_FAILURE,
                    )
                )
                return ReasoningTrace(
                    plan=plan,
                    hops=tuple(hops),
                    terminal_entity_name=None,
                    status=ReasoningStatus.TRAVERSAL_FAILURE,
                )

            visited.add(next_id)
            next_entity = self._graph.entities.get(next_id)
            next_name = next_entity.name if next_entity else next_id

            # Extract chunk_id from provenance
            chunk_ids = (rel.provenance.chunk_id,) if rel.provenance and rel.provenance.chunk_id else ()

            hops.append(
                HopResult(
                    hop_index=step.hop_index,
                    source_entity_id=current_id,
                    source_entity_name=current_name,
                    relation_type=step.relation_type,
                    direction=step.direction,
                    target_entity_id=next_id,
                    target_entity_name=next_name,
                    chunk_ids=chunk_ids,
                    status=ReasoningStatus.SUCCESS,
                )
            )

            # Advance
            current_id = next_id
            current_name = next_name

        terminal = hops[-1].target_entity_name if hops else None
        all_ok = all(h.status == ReasoningStatus.SUCCESS for h in hops)

        return ReasoningTrace(
            plan=plan,
            hops=tuple(hops),
            terminal_entity_name=terminal,
            status=ReasoningStatus.SUCCESS if all_ok else hops[-1].status,
        )
