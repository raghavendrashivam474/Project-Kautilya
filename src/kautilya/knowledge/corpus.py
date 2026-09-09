"""Corpus — the assembled, validated knowledge world."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from kautilya.contracts import Chunk, Document, Entity, Provenance, Relation
from kautilya.ingestion import build_chunks, load_documents


class CorpusValidationError(Exception):
    """Raised when the corpus fails integrity checks."""


@dataclass(frozen=True)
class Corpus:
    documents: tuple[Document, ...]
    chunks: tuple[Chunk, ...]
    entities: tuple[Entity, ...]
    relations: tuple[Relation, ...]

    # ----- lookups -----
    def document(self, doc_id: str) -> Document | None:
        return next((d for d in self.documents if d.id == doc_id), None)

    def chunk(self, chunk_id: str) -> Chunk | None:
        return next((c for c in self.chunks if c.id == chunk_id), None)

    def entity(self, ent_id_or_name: str) -> Entity | None:
        for e in self.entities:
            if e.id == ent_id_or_name or e.name == ent_id_or_name:
                return e
            if ent_id_or_name in e.aliases:
                return e
        return None

    def relations_for(self, entity_id: str) -> list[Relation]:
        return [
            r for r in self.relations
            if r.source_entity_id == entity_id or r.target_entity_id == entity_id
        ]


# ---------- Loading ----------

def _load_entities(path: Path) -> list[Entity]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    result: list[Entity] = []
    for e in data.get("entities", []):
        result.append(
            Entity(
                id=e["id"],
                name=e["name"],
                entity_type=e["entity_type"],
                aliases=tuple(e.get("aliases", []) or []),
            )
        )
    return result


def _load_relations(path: Path) -> list[Relation]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    result: list[Relation] = []
    for r in data.get("relations", []):
        prov = r["provenance"]
        result.append(
            Relation(
                id=r["id"],
                source_entity_id=r["source"],
                relation_type=r["relation_type"],
                target_entity_id=r["target"],
                provenance=Provenance(
                    document_id=prov["document_id"],
                    chunk_id=prov["chunk_id"],
                ),
            )
        )
    return result


def load_corpus(
    corpus_dir: Path | str = "data/corpus",
    knowledge_dir: Path | str = "data/knowledge",
) -> Corpus:
    """Load, chunk, and validate the full knowledge world."""
    corpus_dir = Path(corpus_dir)
    knowledge_dir = Path(knowledge_dir)

    documents = load_documents(corpus_dir)
    chunks = build_chunks(documents)
    entities = _load_entities(knowledge_dir / "entities.yaml")
    relations = _load_relations(knowledge_dir / "relations.yaml")

    corpus = Corpus(
        documents=tuple(documents),
        chunks=tuple(chunks),
        entities=tuple(entities),
        relations=tuple(relations),
    )
    validate_corpus(corpus)
    return corpus


# ---------- Validation ----------

def validate_corpus(corpus: Corpus) -> None:
    """Enforce structural integrity. Raises CorpusValidationError."""
    errors: list[str] = []

    # Unique IDs
    for kind, items in (
        ("document", corpus.documents),
        ("chunk", corpus.chunks),
        ("entity", corpus.entities),
        ("relation", corpus.relations),
    ):
        ids = [i.id for i in items]
        dups = {x for x in ids if ids.count(x) > 1}
        if dups:
            errors.append(f"Duplicate {kind} IDs: {sorted(dups)}")

    doc_ids = {d.id for d in corpus.documents}
    chunk_ids = {c.id for c in corpus.chunks}
    ent_ids = {e.id for e in corpus.entities}

    # Chunks reference real documents
    for c in corpus.chunks:
        if c.document_id not in doc_ids:
            errors.append(f"Chunk {c.id} references missing document {c.document_id}")

    # Relations reference real entities
    for r in corpus.relations:
        if r.source_entity_id not in ent_ids:
            errors.append(f"Relation {r.id} source entity missing: {r.source_entity_id}")
        if r.target_entity_id not in ent_ids:
            errors.append(f"Relation {r.id} target entity missing: {r.target_entity_id}")
        # Provenance
        if r.provenance.document_id not in doc_ids:
            errors.append(
                f"Relation {r.id} provenance document missing: {r.provenance.document_id}"
            )
        if r.provenance.chunk_id not in chunk_ids:
            errors.append(
                f"Relation {r.id} provenance chunk missing: {r.provenance.chunk_id}"
            )

    if errors:
        raise CorpusValidationError("Corpus validation failed:\n  - " + "\n  - ".join(errors))
