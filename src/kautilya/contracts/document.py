"""Document contract — a source text unit in the corpus."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    source: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
