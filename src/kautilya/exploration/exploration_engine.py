"""Knowledge Exploration Engine for Project Kautilya (S8).

Orchestrates multi-hop reasoning, structural graph traversal, and semantic grounding
into a bounded, deterministic, and inspectable exploration process.
"""

from __future__ import annotations

import logging

from kautilya.contracts.entity import Entity
from kautilya.contracts.exploration import ExplorationResult
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.reasoning import ReasoningTrace
from kautilya.contracts.retrieval import RetrievalResult
from kautilya.fusion.evidence_fusion import EvidenceFusion
from kautilya.infrastructure.embeddings.provider import EmbeddingProvider
from kautilya.knowledge.corpus import Corpus
from kautilya.knowledge.graph import KnowledgeGraph
from kautilya.reasoning.decomposer import QueryDecomposer
from kautilya.reasoning.evidence_adapter import trace_to_retrieval_result
from kautilya.reasoning.executor import ReasoningExecutor
from kautilya.retrieval.semantic import SemanticRetriever
from kautilya.retrieval.structural import KAGRetriever

logger = logging.getLogger(__name__)


class KnowledgeExplorationEngine:
    """Bounded, deterministic Knowledge Exploration engine combining graph, reasoning, and semantic retrieval."""

    def __init__(
        self,
        corpus: Corpus,
        graph: KnowledgeGraph | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        max_hops: int = 2,
        top_k: int = 5,
        fusion: EvidenceFusion | None = None,
    ) -> None:
        self.corpus = corpus
        self.graph = graph if graph is not None else KnowledgeGraph.from_corpus(corpus)
        self.max_hops = max_hops
        self.top_k = top_k
        self.fusion = fusion or EvidenceFusion()

        # Component engines
        self.decomposer = QueryDecomposer()
        self.executor = ReasoningExecutor(self.graph, max_hops=max_hops)
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

        # Start entity
        first_hop = trace.hops[0]
        start_entity = self.graph.entities.get(first_hop.source_entity_id)
        if start_entity:
            entity_list.append(start_entity)

        for hop in trace.hops:
            # Find relation object if possible
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

    def explore(
        self,
        query: str,
        top_k: int | None = None,
        max_hops: int | None = None,
    ) -> ExplorationResult:
        """Deterministically explore the knowledge space relevant to the query."""
        k = top_k if top_k is not None else self.top_k
        hops_limit = max_hops if max_hops is not None else self.max_hops

        # 1. Resolve Seed Entities
        seed_entities_list: list[Entity] = self.graph.extract_entities(query)
        if not seed_entities_list:
            # Try resolve_entity fallback
            seed_entities_list = self.graph.resolve_entity(query)

        # 2. Reason if explicit pattern recognized
        reasoning_plan = self.decomposer.decompose(query)
        reasoning_trace: ReasoningTrace | None = None
        reasoning_result: RetrievalResult | None = None
        explored_paths: list[KnowledgePath] = []

        if reasoning_plan:
            # If decomposer identified a seed entity not in seed_entities_list, add it
            plan_seeds = self.graph.resolve_entity(reasoning_plan.seed_entity_name)
            for ps in plan_seeds:
                if ps not in seed_entities_list:
                    seed_entities_list.append(ps)

            reasoning_trace = self.executor.execute(reasoning_plan)
            if reasoning_trace.is_success:
                reasoning_result = trace_to_retrieval_result(reasoning_trace, corpus=self.corpus)
                explored_paths.extend(self._convert_trace_to_paths(reasoning_trace))

        # 3. Structural Graph Exploration
        structural_result = self.structural_retriever.retrieve(query, top_k=k, max_hops=hops_limit)

        for seed in seed_entities_list:
            traversed = self.graph.traverse(seed.id, max_hops=hops_limit)
            for p in traversed:
                if p not in explored_paths:
                    explored_paths.append(p)

        # 4. Semantic Retrieval (if provider is configured)
        if self.semantic_retriever:
            semantic_result = self.semantic_retriever.retrieve(query, top_k=k)
        else:
            semantic_result = RetrievalResult(query=query, evidence=(), retrieval_method="semantic")

        # 5. Evidence Fusion
        fused_result = self.fusion.fuse(
            semantic_result=semantic_result,
            structural_result=structural_result,
            reasoning_result=reasoning_result,
            top_k=k,
        )

        # 6. Assess Exploration Status & Formulate Objective
        if not seed_entities_list and not semantic_result.evidence:
            status = "UNSUPPORTED"
            objective = "No seed entities or semantic evidence found for the query."
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
        elif fused_result.evidence:
            status = "PARTIAL"
            objective = "Direct semantic evidence discovered without explicit structural paths."
        else:
            status = "NO_EVIDENCE"
            objective = "Exploration initiated but yielded no supporting evidence."

        return ExplorationResult(
            query=query,
            objective=objective,
            seed_entities=tuple(seed_entities_list),
            explored_paths=tuple(explored_paths),
            evidence=tuple(fused_result.evidence),
            trace=reasoning_trace,
            status=status,
            metadata={
                "strategy": "hybrid_reasoning_exploration",
                "max_hops": hops_limit,
                "top_k": k,
                "num_explored_paths": len(explored_paths),
                "num_seed_entities": len(seed_entities_list),
                "has_reasoning_trace": reasoning_trace is not None,
                "reasoning_status": reasoning_trace.status.value if reasoning_trace else None,
            },
        )
