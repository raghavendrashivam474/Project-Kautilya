"""Semantic retriever for Project Kautilya.

Combines an EmbeddingProvider and a VectorIndex to retrieve
textual evidence from the corpus for a given query.
"""

from __future__ import annotations

from kautilya.contracts.retrieval import Evidence, RetrievalResult
from kautilya.infrastructure.embeddings.provider import EmbeddingProvider
from kautilya.knowledge.corpus import Corpus
from kautilya.retrieval.index import NumpyVectorIndex, VectorIndex


class SemanticRetriever:
    """Deterministic semantic retrieval over a Kautilya corpus.

    Flow:
        Question → Embedding → VectorIndex → Top-K Chunk IDs → Evidence
    """

    def __init__(
        self,
        corpus: Corpus,
        embedding_provider: EmbeddingProvider,
        top_k: int = 5,
        index: VectorIndex | None = None,
    ) -> None:
        self._corpus = corpus
        self._embedding = embedding_provider
        self._top_k = top_k
        self._index = index or NumpyVectorIndex()
        self._chunk_map: dict[str, object] = {}
        self._build_index()

    def _build_index(self) -> None:
        """Embed all corpus chunks and populate the vector index."""
        chunks = list(self._corpus.chunks)
        if not chunks:
            return

        for chunk in chunks:
            self._chunk_map[chunk.id] = chunk

        texts = [chunk.text for chunk in chunks]
        ids = [chunk.id for chunk in chunks]
        vectors = self._embedding.embed_texts(texts)
        self._index.add(ids, vectors)

    def retrieve(self, query: str, top_k: int | None = None) -> RetrievalResult:
        """Retrieve the most relevant evidence for a query."""
        k = top_k or self._top_k
        query_vector = self._embedding.embed_text(query)
        hits = self._index.search(query_vector, k)

        evidence: list[Evidence] = []
        for chunk_id, score in hits:
            chunk = self._chunk_map.get(chunk_id)
            if chunk is None:
                continue
            evidence.append(
                Evidence(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    text=chunk.text,
                    score=round(score, 4),
                    retrieval_method="semantic",
                    evidence_origin="document/chunk",
                    provenance={
                        "source_document": chunk.document_id,
                        "source_chunk": chunk.id,
                    },
                )
            )

        return RetrievalResult(
            query=query,
            evidence=evidence,
            retrieval_method="semantic",
            metadata={
                "embedding_model": self._embedding.model_name,
                "embedding_dimension": self._embedding.dimension,
                "similarity_metric": "cosine",
                "top_k": k,
                "index_size": self._index.size,
            },
        )
