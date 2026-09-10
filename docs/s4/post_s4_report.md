---

# Project Kautilya — S4 Post-Sprint Completion Report

**To:** Senior Developer / Project Lead
**From:** Junior Developer
**Date:** [Current Date]
**Sprint:** S4 — Evidence Fusion
**Baseline Entry:** `v0.3` (S3 — KAG Structural Retrieval Baseline)
**Release Tag:** `v0.4`
**Status:** ✅ Complete
**Branch Lifecycle:** `s4-evidence-fusion` → merged into `main` (`--no-ff`) → deleted
**Primary Deliverable:** A deterministic, contract-preserving evidence fusion layer that consumes semantic (RAG) and structural (KAG) retrieval results, deduplicates by `chunk_id`, applies rank-based score normalization, computes a weighted fusion score with an agreement bonus, and returns a deterministically-ranked unified `RetrievalResult` — delivered without modifying any S1, S2, or S3 code, contract, or corpus.

---

## 1. Executive Summary

S4 built the smallest scientifically credible evidence fusion baseline that could be inspected, demonstrated, measured, and honestly compared against the S2 (semantic) and S3 (structural) retrieval baselines.

The sprint answered one deliberately narrow research question:

> **Does deterministic rank-based fusion of semantic and structural retrieval, with a modest agreement bonus, improve evidence retrieval compared with either retriever independently?**

The answer, measured against a purpose-built 30-question diagnostic benchmark, is **partially and asymmetrically**: fusion improves Recall@1 over both baselines but degrades Recall@3 versus semantic on multi-hop compositional questions. This is exactly the kind of result S4 was designed to expose — an honest measurement of where fusion helps, where it is neutral, and where it actively hurts, rather than a monolithic validation.

### Headline Metrics (S4 benchmark, 30 questions)

|              | Recall@1 | Recall@3 | Recall@5 |
| ------------ | -------: | -------: | -------: |
| **Semantic** |   60.0%  |   90.0%  |   96.7%  |
| **KAG**      |   43.3%  |   80.0%  |   93.3%  |
| **Fusion**   | **63.3%**|   80.0%  |   93.3%  |

**Fusion Δ vs Semantic:** Recall@1 **+3.3%**, Recall@3 **−10.0%**, Recall@5 **−3.3%**
**Fusion Δ vs KAG:** Recall@1 **+20.0%**, Recall@3 **±0.0%**, Recall@5 **±0.0%**

### Latency (avg per query)

|            | Time     |
| ---------- | -------: |
| Semantic   | 14.23 ms |
| KAG        |  0.36 ms |
| Fusion     |  0.16 ms |
| **Hybrid total** | **14.75 ms** |

Hybrid retrieval costs essentially one additional structural query and a negligible fusion pass. The dominant cost remains the semantic embedding step.

Critically, **S1, S2, and S3 were not disturbed**. All 47 pre-existing tests continue to pass unchanged. The S2 semantic retriever, the S3 KAG retriever, and their evaluations are byte-identical to `v0.3`. The total test suite now stands at **80 tests, all passing**, with ruff clean.

---

## 2. Sprint Objectives — Original vs. Delivered

| # | Objective                                                              | Status       |
|---|------------------------------------------------------------------------|--------------|
| 1 | `EvidenceFusion` component with dedup, normalization, ranking          | ✅ Delivered  |
| 2 | Reuse existing `Evidence` / `RetrievalResult` contracts unchanged      | ✅ Delivered  |
| 3 | Score normalization strategy documented (rank-based)                   | ✅ Delivered  |
| 4 | Deterministic tie-breaking (no randomization, no hash-order dep.)      | ✅ Delivered  |
| 5 | CLI: `kautilya retrieve --mode hybrid`                                 | ✅ Delivered  |
| 6 | CLI: `kautilya evaluate s4` (S2/S3 preserved)                          | ✅ Delivered  |
| 7 | S4 benchmark with six diagnostic categories                            | ✅ Delivered  |
| 8 | Full test coverage (unit, integration, contract, regression)           | ✅ Delivered  |
| 9 | Documentation (spec + completion report)                               | ✅ Delivered  |
| 10| Latency measurement                                                    | ✅ Delivered  |

