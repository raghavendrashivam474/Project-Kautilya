"""Entity contract — a node in the knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    entity_type: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
