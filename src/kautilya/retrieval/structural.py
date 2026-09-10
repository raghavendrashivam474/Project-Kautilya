"""Structural (KAG) retriever for Project Kautilya.

Discovers knowledge paths by traversing explicit entities and relations,
and converts the resulting provenance into common Evidence and RetrievalResult objects.
"""

from __future__ import annotations

from kautilya.contracts.chunk import Chunk
from kautilya.contracts.knowledge_path import KnowledgePath
from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.knowledge.corpus import Corpus
from kautilya.knowledge.graph import KnowledgeGraph


class KAGRetriever:
    """Deterministic structural retrieval over a Kautilya corpus.

    Flow:
        Question → Entity Resolution → Graph Traversal → Knowledge Paths → Evidence
    """

    def __init__(
        self,
        corpus: Corpus,
        graph: KnowledgeGraph | None = None,
        max_hops: int = 2,
        top_k: int = 5,
    ) -> None:
        self._corpus = corpus
        self._graph = graph or KnowledgeGraph.from_corpus(corpus)
        self._max_hops = max_hops
        self._top_k = top_k
        self._chunk_map: dict[str, Chunk] = {c.id: c for c in corpus.chunks}

    @property
    def graph(self) -> KnowledgeGraph:
        """Return the underlying structural knowledge graph."""
        return self._graph

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        max_hops: int | None = None,
    ) -> RetrievalResult:
        """Retrieve structural evidence for a query."""
        k = top_k or self._top_k
        hops = max_hops if max_hops is not None else self._max_hops

        # Step 1: Entity resolution
        seed_entities = self._graph.extract_entities(query)
        if not seed_entities:
            # Fallback to direct resolution
            seed_entities = self._graph.resolve_entity(query)

        if not seed_entities:
            return RetrievalResult(
                query=query,
                evidence=[],
                retrieval_method="structural",
                metadata={
                    "entities_resolved": [],
                    "paths_found": 0,
                    "max_hops": hops,
                    "top_k": k,
                },
            )

        # Step 2: Multi-entity connecting paths or neighborhood traversal
        collected_paths: list[tuple[float, KnowledgePath, bool]] = []
        seen_path_signatures: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()

        if len(seed_entities) >= 2:
            # Check for connecting paths between seed entities
            for i, e1 in enumerate(seed_entities):
                for e2 in seed_entities[i + 1 :]:
                    connecting = self._graph.find_paths_between(e1.id, e2.id, max_hops=max(hops, 3))
                    for path in connecting:
                        sig = (
                            tuple(e.id for e in path.entities),
                            tuple(r.id for r in path.relations),
                        )
                        if sig not in seen_path_signatures:
                            seen_path_signatures.add(sig)
                            # Direct connection score
                            score = round(1.0 / (1.0 + 0.1 * path.hops), 4)
                            collected_paths.append((score, path, True))

        # Neighborhood traversal for each seed entity
        for entity in seed_entities:
            paths = self._graph.traverse(entity.id, max_hops=hops)
            for path in paths:
                sig = (
                    tuple(e.id for e in path.entities),
                    tuple(r.id for r in path.relations),
                )
                if sig not in seen_path_signatures:
                    seen_path_signatures.add(sig)
                    score = round(1.0 / (1.0 + 0.2 * path.hops), 4)
                    collected_paths.append((score, path, False))

        # Sort paths: connecting first, score descending, hops ascending, entity names
        collected_paths.sort(
            key=lambda item: (
                not item[
                    2
                ],  # False (0) is sorted before True (1), so is_connecting=True comes first
                -item[0],
                item[1].hops,
                [e.id for e in item[1].entities],
            )
        )

        # Step 3: Evidence construction from path relations' provenance
        evidence_list: list[Evidence] = []
        seen_chunks: set[str] = set()

        for score, path, _ in collected_paths:
            for i, rel in enumerate(path.relations):
                chunk_id = rel.provenance.chunk_id
                doc_id = rel.provenance.document_id
                if chunk_id in seen_chunks:
                    continue

                chunk = self._chunk_map.get(chunk_id)
                chunk_text = chunk.text if chunk else f"Relation {rel.relation_type}"

                ev = Evidence(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    text=chunk_text,
                    score=score,
                    retrieval_method="structural",
                    evidence_origin="entity/relation",
                    provenance={
                        "document_id": doc_id,
                        "chunk_id": chunk_id,
                        "relation_id": rel.id,
                        "relation_type": rel.relation_type,
                        "source_entity_id": rel.source_entity_id,
                        "target_entity_id": rel.target_entity_id,
                    },
                    metadata={
                        "path_formatted": path.format_path(),
                        "path_hops": path.hops,
                        "step_index": i,
                    },
                )
                evidence_list.append(ev)
                seen_chunks.add(chunk_id)

                if len(evidence_list) >= k:
                    break
            if len(evidence_list) >= k:
                break

        paths_dict = [p.to_dict() for _, p, _ in collected_paths[:k]]

        return RetrievalResult(
            query=query,
            evidence=evidence_list,
            retrieval_method="structural",
            metadata={
                "entities_resolved": [e.name for e in seed_entities],
                "paths_found": len(collected_paths),
                "max_hops": hops,
                "top_k": k,
                "paths": paths_dict,
            },
        )
