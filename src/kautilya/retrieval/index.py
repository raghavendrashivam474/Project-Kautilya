"""Vector index abstraction and NumPy implementation for Project Kautilya."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class VectorIndex(ABC):
    """Abstract interface for a vector similarity index."""

    @abstractmethod
    def add(self, ids: list[str], vectors: list[list[float]]) -> None:
        """Add vectors with their identifiers to the index."""

    @abstractmethod
    def search(
        self, query_vector: list[float], top_k: int
    ) -> list[tuple[str, float]]:
        """Return the top_k nearest (id, score) pairs for a query vector."""


class NumpyVectorIndex(VectorIndex):
    """In-process vector index using NumPy cosine similarity.

    Suitable for small corpora (< 100k chunks).
    Assumes vectors are L2-normalized (dot product == cosine similarity).
    """

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._vectors: np.ndarray | None = None

    def add(self, ids: list[str], vectors: list[list[float]]) -> None:
        self._ids.extend(ids)
        new_vectors = np.array(vectors, dtype=np.float32)
        if self._vectors is None:
            self._vectors = new_vectors
        else:
            self._vectors = np.vstack([self._vectors, new_vectors])

    def search(
        self, query_vector: list[float], top_k: int
    ) -> list[tuple[str, float]]:
        if self._vectors is None or len(self._ids) == 0:
            return []

        query = np.array(query_vector, dtype=np.float32)
        # Cosine similarity via dot product (vectors are normalized)
        scores = self._vectors @ query
        k = min(top_k, len(self._ids))
        top_indices = np.argsort(scores)[::-1][:k]
        return [(self._ids[i], float(scores[i])) for i in top_indices]

    @property
    def size(self) -> int:
        return len(self._ids)