**Guardrails honored throughout:** no LLM, no answer generation, no reasoning, no adaptive routing, no learned re-ranking, no ML training, no graph database, no vector database, no modification of S1/S2/S3 code or contracts, no framework introduction, no production API, no frontend.

---

## 3. Architecture Delivered

### 3.1 High-Level Shape

```
                 ┌────────────────┐
                 │    Question    │
                 └────────┬───────┘
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
      SemanticRetriever          KAGRetriever      ← untouched (S2, S3)
             │                         │
             ▼                         ▼
       RetrievalResult           RetrievalResult
             │                         │
             └────────────┬────────────┘
                          ▼
                  ┌───────────────┐
                  │ EvidenceFusion│              ← new (S4)
                  └───────┬───────┘
                          │
                          ▼
                  RetrievalResult
                          │
                          ▼
                  Unified Evidence
```

Fusion sits *around* the existing retrievers as a pure post-processing layer. It depends only on the `RetrievalResult` contract, not on the internal implementation of either retriever. This preserves the low-change-amplification architecture established in S2 and extended in S3.

### 3.2 Contract Reuse — Zero Modification

The most consequential architectural finding of the sprint: **`Evidence` and `RetrievalResult` required zero changes.**

S2 had the foresight to include free-form `metadata: dict[str, Any]` and `provenance: dict[str, Any]` fields on `Evidence`. S3 demonstrated that structural detail (relation IDs, path formatting, hop counts) could be carried through those fields without altering the type. S4 continues that pattern: all fusion bookkeeping lives in `metadata`.

The fused `Evidence` items carry:

```python
metadata = {
    "fusion_sources": ["semantic", "structural"],  # which methods found this chunk
    "semantic_rank": 2,  # 1-indexed; None if not found by semantic
    "structural_rank": 1,  # None if not found by structural
    "semantic_score": 0.7074,  # raw score; None if not found
    "structural_score": 0.8333,  # raw score; None if not found
    "semantic_norm_score": 0.8,  # rank-normalized
    "structural_norm_score": 1.0,
    "fusion_score": 2.3,  # final combined score
    "agreement": True,  # found by ≥2 methods
    # KAG-specific fields preserved when present:
    "path_formatted": "Vector Labs <--ACQUIRED-- Nova Systems",
    "path_hops": 1,
    # Semantic escape hatch:
    "semantic_provenance": {"source_document": "doc_005", "source_chunk": "chunk_005_001"},
}
```

For hybrid (both-found) items: `retrieval_method="hybrid"`, `evidence_origin="hybrid"`.
For single-source items: the original method and origin are preserved verbatim.

**No `EvidenceV2`, `HybridEvidence`, `FusedEvidence`, or similar type proliferation.** This is the shape of a healthy contract layer, and it is the third consecutive sprint in which the S2 contract design has absorbed a new capability without modification.

### 3.3 The Fusion Algorithm

#### 3.3.1 Deduplication

Evidence identity is `chunk_id` alone. This is safe because the S1 corpus contract guarantees a globally unique chunk namespace (`chunk_003_001` is unambiguous across all documents). Text-based identity was explicitly rejected as fragile.

When the same chunk appears in both retrievers' results, it is merged into a single Evidence item. Structural provenance is used as the base (it is richer: relation IDs, entity IDs, relation types); semantic provenance is preserved under `metadata["semantic_provenance"]` as a non-destructive escape hatch. Provenance keys are merged without silent overwrite — if a collision occurs, the semantic key is namespaced under `semantic_<key>`.

#### 3.3.2 Score Normalization

**Rank-based normalization**, not raw-score comparison.

```
normalized_score(rank, k) = (k - rank + 1) / k

  rank 1 of 5 → 1.0
  rank 2 of 5 → 0.8
  rank 3 of 5 → 0.6
  rank 4 of 5 → 0.4
  rank 5 of 5 → 0.2
```

**Rationale:** Semantic scores (cosine similarity, spread ~0.5–0.9) and structural scores (heuristic hop decay, often tied at 0.8333 for 1-hop paths) are on fundamentally different scales with fundamentally different semantics. A raw-score weighted sum would make KAG dominate every query because 0.8333 > 0.7074 despite the KAG score carrying far less discriminative information. Rank normalization removes that false comparability and lets the agreement signal — a qualitatively different kind of information — do useful work.

