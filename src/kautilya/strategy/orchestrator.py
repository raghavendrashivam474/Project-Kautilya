"""Adaptive Knowledge Orchestrator for Project Kautilya (S11/S12).

Selectively routes queries to the optimal retrieval or reasoning capability
based on deterministic StrategySelector decisions, evaluates evidence sufficiency,
and conditionally escalates to broader hybrid exploration when initial evidence
is insufficient or ambiguous.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from kautilya.contracts.entity import Entity
from kautilya.contracts.exploration import ExplorationResult
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.reasoning import ReasoningTrace
from kautilya.contracts.resolution import ResolutionResult
from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.contracts.strategy import (
    RetrievalStrategy,
    StrategyDecision,
    SufficiencyAssessment,
)
from kautilya.fusion.evidence_fusion import EvidenceFusion
from kautilya.infrastructure.embeddings.provider import EmbeddingProvider
from kautilya.knowledge.corpus import Corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.reasoning.decomposer import QueryDecomposer
from kautilya.reasoning.evidence_adapter import trace_to_retrieval_result
from kautilya.reasoning.executor import ReasoningExecutor
from kautilya.resolution.resolution_engine import KnowledgeResolutionEngine
from kautilya.retrieval.semantic import SemanticRetriever
from kautilya.retrieval.structural import KAGRetriever
from kautilya.strategy.selector import StrategySelector
from kautilya.strategy.sufficiency import EvidenceSufficiencyEvaluator

logger = logging.getLogger(__name__)


class AdaptiveOrchestrator:
    """Deterministic, selective orchestrator above existing Kautilya capabilities."""

    def __init__(
        self,
        corpus: Corpus,
        graph: KnowledgeGraph | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        selector: StrategySelector | None = None,
        fusion: EvidenceFusion | None = None,
        sufficiency_evaluator: EvidenceSufficiencyEvaluator | None = None,
        resolution_engine: KnowledgeResolutionEngine | None = None,
        max_hops: int = 2,
        top_k: int = 5,
    ) -> None:
        self.corpus = corpus
        self.graph = graph if graph is not None else KnowledgeGraph.from_corpus(corpus)
        self.embedding_provider = embedding_provider
        self.max_hops = max_hops
        self.top_k = top_k

        self.selector = selector or StrategySelector(graph=self.graph)
        self.fusion = fusion or EvidenceFusion()
        self.decomposer = QueryDecomposer()
        self.executor = ReasoningExecutor(self.graph, max_hops=max_hops)
        self.sufficiency_evaluator = sufficiency_evaluator or EvidenceSufficiencyEvaluator()
        self.resolution_engine = resolution_engine or KnowledgeResolutionEngine(
            corpus=self.corpus, graph=self.graph
        )

        self.structural_retriever = KAGRetriever(
            corpus=corpus, graph=self.graph, max_hops=max_hops, top_k=top_k
        )
        self.semantic_retriever = (
            SemanticRetriever(corpus=corpus, embedding_provider=embedding_provider, top_k=top_k)
            if embedding_provider is not None
            else None
        )

    def _convert_trace_to_paths(self, trace: ReasoningTrace) -> list[KnowledgePath]:
        """Convert a successful reasoning trace into KnowledgePath objects."""
        if not trace.is_success or not trace.hops:
            return []

        entity_list: list[Entity] = []
        relations_list = []
        directions_list = []

        first_hop = trace.hops[0]
        start_entity = self.graph.entities.get(first_hop.source_entity_id)
        if start_entity:
            entity_list.append(start_entity)

        for hop in trace.hops:
            if hop.direction.value == "outgoing":
                rels = self.graph.get_outgoing(hop.source_entity_id)
                matching = [
                    r
                    for r in rels
                    if r.relation_type == hop.relation_type
                    and r.target_entity_id == hop.target_entity_id
                ]
            else:
                rels = self.graph.get_incoming(hop.source_entity_id)
                matching = [
                    r
                    for r in rels
                    if r.relation_type == hop.relation_type
                    and r.source_entity_id == hop.target_entity_id
                ]

            if matching:
                relations_list.append(matching[0])
            directions_list.append(hop.direction.value)

            target_entity = self.graph.entities.get(hop.target_entity_id or "")
            if target_entity:
                entity_list.append(target_entity)

        if entity_list and len(entity_list) == len(relations_list) + 1:
            return [
                KnowledgePath(
                    entities=tuple(entity_list),
                    relations=tuple(relations_list),
                    directions=tuple(directions_list),
                )
            ]
        return []

    def _explore_single_strategy(
        self,
        query: str,
        strategy: RetrievalStrategy,
        top_k: int,
        max_hops: int,
    ) -> tuple[ExplorationResult, dict[str, Any]]:
        """Execute a specific exploration strategy deterministically."""
        t0 = time.perf_counter()
        sem_invoked = False
        kag_invoked = False
        rea_invoked = False
        fusion_invoked = False

        seed_entities_list: list[Entity] = []
        if self.graph:
            seed_entities_list = self.graph.extract_entities(query)
            if not seed_entities_list:
                seed_entities_list = self.graph.resolve_entity(query)

        explored_paths: list[KnowledgePath] = []
        reasoning_trace: ReasoningTrace | None = None
        evidence_list: list[Evidence] = []

        if strategy == RetrievalStrategy.SEMANTIC:
            if self.semantic_retriever:
                sem_invoked = True
                sem_res = self.semantic_retriever.retrieve(query, top_k=top_k)
                evidence_list = sem_res.evidence

        elif strategy == RetrievalStrategy.STRUCTURAL:
            kag_invoked = True
            kag_res = self.structural_retriever.retrieve(query, top_k=top_k, max_hops=max_hops)
            evidence_list = kag_res.evidence
            for seed in seed_entities_list:
                traversed = self.graph.traverse(seed.id, max_hops=max_hops)
                for p in traversed:
                    if p not in explored_paths:
                        explored_paths.append(p)

        elif strategy == RetrievalStrategy.REASONING:
            rea_invoked = True
            plan = self.decomposer.decompose(query)
            if plan:
                plan_seeds = self.graph.resolve_entity(plan.seed_entity_name)
                for ps in plan_seeds:
                    if ps not in seed_entities_list:
                        seed_entities_list.append(ps)

                reasoning_trace = self.executor.execute(plan)
                if reasoning_trace.is_success:
                    rea_res = trace_to_retrieval_result(reasoning_trace, corpus=self.corpus)
                    evidence_list = rea_res.evidence
                    explored_paths.extend(self._convert_trace_to_paths(reasoning_trace))
                else:
                    kag_invoked = True
                    kag_res = self.structural_retriever.retrieve(
                        query, top_k=top_k, max_hops=max_hops
                    )
                    evidence_list = kag_res.evidence
            else:
                kag_invoked = True
                kag_res = self.structural_retriever.retrieve(query, top_k=top_k, max_hops=max_hops)
                evidence_list = kag_res.evidence

        else:  # HYBRID
            plan = self.decomposer.decompose(query)
            rea_result: RetrievalResult | None = None
            if plan:
                plan_seeds = self.graph.resolve_entity(plan.seed_entity_name)
                for ps in plan_seeds:
                    if ps not in seed_entities_list:
                        seed_entities_list.append(ps)

                rea_invoked = True
                reasoning_trace = self.executor.execute(plan)
                if reasoning_trace.is_success:
                    rea_result = trace_to_retrieval_result(reasoning_trace, corpus=self.corpus)
                    explored_paths.extend(self._convert_trace_to_paths(reasoning_trace))

            kag_invoked = True
            kag_res = self.structural_retriever.retrieve(query, top_k=top_k, max_hops=max_hops)
            for seed in seed_entities_list:
                traversed = self.graph.traverse(seed.id, max_hops=max_hops)
                for p in traversed:
                    if p not in explored_paths:
                        explored_paths.append(p)

            sem_res: RetrievalResult
            if self.semantic_retriever:
                sem_invoked = True
                sem_res = self.semantic_retriever.retrieve(query, top_k=top_k)
            else:
                sem_res = RetrievalResult(query=query, evidence=[], retrieval_method="semantic")

            fusion_invoked = True
            fused_res = self.fusion.fuse(
                semantic_result=sem_res,
                structural_result=kag_res,
                reasoning_result=rea_result,
                top_k=top_k,
            )
            evidence_list = fused_res.evidence

        # Assess Status
        if not seed_entities_list and not evidence_list:
            status = "UNSUPPORTED"
            objective = "No seed entities or evidence found for the query."
        elif reasoning_trace and reasoning_trace.is_success:
            status = "SUCCESS"
            objective = (
                f"Multi-hop reasoning path traced successfully to terminal entity: "
                f"{reasoning_trace.terminal_entity_name}."
            )
        elif explored_paths:
            status = "SUCCESS"
            objective = (
                f"Explored {len(explored_paths)} connected knowledge paths around seed entities."
            )
        elif evidence_list:
            status = "PARTIAL"
            objective = "Direct evidence discovered without explicit multi-hop structural paths."
        else:
            status = "NO_EVIDENCE"
            objective = "Adaptive exploration initiated but yielded no supporting evidence."

        t1 = time.perf_counter()
        total_invocations = sum([sem_invoked, kag_invoked, rea_invoked, fusion_invoked])

        metrics = {
            "strategy": strategy.value,
            "semantic_invoked": sem_invoked,
            "kag_invoked": kag_invoked,
            "reasoning_invoked": rea_invoked,
            "fusion_invoked": fusion_invoked,
            "total_invocations": total_invocations,
            "latency_ms": (t1 - t0) * 1000,
        }

        exploration_res = ExplorationResult(
            query=query,
            objective=objective,
            seed_entities=tuple(seed_entities_list),
            explored_paths=tuple(explored_paths),
            evidence=tuple(evidence_list),
            trace=reasoning_trace,
            status=status,
            metadata={
                "strategy": f"adaptive_{strategy.value}",
                "metrics": metrics,
                "max_hops": max_hops,
                "top_k": top_k,
            },
        )
        return exploration_res, metrics

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        max_hops: int | None = None,
    ) -> tuple[RetrievalResult, StrategyDecision, dict[str, Any]]:
        """Selectively retrieve knowledge using only the strategy deemed appropriate."""
        k = top_k or self.top_k
        hops = max_hops or self.max_hops

        t0 = time.perf_counter()
        decision = self.selector.select(query)

        sem_invoked = False
        kag_invoked = False
        rea_invoked = False
        fusion_invoked = False

        result: RetrievalResult

        if decision.selected_strategy == RetrievalStrategy.SEMANTIC:
            if self.semantic_retriever:
                sem_invoked = True
                result = self.semantic_retriever.retrieve(query, top_k=k)
            else:
                result = RetrievalResult(query=query, evidence=[], retrieval_method="semantic")

        elif decision.selected_strategy == RetrievalStrategy.STRUCTURAL:
            kag_invoked = True
            result = self.structural_retriever.retrieve(query, top_k=k, max_hops=hops)

        elif decision.selected_strategy == RetrievalStrategy.REASONING:
            rea_invoked = True
            plan = self.decomposer.decompose(query)
            if plan:
                trace = self.executor.execute(plan)
                if trace.is_success:
                    result = trace_to_retrieval_result(trace, corpus=self.corpus)
                else:
                    kag_invoked = True
                    result = self.structural_retriever.retrieve(query, top_k=k, max_hops=hops)
            else:
                kag_invoked = True
                result = self.structural_retriever.retrieve(query, top_k=k, max_hops=hops)

        else:  # HYBRID
            sem_result: RetrievalResult
            if self.semantic_retriever:
                sem_invoked = True
                sem_result = self.semantic_retriever.retrieve(query, top_k=k)
            else:
                sem_result = RetrievalResult(query=query, evidence=[], retrieval_method="semantic")

            kag_invoked = True
            kag_result = self.structural_retriever.retrieve(query, top_k=k, max_hops=hops)

            rea_result: RetrievalResult | None = None
            plan = self.decomposer.decompose(query)
            if plan:
                rea_invoked = True
                trace = self.executor.execute(plan)
                if trace.is_success:
                    rea_result = trace_to_retrieval_result(trace, corpus=self.corpus)

            fusion_invoked = True
            result = self.fusion.fuse(
                semantic_result=sem_result,
                structural_result=kag_result,
                reasoning_result=rea_result,
                top_k=k,
            )

        t1 = time.perf_counter()
        total_invocations = sum([sem_invoked, kag_invoked, rea_invoked, fusion_invoked])

        metrics = {
            "strategy": decision.selected_strategy.value,
            "semantic_invoked": sem_invoked,
            "kag_invoked": kag_invoked,
            "reasoning_invoked": rea_invoked,
            "fusion_invoked": fusion_invoked,
            "total_invocations": total_invocations,
            "latency_ms": (t1 - t0) * 1000,
        }

        return result, decision, metrics

    def explore(
        self,
        query: str,
        top_k: int | None = None,
        max_hops: int | None = None,
    ) -> tuple[ExplorationResult, StrategyDecision, dict[str, Any]]:
        """Deterministically explore using adaptive strategy routing, returning an ExplorationResult."""
        k = top_k or self.top_k
        hops = max_hops or self.max_hops

        decision = self.selector.select(query)
        exploration_res, metrics = self._explore_single_strategy(
            query=query,
            strategy=decision.selected_strategy,
            top_k=k,
            max_hops=hops,
        )
        return exploration_res, decision, metrics

    def resolve_adaptive(
        self,
        query: str,
        top_k: int | None = None,
        max_hops: int | None = None,
    ) -> tuple[ResolutionResult, StrategyDecision, SufficiencyAssessment, dict[str, Any]]:
        """Two-phase adaptive resolution: initial execution, sufficiency check, conditional escalation."""
        k = top_k or self.top_k
        hops = max_hops or self.max_hops

        t0 = time.perf_counter()

        # ── Phase 1: Initial Selection & Exploration ──
        decision = self.selector.select(query)
        p1_exp, p1_metrics = self._explore_single_strategy(
            query=query,
            strategy=decision.selected_strategy,
            top_k=k,
            max_hops=hops,
        )
        p1_resolution = self.resolution_engine.resolve(p1_exp)

        # ── Phase 2: Sufficiency Assessment ──
        assessment = self.sufficiency_evaluator.evaluate(
            query=query,
            initial_strategy=decision.selected_strategy,
            resolution_result=p1_resolution,
            reasoning_trace=p1_exp.trace,
        )

        final_resolution = p1_resolution
        escalated = False
        p2_invocations = 0
        final_strategy = decision.selected_strategy

        if assessment.escalation_required and assessment.escalation_strategy:
            # Conditional Escalation to broader exploration (HYBRID)
            escalated = True
            final_strategy = assessment.escalation_strategy
            p2_exp, p2_metrics = self._explore_single_strategy(
                query=query,
                strategy=assessment.escalation_strategy,
                top_k=k,
                max_hops=hops,
            )
            final_resolution = self.resolution_engine.resolve(p2_exp)
            p2_invocations = p2_metrics["total_invocations"]

        t1 = time.perf_counter()
        total_invocations = p1_metrics["total_invocations"] + p2_invocations

        combined_metrics = {
            "initial_strategy": decision.selected_strategy.value,
            "final_strategy": final_strategy.value,
            "escalated": escalated,
            "sufficiency_status": assessment.status.value,
            "escalation_reason": assessment.reason,
            "phase1_invocations": p1_metrics["total_invocations"],
            "phase2_invocations": p2_invocations,
            "total_invocations": total_invocations,
            "latency_ms": (t1 - t0) * 1000,
        }

        return final_resolution, decision, assessment, combined_metrics
