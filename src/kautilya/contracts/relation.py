"""Relation contract — a typed edge with provenance back to source material."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provenance:
    document_id: str
    chunk_id: str


@dataclass(frozen=True)
class Relation:
    id: str
    source_entity_id: str
    relation_type: str
    target_entity_id: str
    provenance: Provenance
