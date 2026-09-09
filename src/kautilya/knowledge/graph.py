"""Structural knowledge index for graph traversal in Project Kautilya."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from kautilya.contracts.entity import Entity
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.relation import Relation
from kautilya.knowledge.corpus import Corpus


@dataclass(frozen=True)
class KnowledgeGraph:
    """In-memory structural index derived from S1 entities and relations.

    Provides adjacency lookups, entity extraction, and bounded path traversal.
    This is a derived runtime structure -- the S1 corpus remains authoritative.
    """

    entities: dict[str, Entity]
    outgoing: dict[str, tuple[Relation, ...]]
    incoming: dict[str, tuple[Relation, ...]]

    @classmethod
    def from_corpus(cls, corpus: Corpus) -> KnowledgeGraph:
        """Build the structural index from a loaded Corpus."""
        entities = {e.id: e for e in corpus.entities}
        out: dict[str, list[Relation]] = {eid: [] for eid in entities}
        inc: dict[str, list[Relation]] = {eid: [] for eid in entities}

        for rel in corpus.relations:
            if rel.source_entity_id in out:
                out[rel.source_entity_id].append(rel)
            if rel.target_entity_id in inc:
                inc[rel.target_entity_id].append(rel)

        # Sort for deterministic traversal order
        for rel_list in out.values():
            rel_list.sort(
                key=lambda r: (r.relation_type, r.target_entity_id, r.id)
            )
        for rel_list in inc.values():
            rel_list.sort(
                key=lambda r: (r.relation_type, r.source_entity_id, r.id)
            )

        return cls(
            entities=entities,
            outgoing={eid: tuple(rels) for eid, rels in out.items()},
            incoming={eid: tuple(rels) for eid, rels in inc.items()},
        )

    def resolve_entity(self, query: str) -> list[Entity]:
        """Resolve an exact query string to matching entities.

        Matching priority (deterministic):
        1. Exact entity ID
        2. Exact name (case-insensitive)
        3. Alias (case-insensitive)

        Returns matching entities sorted by ID.
        """
        q = query.strip().lower()
        if not q:
            return []

        matches: list[Entity] = []
        seen: set[str] = set()

        for entity in sorted(self.entities.values(), key=lambda e: e.id):
            if entity.id in seen:
                continue
            if entity.id.lower() == q:
                matches.append(entity)
                seen.add(entity.id)
                continue
            if entity.name.lower() == q:
                matches.append(entity)
                seen.add(entity.id)
                continue
            for alias in entity.aliases:
                if alias.lower() == q:
                    matches.append(entity)
                    seen.add(entity.id)
                    break

        return matches

    def extract_entities(self, text: str) -> list[Entity]:
        """Extract all mentioned entities from natural language text.

        Matches by entity names, aliases, and IDs (case-insensitive).
        Longer matches take precedence to avoid partial substring collisions.
        Tracks matched character spans to prevent overlapping sub-string captures.
        Returns matched entities ordered by first occurrence in text.
        """
        q = text.lower()
        if not q.strip():
            return []

        # Build list of (term, entity) sorted by term length descending
        candidates: list[tuple[str, Entity]] = []
        for entity in self.entities.values():
            candidates.append((entity.id.lower(), entity))
            candidates.append((entity.name.lower(), entity))
            for alias in entity.aliases:
                candidates.append((alias.lower(), entity))

        candidates.sort(key=lambda item: len(item[0]), reverse=True)

        found: list[tuple[int, Entity]] = []
        matched_entity_ids: set[str] = set()
        consumed_spans: list[tuple[int, int]] = []

        for term, entity in candidates:
            if not term or entity.id in matched_entity_ids:
                continue
            pos = q.find(term)
            if pos != -1:
                start_pos = pos
                end_pos = pos + len(term)

                # Overlap check: has any part of this span already been consumed by a longer match?
                overlapping = any(
                    not (end_pos <= existing_start or start_pos >= existing_end)
                    for existing_start, existing_end in consumed_spans
                )
                if overlapping:
                    continue

                # Boundary check: avoid matching inside other alphanumeric words
                is_start_ok = start_pos == 0 or not q[start_pos - 1].isalnum()
                is_end_ok = end_pos == len(q) or not q[end_pos].isalnum()

                if is_start_ok and is_end_ok:
                    found.append((start_pos, entity))
                    matched_entity_ids.add(entity.id)
                    consumed_spans.append((start_pos, end_pos))

        found.sort(key=lambda item: (item[0], item[1].id))
        return [entity for _, entity in found]

    def get_outgoing(self, entity_id: str) -> tuple[Relation, ...]:
        """Return outgoing relations for an entity, sorted deterministically."""
        return self.outgoing.get(entity_id, ())

    def get_incoming(self, entity_id: str) -> tuple[Relation, ...]:
        """Return incoming relations for an entity, sorted deterministically."""
        return self.incoming.get(entity_id, ())

    def traverse(
        self, start_entity_id: str, max_hops: int = 2
    ) -> list[KnowledgePath]:
        """Perform bounded BFS traversal starting from a seed entity.

        Explores both outgoing and incoming relations up to max_hops.
        Guarantees:
        - Cycle-free paths
        - Deterministic path ordering
        - Bounded depth
        """
        if start_entity_id not in self.entities:
            return []

        start_entity = self.entities[start_entity_id]
        results: list[KnowledgePath] = [
            KnowledgePath(entities=(start_entity,), relations=(), directions=())
        ]

        if max_hops <= 0:
            return results

        # Queue items: (current_entity_id, entities_tuple, relations_tuple, directions_tuple)
        queue: deque[tuple[str, tuple[Entity, ...], tuple[Relation, ...], tuple[str, ...]]] = deque()
        queue.append((start_entity_id, (start_entity,), (), ()))

        while queue:
            curr_id, path_entities, path_rels, path_dirs = queue.popleft()
            current_depth = len(path_rels)

            if current_depth >= max_hops:
                continue

            visited_ids = {e.id for e in path_entities}

            # Outgoing edges: curr_id --[rel]--> target_id
            for rel in self.get_outgoing(curr_id):
                target_id = rel.target_entity_id
                if target_id not in visited_ids and target_id in self.entities:
                    next_entity = self.entities[target_id]
                    new_entities = (*path_entities, next_entity)
                    new_rels = (*path_rels, rel)
                    new_dirs = (*path_dirs, "outgoing")
                    path = KnowledgePath(
                        entities=new_entities,
                        relations=new_rels,
                        directions=new_dirs,
                    )
                    results.append(path)
                    queue.append((target_id, new_entities, new_rels, new_dirs))

            # Incoming edges: source_id --[rel]--> curr_id (traversed as curr_id <--[rel]-- source_id)
            for rel in self.get_incoming(curr_id):
                source_id = rel.source_entity_id
                if source_id not in visited_ids and source_id in self.entities:
                    next_entity = self.entities[source_id]
                    new_entities = (*path_entities, next_entity)
                    new_rels = (*path_rels, rel)
                    new_dirs = (*path_dirs, "incoming")
                    path = KnowledgePath(
                        entities=new_entities,
                        relations=new_rels,
                        directions=new_dirs,
                    )
                    results.append(path)
                    queue.append((source_id, new_entities, new_rels, new_dirs))

        return results

    def find_paths_between(
        self, source_id: str, target_id: str, max_hops: int = 3
    ) -> list[KnowledgePath]:
        """Find all simple paths between two entities within max_hops."""
        if (
            source_id not in self.entities
            or target_id not in self.entities
            or source_id == target_id
        ):
            return []

        all_paths = self.traverse(source_id, max_hops=max_hops)
        return [p for p in all_paths if p.entities[-1].id == target_id]
