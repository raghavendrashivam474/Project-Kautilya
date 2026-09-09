# S4 — Evidence Fusion Specification

**Sprint:** S4 — Evidence Fusion
**Baseline Entry:** `v0.3` (S3 — KAG Structural Retrieval Baseline)
**Release Tag:** `v0.4`
**Status:** Implemented

---

## 1. Research Question

> **Does deterministic rank-based fusion of semantic and structural retrieval, with a modest agreement bonus, improve evidence retrieval compared with either retriever independently?**

S4 does not build answer generation, reasoning, or adaptive routing. It answers one question: **can we combine RAG and KAG evidence into a better-ranked unified result?**

## 2. Architecture
text

             ┌────────────────┐
             │    Question    │
             └────────┬───────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
  SemanticRetriever          KAGRetriever
         │                         │
         ▼                         ▼
   RetrievalResult           RetrievalResult
         │                         │
         └────────────┬────────────┘
                      ▼
              ┌───────────────┐
              │ EvidenceFusion│
              └───────┬───────┘
                      │
                      ▼
              RetrievalResult
text


**Zero modifications to S1, S2, S3, or the `Evidence` / `RetrievalResult` contracts.** Fusion sits *around* the existing retrievers as a pure post-processing layer that consumes two `RetrievalResult` objects and returns one.

## 3. Fusion Algorithm

### 3.1 Deduplication

Evidence identity is `chunk_id` alone. This is safe because the S1 corpus contract guarantees a globally unique chunk namespace.

When the same chunk appears in both retrievers' results, it is merged into a single Evidence item. Structural provenance is preserved as the base (richer); semantic provenance is preserved under `metadata["semantic_provenance"]`.

### 3.2 Score Normalization

**Rank-based normalization**, not raw-score comparison.
normalized_score(rank, k) = (k - rank + 1) / k

rank 1 of 5 → 1.0
rank 2 of 5 → 0.8
rank 3 of 5 → 0.6
rank 4 of 5 → 0.4
rank 5 of 5 → 0.2

text


**Rationale:** Semantic scores (cosine similarity, spread 0.5–0.9) and structural scores (heuristic hop decay, often tied at 0.8333) are on different scales with different semantics. Rank normalization removes that false comparability. Score-aware fusion is a separate future experiment.

### 3.3 Fusion Score
fusion_score =
w_sem * normalized_semantic_score (0 if not found by semantic)
+ w_kag * normalized_structural_score (0 if not found by structural)
+ agreement_bonus * (1 if found by both else 0)

text


**Baseline experimental parameters** (see `experiments/configs/s4_hybrid.yaml`):

- `semantic_weight = 1.0`
- `structural_weight = 1.0`
- `agreement_bonus = 0.5`

These are **hypotheses**, not truths. They provide symmetric weighting with a modest reward for cross-source agreement.

### 3.4 Deterministic Tie-Breaking
sort_key = (-fusion_score, -agreement, best_rank, chunk_id)

text


- Primary: higher fusion score first.
- Secondary: agreement (both-found) beats single-source at same score.
- Tertiary: better (lower) best rank across either source.
- Final: `chunk_id` alphabetical ascending — guarantees bit-identical output.

## 4. Contract Reuse

`Evidence` was **not modified**. The existing free-form `metadata` and `provenance` fields express everything fusion needs:

```python
metadata = {
    "fusion_sources": ["semantic", "structural"],   # methods that found this chunk
    "semantic_rank": 2,          # None if not found by semantic
    "structural_rank": 1,        # None if not found by structural
    "semantic_score": 0.7074,
    "structural_score": 0.8333,
    "semantic_norm_score": 0.8,
    "structural_norm_score": 1.0,
    "fusion_score": 2.3,
    "agreement": True,
    # KAG-only fields (preserved when present):
    "path_formatted": "Vector Labs <--ACQUIRED-- Nova Systems",
    "path_hops": 1,
    "semantic_provenance": {...},   # escape hatch for semantic provenance
}
For hybrid (both-found) items: retrieval_method="hybrid", evidence_origin="hybrid".
For single-source items: the original method/origin is preserved.

5. CLI
kautilya retrieve <query> --mode hybrid — new. Prints semantic input, structural input, and fused output with per-item source attribution, ranks, and latency.
kautilya retrieve <query> --mode semantic — unchanged from S2.
kautilya retrieve <query> --mode kag — unchanged from S3.
kautilya evaluate s4 — new. Runs RAG, KAG, and Fusion side-by-side over the S4 benchmark; reports Recall@1/3/5 with per-category breakdown, deltas, and latency.
kautilya evaluate s2, kautilya evaluate s3 — unchanged.
6. Benchmark
data/benchmarks/s4_questions.yaml — 30 questions across six diagnostic categories:

Category    Purpose    Count
semantic_friendly    Lexical/topical — RAG should shine    7
structural_friendly    Relation-typed — KAG should shine    6
agreement    Both retrievers should return the same chunk    3
complementary    Each retriever returns different-but-useful evidence    5
ambiguous_hub    Hub entities where KAG produces structural ties    4
hybrid_required    Only fusion should succeed (multi-hop compositional queries)    5
Ground truth is per-question (document_id, chunk_id) pairs, authored against the actual S1 corpus.

7. What S4 Does Not Do
No LLM answer generation.
No reasoning.
No adaptive routing (fusion always runs both retrievers).
No learned re-ranking or ML training.
No graph or vector database.
No modifications to S1/S2/S3 code or contracts.
No claim that agreement = truth. Agreement is retrieval agreement, not correctness.
8. Files Added / Modified
Added:

src/kautilya/fusion/evidence_fusion.py
src/kautilya/fusion/__init__.py (populated)
tests/fusion/test_evidence_fusion.py
tests/fusion/test_hybrid_integration.py
data/benchmarks/s4_questions.yaml
experiments/configs/s4_hybrid.yaml
docs/s4/s4-evidence-fusion.md (this file)
docs/s4/post_s4_report.md
Modified:

src/kautilya/cli/__main__.py — added --mode hybrid and evaluate s4; existing modes unchanged.
9. Definition of Done
See post_s4_report.md §11.
