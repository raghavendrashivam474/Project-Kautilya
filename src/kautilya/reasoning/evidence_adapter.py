"""Convert ReasoningTrace into the existing RetrievalResult contract.

This is the bridge between S5 reasoning and S4 fusion.
The adapter produces Evidence objects that the existing
EvidenceFusion can consume alongside semantic and structural results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kautilya.contracts.reasoning import ReasoningTrace
from kautilya.contracts.retrieval import Evidence, RetrievalResult

if TYPE_CHECKING:
    from kautilya.knowledge.corpus import Corpus


def trace_to_retrieval_result(
    trace: ReasoningTrace,
    *,
    corpus: Corpus | None = None,
    base_score: float = 0.95,
) -> RetrievalResult:
    """Convert a successful ReasoningTrace into a RetrievalResult.

    Each hop's supporting chunks become Evidence items.
    Earlier hops or terminal hop can be weighted deterministically.
    Failed traces produce an empty RetrievalResult.
    """
    if not trace.is_success:
        return RetrievalResult(
            query=trace.plan.query,
            evidence=[],
            retrieval_method="reasoning",
            metadata={
                "status": trace.status.value,
                "reasoning_trace": trace.to_dict(),
            },
        )

    evidence_list: list[Evidence] = []
    seen_chunks: set[str] = set()

    for hop in trace.hops:
        for chunk_id in hop.chunk_ids:
            if chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)

            doc_id = _chunk_to_doc_id(chunk_id)
            chunk_text = ""
            if corpus is not None:
                chunk_obj = corpus.chunk(chunk_id)
                if chunk_obj is not None:
                    chunk_text = chunk_obj.text

            path_formatted = f"{hop.source_entity_name} --{hop.relation_type}--> {hop.target_entity_name}"

            evidence_list.append(
                Evidence(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    text=chunk_text,
                    score=base_score,
                    retrieval_method="reasoning",
                    evidence_origin="graph/reasoning",
                    provenance={
                        "reasoning_hop": hop.hop_index,
                        "relation": hop.relation_type,
                        "source_entity": hop.source_entity_name,
                        "target_entity": hop.target_entity_name,
                        "terminal": trace.terminal_entity_name,
                    },
                    metadata={
                        "hop_index": hop.hop_index,
                        "path_formatted": path_formatted,
                    },
                )
            )

    return RetrievalResult(
        query=trace.plan.query,
        evidence=evidence_list,
        retrieval_method="reasoning",
        metadata={
            "status": trace.status.value,
            "hops": trace.plan.num_hops,
            "terminal_entity": trace.terminal_entity_name,
            "reasoning_trace": trace.to_dict(),
        },
    )


def _chunk_to_doc_id(chunk_id: str) -> str:
    """chunk_005_001 -> doc_005."""
    parts = chunk_id.split("_")
    if len(parts) >= 2:
        return f"doc_{parts[1]}"
    return chunk_id
