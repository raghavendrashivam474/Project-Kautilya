"""KnowledgePath contract — represents a structural path in the knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kautilya.contracts.entity import Entity
from kautilya.contracts.relation import Relation


@dataclass(frozen=True)
class KnowledgePath:
    """A directed/undirected path through entities and relations in the graph.

    Represents structural evidence:
        Entity_0 --[Rel_0]--> Entity_1 --[Rel_1]--> Entity_2 ...
    """

    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...] = field(default_factory=tuple)
    directions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def hops(self) -> int:
        """Return the number of relation hops in this path."""
        return len(self.relations)

    @property
    def document_ids(self) -> list[str]:
        """Return document IDs supporting the relations in this path."""
        return [r.provenance.document_id for r in self.relations]

    @property
    def chunk_ids(self) -> list[str]:
        """Return chunk IDs supporting the relations in this path."""
        return [r.provenance.chunk_id for r in self.relations]

    def format_path(self) -> str:
        """Return human-readable string representation of the path."""
        if not self.entities:
            return ""
        if not self.relations:
            return self.entities[0].name

        parts: list[str] = [self.entities[0].name]
        for i, rel in enumerate(self.relations):
            direction = self.directions[i] if i < len(self.directions) else "outgoing"
            target_name = self.entities[i + 1].name
            if direction == "incoming":
                parts.append(f" <--{rel.relation_type}-- {target_name}")
            else:
                parts.append(f" --{rel.relation_type}--> {target_name}")
        return "".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Convert path to dictionary representation for traces and logging."""
        return {
            "entities": [e.name for e in self.entities],
            "entity_ids": [e.id for e in self.entities],
            "relations": [r.relation_type for r in self.relations],
            "relation_ids": [r.id for r in self.relations],
            "directions": list(self.directions),
            "hops": self.hops,
            "formatted": self.format_path(),
            "provenance": [
                {
                    "relation_id": r.id,
                    "relation_type": r.relation_type,
                    "document_id": r.provenance.document_id,
                    "chunk_id": r.provenance.chunk_id,
                }
                for r in self.relations
            ],
        }