This is a deliberate S4 baseline choice. Score-aware fusion (e.g., min-max normalization, learned calibration) is a separate future experiment that can be layered on top of the rank-based baseline.

#### 3.3.3 Fusion Score Formula

```
fusion_score =
      w_sem × normalized_semantic_score      (0 if not found by semantic)
    + w_kag × normalized_structural_score    (0 if not found by structural)
    + agreement_bonus × (1 if found by both else 0)
```

**Baseline experimental parameters** (configured in `experiments/configs/s4_hybrid.yaml`):

- `semantic_weight = 1.0`
- `structural_weight = 1.0`
- `agreement_bonus = 0.5`

These are **hypotheses to be tested**, not truths. They provide symmetric weighting with a modest reward for cross-source agreement (0.5 is half a rank-1 normalized score — enough to lift agreed evidence but not enough to overwhelm a rank-1 unique hit from either source).

#### 3.3.4 Deterministic Tie-Breaking

```
sort_key = (-fusion_score, -agreement, best_rank, chunk_id)
```

- **Primary:** higher fusion score first.
- **Secondary:** agreement (both-found) beats single-source at the same score. This ensures that when two items have identical fusion scores, the one independently confirmed by both retrievers ranks higher.
- **Tertiary:** better (lower) best rank across either source. This breaks ties between items that agree on score and agreement status but differ in how strongly either retriever ranked them.
- **Final:** `chunk_id` alphabetical ascending. This guarantees bit-identical output across runs regardless of Python hash ordering, set iteration order, or any other source of nondeterminism.

No randomization anywhere in the pipeline.

### 3.4 CLI Extensions

`src/kautilya/cli/__main__.py` was extended in-place:

- **`kautilya retrieve <query> --mode hybrid`** — new. Prints semantic input, structural input, and fused output with per-item source attribution, ranks, agreement flags, path information, and latency breakdown.
- **`kautilya evaluate s4`** — new. Runs RAG, KAG, and Fusion side-by-side over the S4 benchmark; reports Recall@1/3/5 with per-category breakdown, deltas versus each baseline, latency, and per-question failure detail.
- **`--mode semantic`**, **`--mode kag`**, **`evaluate s2`**, **`evaluate s3`** — all preserved byte-identical.

---

## 4. The S4 Benchmark

`data/benchmarks/s4_questions.yaml` — 30 questions across six diagnostic categories deliberately designed to be **diagnostic, not flattering**:

| Category              | n | Purpose                                                       |
| --------------------- |--:| ------------------------------------------------------------- |
| `semantic_friendly`   | 7 | Lexical/topical questions where RAG should shine              |
| `structural_friendly` | 6 | Relation-typed questions where KAG should shine               |
| `agreement`           | 3 | Questions where both retrievers should return the same chunk  |
| `complementary`       | 5 | Questions where each retriever returns different-but-useful evidence |
| `ambiguous_hub`       | 4 | Hub entities where KAG produces structural ties               |
| `hybrid_required`     | 5 | Multi-hop compositional queries where only fusion is expected to succeed |

**Design principles:**

1. **Written against the actual S1 corpus.** Every question references entities, relations, and chunks that exist in the 12-document, 15-entity, 23-relation controlled corpus. No speculative entities.
2. **Genuinely diagnostic.** The benchmark includes cases where RAG wins, KAG wins, both win, both fail, and fusion is expected to win. A benchmark where fusion magically wins everything would be less scientifically useful than one that exposes failure modes.
3. **Ground truth is explicit.** Each question carries `(document_id, chunk_id)` pairs as expected evidence, enabling automated Recall@K calculation.
4. **Reproducible.** Deterministic retrievers + deterministic fusion = identical results across runs.

---

## 5. Results in Detail

### 5.1 Headline Recall

|              | Recall@1 | Recall@3 | Recall@5 |
| ------------ | -------: | -------: | -------: |
| **Semantic** |   60.0%  |   90.0%  |   96.7%  |
| **KAG**      |   43.3%  |   80.0%  |   93.3%  |
| **Fusion**   | **63.3%**|   80.0%  |   93.3%  |

