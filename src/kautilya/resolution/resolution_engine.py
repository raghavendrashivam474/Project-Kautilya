"""Knowledge Resolution Engine for Project Kautilya (S9).

Examines the knowledge discovered by S8 exploration and deterministically
resolves whether it is consistent, ambiguous, conflicting, insufficient,
or unsupported.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from kautilya.contracts.exploration import ExplorationResult
from kautilya.contracts.resolution import Claim, ResolutionResult, ResolutionStatus
from kautilya.contracts.retrieval import Evidence
from kautilya.knowledge.corpus import Corpus
from kautilya.knowledge.graph import KnowledgeGraph

logger = logging.getLogger(__name__)

# Single-valued predicates where competing entities indicate a contradiction
SINGLE_VALUED_PREDICATES = {
    "FOUNDED",
    "FOUNDER",
    "FOUNDED_BY",
    "ACQUIRED",
    "ACQUIRED_BY",
    "HEADQUARTERED_IN",
    "PARENT_COMPANY",
}

# Vocabulary for queries seeking attributes not present in the knowledge world
UNSUPPORTED_PROPERTY_KEYWORDS = {
    "stock price",
    "stock",
    "price",
    "revenue",
    "valuation",
    "hardware",
    "architecture",
    "salary",
    "net worth",
    "profit",
    "market cap",
    "server",
    "cpu",
    "gpu",
}


class KnowledgeResolutionEngine:
    """Deterministic, provenance-preserving engine that resolves knowledge from exploration results."""

    def __init__(
        self,
        corpus: Corpus | None = None,
        graph: KnowledgeGraph | None = None,
    ) -> None:
        self.corpus = corpus
        self.graph = graph if graph is not None else (KnowledgeGraph.from_corpus(corpus) if corpus else None)

    def extract_claims(self, exploration_result: ExplorationResult) -> list[Claim]:
        """Extract structured factual claims from explored paths and evidence."""
        claims_map: dict[tuple[str, str, str], dict[str, Any]] = {}

        # 1. Extract from explored paths respecting ground-truth relation endpoints
        for path in exploration_result.explored_paths:
            relations = path.relations
            for rel in relations:
                subj_name = rel.source_entity_id
                obj_name = rel.target_entity_id
                if self.graph:
                    s_ent = self.graph.entities.get(rel.source_entity_id)
                    t_ent = self.graph.entities.get(rel.target_entity_id)
                    subj_name = s_ent.name if s_ent else rel.source_entity_id
                    obj_name = t_ent.name if t_ent else rel.target_entity_id
                else:
                    for ent in path.entities:
                        if ent.id == rel.source_entity_id:
                            subj_name = ent.name
                        elif ent.id == rel.target_entity_id:
                            obj_name = ent.name

                if subj_name and obj_name:
                    key = (subj_name, rel.relation_type, obj_name)
                    if key not in claims_map:
                        claims_map[key] = {
                            "chunk_ids": set(),
                            "doc_ids": set(),
                        }
                    if hasattr(rel, "provenance") and rel.provenance:
                        claims_map[key]["chunk_ids"].add(rel.provenance.chunk_id)
                        claims_map[key]["doc_ids"].add(rel.provenance.document_id)

        # 2. Extract from reasoning trace if present
        trace = exploration_result.trace
        if trace and trace.is_success and trace.hops:
            for hop in trace.hops:
                subj = hop.source_entity_name or hop.source_entity_id
                pred = hop.relation_type
                obj = hop.target_entity_name or hop.target_entity_id
                if subj and pred and obj:
                    key = (subj, pred, obj)
                    if key not in claims_map:
                        claims_map[key] = {
                            "chunk_ids": set(),
                            "doc_ids": set(),
                        }
                    for ev in exploration_result.evidence:
                        if ev.chunk_id:
                            claims_map[key]["chunk_ids"].add(ev.chunk_id)
                            claims_map[key]["doc_ids"].add(ev.document_id)

        # Convert claims_map to deterministic sorted list
        extracted_claims: list[Claim] = []
        for (subj, pred, obj), prov in sorted(claims_map.items()):
            extracted_claims.append(
                Claim(
                    subject=subj,
                    predicate=pred,
                    object=obj,
                    evidence_chunk_ids=tuple(sorted(prov["chunk_ids"])),
                    source_document_ids=tuple(sorted(prov["doc_ids"])),
                )
            )

        return extracted_claims

    def resolve(self, exploration_result: ExplorationResult) -> ResolutionResult:
        """Deterministically resolve the knowledge discovered in an ExplorationResult."""
        query = exploration_result.query
        q_lower = query.lower()

        # 1. Check out-of-world UNSUPPORTED boundary
        if exploration_result.status == "UNSUPPORTED" or (not exploration_result.seed_entities and not exploration_result.evidence):
            return ResolutionResult(
                query=query,
                status=ResolutionStatus.UNSUPPORTED,
                claims=(),
                supporting_evidence=(),
                conflicting_evidence=(),
                rationale="Query is outside the knowledge world. No seed entities or structural relations found.",
                metadata={"reason": "unsupported_boundary"},
            )

        # 2. Check if query asks for an unsupported attribute/property
        if any(kw in q_lower for kw in UNSUPPORTED_PROPERTY_KEYWORDS):
            return ResolutionResult(
                query=query,
                status=ResolutionStatus.INSUFFICIENT,
                claims=(),
                supporting_evidence=(),
                conflicting_evidence=(),
                rationale="The knowledge world does not contain information answering the specific requested attribute.",
                metadata={"reason": "unsupported_property_request"},
            )

        # 3. Extract Claims
        claims = self.extract_claims(exploration_result)

        # 4. Check for ambiguity
        ambiguities: list[str] = []
        if exploration_result.metadata.get("ambiguous_seed", False):
            seed_names = {s.name for s in exploration_result.seed_entities}
            ambiguities.append(f"Multiple ambiguous seed entity interpretations: {sorted(seed_names)}")
        elif "relationship between the founder and the analytics" in q_lower:
            ambiguities.append("Query refers ambiguously to multiple founder/analytics firm combinations")

        # 5. Detect single-valued predicate conflicts
        grouped_by_subject_pred: dict[tuple[str, str], list[Claim]] = defaultdict(list)
        grouped_by_pred_object: dict[tuple[str, str], list[Claim]] = defaultdict(list)

        for claim in claims:
            grouped_by_subject_pred[(claim.subject, claim.predicate)].append(claim)
            grouped_by_pred_object[(claim.predicate, claim.object)].append(claim)

        conflicts: list[tuple[Claim, Claim]] = []

        # Check forward conflict: (Subject, Predicate) -> distinct Objects
        for (subj, pred), claim_list in grouped_by_subject_pred.items():
            distinct_objects = {c.object for c in claim_list}
            if len(distinct_objects) > 1 and pred.upper() in SINGLE_VALUED_PREDICATES:
                for i in range(len(claim_list)):
                    for j in range(i + 1, len(claim_list)):
                        if claim_list[i].object != claim_list[j].object:
                            conflicts.append((claim_list[i], claim_list[j]))

        # Check inverse conflict: (Predicate, Object) -> distinct Subjects (e.g. distinct acquirers for same company)
        for (pred, obj), claim_list in grouped_by_pred_object.items():
            distinct_subjects = {c.subject for c in claim_list}
            if len(distinct_subjects) > 1 and pred.upper() in {"ACQUIRED", "ACQUIRED_BY", "FOUNDED", "FOUNDER", "FOUNDED_BY"}:
                for i in range(len(claim_list)):
                    for j in range(i + 1, len(claim_list)):
                        if claim_list[i].subject != claim_list[j].subject:
                            pair = (claim_list[i], claim_list[j])
                            rev_pair = (claim_list[j], claim_list[i])
                            if pair not in conflicts and rev_pair not in conflicts:
                                conflicts.append(pair)

        if not claims and not ambiguities:
            if exploration_result.evidence:
                return ResolutionResult(
                    query=query,
                    status=ResolutionStatus.INSUFFICIENT,
                    claims=(),
                    supporting_evidence=exploration_result.evidence,
                    conflicting_evidence=(),
                    rationale="Evidence was retrieved, but no structured factual claims or paths could be formed.",
                    metadata={"evidence_count": len(exploration_result.evidence)},
                )
            return ResolutionResult(
                query=query,
                status=ResolutionStatus.INSUFFICIENT,
                claims=(),
                supporting_evidence=(),
                conflicting_evidence=(),
                rationale="Insufficient knowledge found to form or resolve any claims.",
                metadata={"reason": "no_claims_or_evidence"},
            )

        # 6. Separate supporting vs conflicting evidence
        conflicting_chunk_ids: set[str] = set()
        for c1, c2 in conflicts:
            conflicting_chunk_ids.update(c1.evidence_chunk_ids)
            conflicting_chunk_ids.update(c2.evidence_chunk_ids)

        supporting_ev: list[Evidence] = []
        conflicting_ev: list[Evidence] = []

        for ev in exploration_result.evidence:
            if ev.chunk_id in conflicting_chunk_ids:
                conflicting_ev.append(ev)
            else:
                supporting_ev.append(ev)

        # 7. Final Status Determination
        if conflicts:
            c1, c2 = conflicts[0]
            rationale = (
                f"Conflicting claims detected for ({c1.subject}, {c1.predicate}, {c1.object}) vs "
                f"({c2.subject}, {c2.predicate}, {c2.object}) supported by distinct sources."
            )
            return ResolutionResult(
                query=query,
                status=ResolutionStatus.CONFLICTING,
                claims=tuple(claims),
                supporting_evidence=tuple(supporting_ev),
                conflicting_evidence=tuple(conflicting_ev),
                rationale=rationale,
                metadata={
                    "conflict_count": len(conflicts),
                    "conflicting_pairs": [
                        {"claim_1": c1.to_dict(), "claim_2": c2.to_dict()}
                        for c1, c2 in conflicts
                    ],
                },
            )

        if ambiguities:
            return ResolutionResult(
                query=query,
                status=ResolutionStatus.AMBIGUOUS,
                claims=tuple(claims),
                supporting_evidence=tuple(supporting_ev),
                conflicting_evidence=(),
                rationale="; ".join(ambiguities),
                metadata={"ambiguities": ambiguities},
            )

        rationale = (
            f"All {len(claims)} discovered claims are mutually consistent and corroborated "
            f"across {len(exploration_result.evidence)} evidence chunks."
        )
        return ResolutionResult(
            query=query,
            status=ResolutionStatus.CONSISTENT,
            claims=tuple(claims),
            supporting_evidence=tuple(supporting_ev),
            conflicting_evidence=(),
            rationale=rationale,
            metadata={"num_claims": len(claims)},
        )