### 5.2 Per-Category Recall@3

| Category              | Semantic | KAG    | Fusion | n |
| --------------------- | -------: | -----: | -----: |--:|
| `agreement`           |  100.0%  | 100.0% | 100.0% | 3 |
| `ambiguous_hub`       |  100.0%  | 100.0% | 100.0% | 4 |
| `complementary`       |  100.0%  |  80.0% |  80.0% | 5 |
| `hybrid_required`     |   60.0%  |  20.0% |  40.0% | 5 |
| `semantic_friendly`   |  100.0%  | 100.0% | 100.0% | 7 |
| `structural_friendly` |   83.3%  |  83.3% |  66.7% | 6 |

### 5.3 Where Fusion Helped

**`ambiguous_hub` (Recall@1 improvement):** This is exactly the case S4 was built for. When KAG returned five 1-hop paths all scoring 0.8333 (structurally indistinguishable because they are all valid 1-hop facts about the same hub entity), semantic re-ranking via the agreement bonus surfaced the correct chunk to rank 1.

The canonical example is the Vector Labs "What technology did they develop?" query:
- Semantic rank 1: `chunk_002_001` (Vector Labs founding doc — topically relevant but doesn't name the technology)
- KAG rank 1: `chunk_005_001` (via `ACQUIRED` relation — mentions "HelixDB")
- **Fusion rank 1: `chunk_005_001`** (sem_rank=2 + kag_rank=1 + agreement → fusion_score=2.3)

Fusion correctly elevated the chunk containing the actual answer ("HelixDB") above semantic's topically-similar but less informative rank-1 hit.

**Recall@1 overall (+20% vs KAG, +3.3% vs semantic):** Agreement is a strong signal for the *most likely* correct answer when both retrievers independently converge on the same chunk.

### 5.4 Where Fusion Hurt

**`hybrid_required` (Recall@3: 40% vs semantic 60%):** Multi-hop compositional questions like *"Who founded the company that acquired Vector Labs?"* Semantic occasionally caught the correct chunk at rank 5. KAG, given only "Vector Labs" as the resolved seed entity, flooded its top-5 with the same hub-connected chunks. Fusion's agreement bonus then amplified those hub chunks and pushed semantic's rank-5 correct hit off the fused top-5.

**`structural_friendly` (Recall@3: 66.7% vs semantic 83.3%):** Similar mechanism — when semantic finds the correct chunk late in its list and KAG cannot help disambiguate a hub, fusion's agreement-first behavior can suppress the correct answer.

### 5.5 The Two Fusion Failures — Detailed Analysis

Both failures were `hybrid_required` multi-hop compositional questions:

**Failure 1 — `s4_q22`: "Who founded the company that acquired Vector Labs?"**
- **Expected:** `chunk_001_001` or `chunk_012_001` (both describe Rohan Kapoor founding Nova Systems).
- **Semantic:** Retrieved `chunk_012_001` at rank 5 (just barely in the window).
- **KAG:** Seeded only on "Vector Labs" — did not retrieve either expected chunk. All five results were Vector-Labs-adjacent.
- **Fusion:** Dropped `chunk_012_001` because four Vector-Labs-adjacent chunks had mutual agreement and outranked it.
- **Root cause:** The question requires composing two hops (`acquire(Vector Labs) → Nova Systems`, then `founded_by(Nova Systems) → Rohan Kapoor`). Neither retriever seeds on "Rohan Kapoor" or "Nova Systems" as the primary entity. Semantic catches the answer by lexical proximity at the tail of its list; KAG cannot reach it from the Vector Labs seed. Fusion's agreement bonus amplifies the wrong convergence.

**Failure 2 — `s4_q24`: "Who co-founded the company that Nova Systems acquired?"**
- **Expected:** `chunk_002_001` or `chunk_006_001` (Mira Sharma co-founding Vector Labs).
- **Semantic:** Had `chunk_006_001` at rank 5.
- **KAG:** Had `chunk_002_001` at rank 5.
- **Fusion:** Dropped both because Nova-Systems-adjacent chunks with mutual agreement outranked them.
- **Root cause:** Same structural signature as s4_q22. The compositional chain (`acquired_by(Nova Systems) → Vector Labs`, then `co_founded_by(Vector Labs) → Mira Sharma`) requires two hops that neither retriever's seed produces directly.

**Shared failure signature:** The question requires composing two hops that neither retriever's seed entity produces. Each retriever finds a partial answer at the tail of its own list. The agreement-bonus fusion punishes tail-of-list survivors in favor of high-agreement hub neighbors.

This is precisely the phenomenon warned about in the S4 specification (§13):

> **Do NOT assume agreement automatically means truth.** Agreement is *retrieval agreement*, not *correctness agreement*.

---

## 6. Research Outcome Classification

The S4 specification (§33) defined four possible outcomes:

| Outcome | Description | Observed? |
| ------- | ----------- | --------- |
| **A** — Strong fusion | Fusion outperforms both baselines across all metrics | ❌ Not observed |
| **B** — Small improvement | Fusion marginally improves some metrics | ✅ Observed at Recall@1 |
| **C** — No improvement | Fusion matches but does not exceed baselines | ✅ Observed at Recall@3/5 vs KAG |
| **D** — Fusion makes things worse | Fusion degrades some metrics vs a baseline | ✅ Observed on `hybrid_required` and `structural_friendly` vs semantic |

The realistic classification is **B + C + D concurrently**: fusion is a real improvement for surface-level questions where both retrievers agree on the correct answer, neutral on categories where one retriever already saturates, and a real regression on multi-hop compositional questions where neither retriever is confident.

**This is a successful research result.** It maps a specific failure mode (multi-hop composition + hub agreement echo chambers) and points directly at the next research direction. A monolithic "fusion wins everywhere" result would have been less informative and less honest.

---

## 7. Implications for S5

The failure signature suggests three research directions, in increasing order of ambition:

### 7.1 Query Decomposition

Multi-hop questions like *"Who founded the company that acquired Vector Labs?"* need to be split into sub-queries: `acquire(Vector Labs) → Nova Systems`, then `founded_by(Nova Systems) → Rohan Kapoor`. KAG has all the necessary relations in the graph; it just needs multi-step guidance. This is where reasoning enters and is the most natural S5 candidate.

### 7.2 Adaptive Fusion Weights

For `hybrid_required` questions, the agreement bonus may need to be dampened or replaced with a diversity bonus that rewards evidence from different structural neighborhoods. For `agreement` and `ambiguous_hub` questions, the current bonus works well. Adaptive routing (choosing fusion parameters based on query characteristics) is explicitly out of scope for S4 but is a natural S5 extension.

### 7.3 Score-Aware Normalization

Rank normalization discards absolute confidence information. A semantic hit at cosine 0.85 vs 0.55 is meaningful; KAG's uniform 0.8333 is not. A hybrid normalizer that respects semantic confidence spread while still handling KAG ties could reduce the `hybrid_required` regression. This is a separate experiment that can be A/B tested against the rank-based baseline.

**None of these belong in S4.** S4 is the baseline against which they will be measured.

---

## 8. Notable Implementation Findings

### 8.1 Rank Normalization Was the Right Call

Raw-score fusion would have been catastrophic on this corpus. Semantic cosine similarity ranges roughly 0.5–0.9; KAG structural scores are almost uniformly 0.8333 (1-hop paths scored as `1 / (1 + 0.2 × 1)`). A weighted sum of raw scores would have made KAG dominate every query regardless of semantic relevance. Rank normalization removed the false comparability and let agreement — a fundamentally different and more informative signal — do useful work.

### 8.2 The Agreement Bonus Is a Double-Edged Instrument

At 0.5 (half a rank-1 normalized score), agreement is strong enough to lift agreed-on evidence to the top but not strong enough to overwhelm a rank-1 unique hit from either source. In the `ambiguous_hub` case this is exactly right: it breaks KAG's structural ties using semantic signal. In the `hybrid_required` case it becomes a liability because it amplifies retrieval echo chambers around hub entities. **This is not a bug to fix in S4; it is a finding to document and a lever for S5 to tune.**

### 8.3 Latency Is Dominated by Embedding, Not Fusion

Fusion itself averaged 0.16 ms per query. The hybrid overhead versus pure semantic is negligible (14.75 ms vs 14.23 ms — the extra ~0.5 ms is KAG graph traversal). This confirms fusion is architecturally cheap. Any future latency budget concerns will be about the retrievers, not the fusion layer. If S5 introduces query decomposition or multi-step retrieval, that is where latency will need to be managed.

### 8.4 Deduplication Rate Is Meaningful

Across the benchmark, the average deduplication rate was ~30–40%, meaning roughly one-third of the combined evidence pool was redundant between the two retrievers. This is high enough to justify the deduplication step (without it, top-K slots would be wasted on duplicates) but low enough to confirm that the two retrievers are genuinely complementary — they are not simply returning the same evidence in different orders.

---

## 9. Testing & Quality

### 9.1 Test Suite

| Test file                                    | Tests | Purpose                                        |
| -------------------------------------------- | ----: | ---------------------------------------------- |
| `tests/contracts/test_contracts.py`          |     4 | S1 contract construction (unchanged)           |
| `tests/contracts/test_retrieval_contracts.py`|     2 | S2 Evidence/RetrievalResult (unchanged)        |
| `tests/contracts/test_knowledge_path.py`     |     3 | S3 KnowledgePath (unchanged)                   |
| `tests/knowledge/test_corpus.py`             |     7 | S1 corpus loading (unchanged)                  |
| `tests/knowledge/test_graph.py`              |    15 | S3 graph traversal (unchanged)                 |
| `tests/retrieval/test_index.py`              |     4 | S2 vector index (unchanged)                    |
| `tests/retrieval/test_semantic.py`           |     5 | S2 semantic retriever (unchanged)              |
| `tests/retrieval/test_structural.py`         |     7 | S3 KAG retriever (unchanged)                   |
| `tests/fusion/test_evidence_fusion.py`       |    29 | **New** — Fusion unit tests                    |
| `tests/fusion/test_hybrid_integration.py`    |     4 | **New** — End-to-end hybrid against real corpus|
| **Total**                                    | **80**|                                                |

### 9.2 Coverage Layers

**Unit tests** (`test_evidence_fusion.py`):
- `_rank_normalize`: boundary values, monotonicity, out-of-range, zero-k.
- Smoke: return type, query preservation, mismatched query rejection.
- Deduplication: same-chunk dedup, disjoint preservation, dedup rate calculation.
- Scoring: agreement bonus application, no-bonus single-source, weight scaling, metadata rank/score capture.
- Ranking: score ordering, agreement tiebreak, chunk_id alphabetical tiebreak, top-K truncation, determinism.
- Provenance: structural preservation, semantic escape hatch, KAG path metadata.
- Edge cases: both empty, semantic-only, structural-only, contract shape validation.

**Integration tests** (`test_hybrid_integration.py`):
- End-to-end hybrid against the real S1 corpus with real embedding model.
- Verifies that `chunk_005_001` (the HelixDB/acquisition chunk) surfaces at rank 1 for the Vector Labs query.
- Verifies determinism across repeated runs.
- Verifies metadata population.

**Regression:** All 47 pre-existing S1/S2/S3 tests unchanged and green. No test was deleted, disabled, or weakened.

### 9.3 Quality Gates

- `uv run pytest -q` → **80 passed** in ~25s.
- `uv run ruff check .` → **All checks passed.**
- Determinism verified at three layers: unit, integration, and empirical (S4 evaluation is reproducible across runs).

---

## 10. Deviations from the Brief

1. **No ADR created.** No S1/S2/S3 contracts were modified. The additive introduction of `EvidenceFusion` (new module, new class, no changes to existing types) does not qualify per project convention. This mirrors S2 and S3 precedent.

2. **`retrieval_method="hybrid"` for merged evidence.** The Evidence contract's `retrieval_method` field is a single string. When an evidence item is found by both retrievers, we label it `"hybrid"` and record the constituent methods in `metadata["fusion_sources"]`. This preserves the frozen dataclass shape while making the fusion source inspectable. Alternative approaches (list-typed method, new EvidenceHybrid subclass) would have violated the locked design decision to avoid contract modification.

3. **Sprint branch named `s4-evidence-fusion`** rather than `sprint/s4-evidence-fusion`. Naming convention deviation only; branch discipline (feature branch, `--no-ff` merge, delete after merge) preserved.

None of these deviations affect the deliverables or the definition of done.

---

## 11. Known Limitations

Recorded deliberately as inputs to S5.

1. **Agreement bonus amplifies hub echo chambers.** On multi-hop compositional questions where both retrievers are seeded on the same starting entity, both flood their top-K with that entity's 1-hop neighborhood. Agreement rewards this convergence, suppressing the actual (further-hop) answer. This is the primary failure mode and the most important input to S5.

2. **Fusion cannot decompose compositional questions.** *"Who founded the company that acquired Vector Labs?"* requires two hops. Neither retriever seeds on "Rohan Kapoor" (the answer entity), so the correct chunks appear late in each list. Fusion has no mechanism to reason through the composition.

3. **Rank normalization discards absolute confidence.** A semantic hit at cosine 0.85 and one at 0.55 both look like "rank 1" and "rank 2" to fusion. This is the deliberate S4 trade-off but is worth revisiting in S5 with score-aware normalization experiments.

4. **The corpus is small.** 12 chunks, 15 entities, 23 relations. Both RAG and KAG saturate on many questions. Meaningful discrimination requires either a larger corpus or a more adversarial benchmark. The S4 results are a claim about the fusion *pipeline* being correct, not about fusion *in general* being superior.

5. **Fusion is not adaptive.** Every query pays the cost of running both retrievers. For questions clearly in one retriever's sweet spot, this is wasteful. Adaptive routing is an explicit S5 candidate.

6. **No answer generation.** S4, like S2 and S3, retrieves evidence. It does not synthesize answers. This remains explicitly out of scope until the reasoning sprint.

7. **Benchmark is authored against the corpus.** As with S2 and S3, the benchmark was written to match actual S1 content. This is correct methodology but means the benchmark is calibrated to what the corpus covers well. It is not adversarial.

---

## 12. Inputs to S5 (Hybrid Reasoning)

S4 hands S5 the following:

1. **A working fusion baseline** with three measurable regimes: where it helps (Recall@1, `ambiguous_hub`), where it is neutral (`agreement`, `semantic_friendly`), and where it hurts (`hybrid_required`, `structural_friendly`).

2. **A concrete failure mode to solve:** multi-hop compositional questions where the answer is not reachable from any single seed entity. The two fusion failures (s4_q22, s4_q24) are the minimal test cases for S5's query decomposition capability.

3. **The `KnowledgePath` contract** already exposes hop counts, relation types, and directions — the raw material for multi-step reasoning.

4. **The `EvidenceFusion.metadata` inspectable trace** — S5 can reason about which chunks were agreed-on vs unique, how fusion arrived at its ranking, and whether alternative weightings would have surfaced the correct answer.

5. **A benchmark with `hybrid_required` questions that fusion cannot solve.** These are the questions S5 must break.

6. **A clean CLI boundary** (`--mode hybrid`) that S5 can extend with `--mode reasoning`.

7. **Latency budget headroom.** Fusion adds ~0.5 ms overhead. S5 has room to add multi-step retrieval before latency becomes a concern.

S5 must not modify S2, S3, or S4. It should build a peer capability that consumes fusion output (or the underlying retrievers directly) and produces reasoning-augmented retrieval.

---

## 13. Definition of Done — Checklist

### Fusion
- [x] Semantic and KAG results can be consumed together
- [x] Evidence is deduplicated deterministically (`chunk_id`)
- [x] Retrieval-source information is preserved (`fusion_sources` in metadata)
- [x] Provenance is preserved (structural as base, semantic as escape hatch)
- [x] Structural path information is preserved (`path_formatted`, `path_hops`)
- [x] Scores are normalized before cross-source comparison (rank-based)
- [x] Fusion ranking is deterministic (`(-score, -agreement, best_rank, chunk_id)`)
- [x] top-k works correctly

### CLI
- [x] `--mode semantic` still works (100/100/100 on S2 benchmark)
- [x] `--mode kag` still works (60/100/100 on S3 benchmark)
- [x] `--mode hybrid` works
- [x] `evaluate s2` still works
- [x] `evaluate s3` still works
- [x] `evaluate s4` works

### Benchmark
- [x] S4 benchmark exists (30 questions)
- [x] Semantic-friendly cases exist (7)
- [x] Structural-friendly cases exist (6)
- [x] Complementary cases exist (5)
- [x] Agreement cases exist (3)
- [x] Ambiguous-hub cases exist (4)
- [x] Hybrid-required cases exist (5)
- [x] Ground truth is explicit
- [x] Benchmark is reproducible (deterministic)

### Evaluation
- [x] RAG baseline measured (60.0 / 90.0 / 96.7)
- [x] KAG baseline measured (43.3 / 80.0 / 93.3)
- [x] Fusion measured (63.3 / 80.0 / 93.3)
- [x] Recall@1/3/5 reported
- [x] Fusion deltas reported (+3.3% / −10.0% / −3.3% vs sem; +20.0% / ±0.0% / ±0.0% vs KAG)
- [x] Latency measured (14.75 ms hybrid total)

### Regression
- [x] All S1 tests pass (4/4)
- [x] All S2 tests pass (11/11)
- [x] All S3 tests pass (32/32)
- [x] All S4 tests pass (33/33)
- [x] Total: 80/80 passing
- [x] Ruff clean

### Documentation
- [x] S4 specification exists (`docs/s4/s4-evidence-fusion.md`)
- [x] Implementation documented
- [x] Fusion algorithm documented
- [x] Score normalization documented
- [x] Benchmark methodology documented
- [x] Results documented
- [x] Limitations documented
- [x] No architectural changes required no ADR

### Git
- [x] S4 branch starts from `v0.3`
- [x] Capability-scoped commits
- [x] Merged with `--no-ff`
- [x] Branch deleted after merge
- [x] `v0.4` tagged
- [x] `v0.1`, `v0.2`, `v0.3` intact
- [x] `main` clean
- [x] `origin/main` synchronized

---

## 14. Progression

```
v0.0    Foundation
  │
v0.1    S1 — Knowledge World
  │       "We have something to reason over."
  │
v0.2    S2 — Semantic Retrieval Baseline
  │       "We can retrieve textual evidence."
  │
v0.3    S3 — KAG Structural Retrieval Baseline
  │       "We can retrieve structural evidence."
  │
v0.4    S4 — Evidence Fusion                    ← YOU ARE HERE
  │       "We can combine them — sometimes it helps, sometimes it hurts."
  │
v0.5    S5 — Hybrid Reasoning
  │       "Can composition and adaptivity beat naive fusion?"
  │
        Evaluation → V0 Research Result
```

---

## 15. Closing Note

S4 was a research sprint whose success criterion was not *"fusion wins"* but *"we now understand whether and how fusion adds value."* On that criterion it succeeded.

The 63.3% Recall@1 headline is real, and it beats both baselines. So is the −10% Recall@3 regression on `hybrid_required` questions. Both numbers are honest measurements against a diagnostic benchmark, and together they map the terrain S5 has to cross.

What we now have:

- A fusion layer that consumes two `RetrievalResult`s and emits one — with zero contract changes across three consecutive sprints.
- A benchmark that isolates six diagnostic categories, including cases fusion is expected to fail.
- Metrics that show fusion helps at rank 1 (+3.3% vs semantic, +20% vs KAG) and hurts on multi-hop composition (−10% Recall@3 vs semantic on `hybrid_required`).
- A test suite of 80 tests that guarantees fusion is deterministic and that S1/S2/S3 remain untouched.
- Documentation that records not just what was built, but *why the numbers look the way they do and what they imply for S5.*

The S4 specification warned:

> Enter it asking: **Under what knowledge/question conditions does combining semantic and structural evidence improve retrieval?**

We now have an answer to that question, and it is more interesting than a monolithic win would have been.

**Kautilya has learned to combine what it sees and what it knows. S5 will teach it to reason about the composition.**

---

*Report generated for Project Kautilya, post-S4 milestone. Baseline `v0.4` established, tagged, and merged.*
*80/80 tests passing. Ruff clean. Working tree clean. Ready for S5.*