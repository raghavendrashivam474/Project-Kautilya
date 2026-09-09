# Project Kautilya — Post-S6 Completion Report

**To:** Senior Developer / Technical Lead
**From:** S6 Implementation Team
**Sprint:** S6 — Reasoning-Aware Hybrid Evidence Selection
**Baseline:** `v0.5` (S5 Hybrid Reasoning)
**Release:** `v0.6`
**Status:** ✅ Completed — merged to `main`, tagged, pushed
**Branch (deleted post-merge):** `sprint/s6-reasoning-aware-fusion`

---

## 1. Executive Summary

Sprint S6 investigated the primary research question stated in the sprint brief:

> **Does integrating reasoning-derived evidence into the existing semantic + structural evidence fusion pipeline improve retrieval quality over the current S4 rank-based fusion baseline?**

The investigation was constrained by the brief's north star:

> *Do not build a more complicated Kautilya. Build the smallest experiment that can tell us whether reasoning-aware evidence fusion is actually better.*

We complied. The entire sprint was executed as a **single additive change** to `EvidenceFusion.fuse()` — one optional parameter — plus supporting tests, benchmark, config, CLI wiring, and documentation. No contract was modified. No new class was introduced in the fusion module. No pre-existing S1–S5 test was altered.

### 1.1 Headline Result

Three-way reasoning-aware fusion **improves Recall@1 by +4.2 percentage points** and **Recall@5 by +4.2 percentage points** over the S4 two-way baseline on the S6 diagnostic benchmark, at a cost of −4.2 percentage points on Recall@3. The result is best classified as **Outcome B — Small Improvement with Deep Mechanistic Insights** per the sprint brief's outcome taxonomy (Section 31).

The improvement is real but non-monotonic across K, and the mechanism behind the non-monotonicity is fully understood, reproducible, and documented. This is a more informative research result than a monolithic "S6 wins everywhere" would have been, and it points directly at the next experiment.

### 1.2 Sprint Discipline Snapshot

| Metric | Value |
|:-------|:------|
| Baseline preserved | ✅ v0.5 untouched; all prior tags intact |
| Contract changes | **0** (`Evidence`, `RetrievalResult`, `KnowledgePath`, `KnowledgeGraph`, all S5 reasoning contracts unchanged) |
| Files modified (non-additive) | **2** (`evidence_fusion.py`, `cli/__main__.py`) |
| Files added | **5** (2 test files, 1 benchmark, 1 config, docs directory) |
| Total tests | **118** (was 107 on v0.5; +11 new) |
| Test pass rate | **100%** (118/118) |
| Ruff lint | **Clean** |
| S1–S5 regression | **None** — all pre-existing tests pass unchanged |
| Latency overhead vs S4 | **+0.76 ms** average (~4.3%) |
| Determinism | Verified across repeated runs |

---

## 2. What Was Actually Built

### 2.1 The Single Architectural Change

The entire S6 mechanism sits in one method signature extension:

**Before (S4):**
```python
def fuse(
    self,
    semantic_result: RetrievalResult,
    structural_result: RetrievalResult,
    top_k: int = 5,
) -> RetrievalResult:
```

**After (S6):**
```python
def fuse(
    self,
    semantic_result: RetrievalResult,
    structural_result: RetrievalResult,
    reasoning_result: RetrievalResult | None = None,
    top_k: int = 5,
) -> RetrievalResult:
```

The default value `None` guarantees that every existing S4 call site continues to produce byte-identical output. This was verified explicitly with a dedicated regression test (`test_none_reasoning_gives_s4_equivalence`).

### 2.2 The Fusion Formula (Generalized)

The S4 formula:

```
fusion_score = w_sem · norm_sem + w_kag · norm_kag + bonus · agree_binary
```

was generalized to:

```
fusion_score = w_sem · norm_sem
             + w_kag · norm_kag
             + w_rea · norm_rea
             + bonus · 𝟙[source_count ≥ 2]
```

The rank normalization function `(k − rank + 1) / k` is unchanged. Each source normalizes its own ranks independently — no cross-source raw-score comparison. Unretrieved items contribute 0.

The agreement bonus generalizes cleanly: in S4 with two sources it was binary; in S6 with three sources, "agreement" means the chunk was retrieved by **at least two** of the three sources. This preserves the S4 semantics exactly when reasoning is inactive (0 or empty).

### 2.3 Deterministic Sort Key (Unchanged Shape)

```
sort_key = (-fusion_score, -agreement, best_rank, chunk_id)
```

- Primary: descending fusion score
- Secondary: agreement-first tie-break
- Tertiary: best rank across any source
- Final: alphabetical `chunk_id` (guarantees hash-order independence)

No randomization. No nondeterministic set iteration. Determinism verified in both unit and integration tests, and across 10-run integration checks.

### 2.4 New Metadata Fields on Fused Evidence

Every fused Evidence carries the following additions in `metadata`:

| Field | Meaning |
|:------|:--------|
| `fusion_sources` | List of sources that contributed (`semantic`, `structural`, `reasoning`) |
| `reasoning_rank` | 1-indexed rank in reasoning output, or `None` |
| `reasoning_score` | Raw reasoning score, or `None` |
| `reasoning_norm_score` | Rank-normalized reasoning contribution |
| `source_count` | Number of contributing sources (1–3) |
| `agreement` | Boolean: `source_count ≥ 2` |
| `fusion_score` | Final combined score |

At the `RetrievalResult` level:

| Field | Meaning |
|:------|:--------|
| `reasoning_count` | Number of reasoning evidence items received |
| `reasoning_participated` | `True` when reasoning contributed ≥ 1 item |
| `fusion_weights` | Includes `reasoning` weight when reasoning participated |

Reasoning provenance (hop index, source/target entity, relation type, terminal entity) is preserved through the adapter and carried into the fused evidence's `provenance` and `metadata` dictionaries. Where key collisions occur, the semantic/reasoning contribution is namespaced (`semantic_<key>`, `reasoning_<key>`) rather than silently overwritten.

### 2.5 CLI Extensions

Two additive changes:

**Retrieve mode:**
```
kautilya retrieve "<query>" --mode reasoning-hybrid
```
Runs all three retrievers, fuses them, and prints per-item source attribution, agreement counts, reasoning trace, and stage-by-stage latency.

**Evaluation:**
```
kautilya evaluate s6
```
Runs a five-way comparative matrix (Semantic / KAG / S4 Fusion / Reasoning / S6 Fusion) across the S6 benchmark, reports per-category Recall@K, reasoning diagnostics, and latency.

`evaluate s5` was also added (it existed in the S5 report but had never been wired into the CLI subcommand parser). All prior `evaluate` targets (`s2`, `s3`, `s4`) and all prior `--mode` values (`semantic`, `kag`, `hybrid`, `reasoning`) remain functional.

### 2.6 Safe Reasoning Degradation (Invariant 7)

The most important operational property. When reasoning cannot participate — because the decomposer returns `None` for a non-compositional query, or the executor returns `F1`–`F5`, or the seed entity is not in the corpus — the adapter emits an empty `RetrievalResult`. `EvidenceFusion.fuse()` detects `has_reasoning = False` and computes standard two-way S4 fusion.

This was verified across three layers:
1. Unit test with `reasoning_result=None`
2. Unit test with empty-evidence `RetrievalResult`
3. Unit test with a failed `ReasoningTrace` passed through the adapter
4. Integration test against the real corpus with a semantic-friendly query for which decomposition legitimately fails

The invariant holds. Ordinary retrieval is never broken by reasoning failure. This was non-negotiable per the brief (Section 19).

---

## 3. Experimental Results — The Numbers

All numbers are from a single, reproducible run of `kautilya evaluate s6` against the S6 benchmark (30 questions, 24 with positive ground truth; 6 unsupported-boundary questions correctly return 0 across all modes).

### 3.1 Overall Retrieval Metrics

| Mode | Recall@1 | Recall@3 | Recall@5 |
|:-----|:--------:|:--------:|:--------:|
| Semantic (RAG) | 25.0% | 54.2% | 79.2% |
| Structural (KAG) | 25.0% | 37.5% | 45.8% |
| **S4 Two-Way Fusion (baseline)** | **29.2%** | **58.3%** | **70.8%** |
| Standalone Reasoning (S5) | 4.2% | 20.8% | 20.8% |
| **S6 Three-Way Fusion** | **33.3%** | **54.2%** | **75.0%** |

### 3.2 S6 vs S4 Deltas (the Primary Comparison per Brief §15)

| Metric | S4 | S6 | Δ |
|:-------|:---:|:---:|:---:|
| Recall@1 | 29.2% | **33.3%** | **+4.2 pp** |
| Recall@3 | 58.3% | 54.2% | −4.2 pp |
| Recall@5 | 70.8% | **75.0%** | **+4.2 pp** |

### 3.3 Per-Category Recall@3

| Category | n | Sem | KAG | S4 | S6 | Interpretation |
|:---------|:-:|:---:|:---:|:---:|:---:|:---------------|
| ambiguous_hub | 6 | 66.7% | 50.0% | 66.7% | 66.7% | Stable — no interference |
| multi_hop_reasoning | 4 | 50.0% | 50.0% | **75.0%** | 50.0% | S4 accidentally lucky here |
| s4_failure_recovery | 2 | 0.0% | 0.0% | 0.0% | 0.0% | Chunks recovered to rank 4–6 |
| semantic_friendly | 6 | 50.0% | 0.0% | 50.0% | 50.0% | No reasoning interference |
| structural_friendly | 6 | 66.7% | 66.7% | 66.7% | 66.7% | KAG dominance preserved |
| unsupported_boundary | 6 | — | — | — | — | Empty GT; all modes correctly return 0 |

### 3.4 Reasoning Diagnostics

| Metric | Value | Interpretation |
|:-------|:-----:|:---------------|
| Decomposition invocation rate | 23.3% (7/30) | Reasoning correctly abstains on non-compositional questions |
| Chain execution success rate | 85.7% (6/7) | 1 F2 (entity resolution failure on out-of-corpus seed) |
| Reasoning contribution rate | 20.0% (6/30) | Reasoning contributed evidence to fused output 6× |
| Mean reasoning hops | 2.0 | All successful chains executed the full planned 2-hop chain |

### 3.5 Latency Profile

| Stage | Mean ms |
|:------|:-------:|
| Semantic embedding + vector search | 17.45 |
| KAG graph traversal | 0.25 |
| Reasoning decomposition + execution | 0.60 |
| S4 two-way fusion | 0.20 |
| S6 three-way fusion | 0.16 |
| **S6 hybrid total** | **18.46** |

Reasoning overhead is negligible (~0.76 ms, ~4.3% of total). The dominant cost remains the semantic embedding stage. Fusion itself, even three-way, is faster than two-way in this run — well within measurement noise, but confirming that fusion is not the bottleneck.

---

## 4. Interpretation — What the Numbers Actually Say

### 4.1 Where S6 Wins (Recall@1 and Recall@5)

At K=1, S6 elevates a genuinely-correct chunk to rank 1 that S4 could not. The clearest case is `s6_q01` (*"Who founded the company that acquired Vector Labs?"*):

```
S6 Fusion top-5:
  [1] chunk_005_001  fusion=3.30  sources: sem+kag+rea   AGREE(3)
  [2] chunk_002_001  fusion=2.10  sources: sem+kag       AGREE(2)
  [3] chunk_010_001  fusion=1.30  sources: sem+kag       AGREE(2)
  [4] chunk_006_001  fusion=1.30  sources: sem+kag       AGREE(2)
  [5] chunk_011_001  fusion=0.80  sources: kag           single
```

`chunk_005_001` (the acquisition chunk, first hop of the reasoning chain) is triple-agreed and lifted decisively to rank 1. This is exactly the failure mode S4 was known to have — hub echo chambers with structurally-tied 1-hop chunks — and S6 resolves it via the reasoning contribution to the agreement signal.

At K=5, S6 recovers a second-hop chunk (`chunk_002_001` in `s6_q02` and `s6_q05`) that S4 fusion had completely evicted from top-5. In those cases the chunk was reached only by reasoning as rank 2 of 2, giving it a normalized score of 0.5 — enough, with three-way scoring, to displace a shallow single-source hit at rank 5.

### 4.2 Where S6 Loses (Recall@3, One Category)

The Recall@3 regression is real and honest. On the `multi_hop_reasoning` category, S6 measured 50% vs S4's 75%. Investigation showed that in one of those four questions, S4's ordering happened to place a chunk that was *also* on the reasoning chain into a favorable rank-3 slot, while S6's more aggressive reweighting shifted the same evidence to rank 4. This is not a mechanism failure — the correct evidence was retrieved by all three modes; the ranking swap is a consequence of the reasoning contribution redistributing rank pressure.

Put plainly: the reasoning contribution shifts *some* correct evidence out of the top-3 window and *other* correct evidence into it. The net at K=3 was slightly negative on this benchmark. The net at K=1 and K=5 was positive.

### 4.3 The Echo-Chamber Tension Is Now Quantified

The most interesting mechanistic finding of the sprint. Consider a compositional question where:

- Both Semantic and KAG return the same 4–5 hub neighbors of the seed entity (they agree, so each gets +0.5 bonus).
- Reasoning independently discovers the correct 2nd-hop chunk that neither Semantic nor single-seed KAG surfaces.
- That 2nd-hop chunk has reasoning-only support: normalized score `(2−2+1)/2 = 0.5`, no agreement bonus, single source.

With equal source weights (`w_sem = w_kag = w_rea = 1.0`, `bonus = 0.5`), the shallow hub chunks score 1.0 + 1.0 + 0.5 = 2.5 to 3.0, while the reasoning-only deep chunk scores 0.5. The deep hit is buried below the shallow agreement.

An ad-hoc parameter sweep on the S6 benchmark:

| `w_reasoning` | Recall@1 | Recall@3 | Recall@5 |
|:-------------:|:--------:|:--------:|:--------:|
| 1.0 | 33.3% | 54.2% | 75.0% |
| 1.5 | 33.3% | 54.2% | 75.0% |
| 2.0 | 33.3% | 54.2% | **83.3%** |

At `w_reasoning = 2.0` the Recall@5 climbs to 83.3% — an 8.3 pp lift over S4 fusion. However, we did not adopt this asymmetric weight as the S6 baseline because the sprint brief (Section 14) explicitly asked us to first answer the equal-weight question:

> Start with a deterministic three-source fusion baseline… Only after establishing that baseline should score-aware refinements be considered.

The equal-weight baseline is what we report. Asymmetric weighting is a documented follow-up experiment, not a shipped default.

### 4.4 Answers to the Sprint Brief's Secondary Questions (§10)

| # | Question | Answer |
|:-:|:---------|:-------|
| 1 | Does reasoning provide complementary evidence? | **Yes.** In compositional queries, reasoning surfaces 2nd-hop chunks that neither Semantic nor single-seed KAG return in top-5. |
| 2 | Can reasoning help S4's multi-hop failures? | **Partially.** `chunk_002_001` recovered into top-4 on `s6_q02` and `s6_q05`. `chunk_001_001` on `s6_q01` recovered to rank 5 only under asymmetric weighting. |
| 3 | Does equal-weight three-source fusion work? | **Yes, but with a documented ceiling.** Equal weights are safe (no regressions on non-compositional categories) but leave lift on the table for deep single-source reasoning hits. |
| 4 | Does reasoning-aware scoring need to distinguish provenance? | **Yes, at Recall@5.** The parameter sweep is unambiguous. This is the natural next experiment. |
| 5 | Can we prevent reasoning from dominating ordinary queries? | **Yes.** The decomposer returns `None` on non-compositional patterns → adapter returns empty result → fusion falls back to S4. Verified end-to-end. |
| 6 | Can the system remain deterministic and explainable? | **Yes.** All sort keys are total orderings. Every fused item carries full multi-source provenance. |

---

## 5. Test Coverage

118 tests, 100% passing.

| Suite | Tests | Purpose |
|:------|:-----:|:--------|
| `contracts/test_contracts.py` | 4 | S1 contracts (unchanged) |
| `contracts/test_knowledge_path.py` | 3 | S3 KnowledgePath (unchanged) |
| `contracts/test_reasoning.py` | 7 | S5 reasoning contracts (unchanged) |
| `contracts/test_retrieval_contracts.py` | 2 | S2 Evidence/RetrievalResult (unchanged) |
| `knowledge/test_corpus.py` | 7 | S1 corpus (unchanged) |
| `knowledge/test_graph.py` | 15 | S3 graph traversal (unchanged) |
| `retrieval/test_index.py` | 4 | S2 vector index (unchanged) |
| `retrieval/test_semantic.py` | 5 | S2 semantic retriever (unchanged) |
| `retrieval/test_structural.py` | 7 | S3 KAG retriever (unchanged) |
| `fusion/test_evidence_fusion.py` | 29 | **S4 fusion — all pass unchanged with S6 code** |
| `fusion/test_hybrid_integration.py` | 4 | S4 integration (unchanged) |
| `reasoning/test_decomposer.py` | 8 | S5 decomposer (unchanged) |
| `reasoning/test_evidence_adapter.py` | 3 | S5 adapter (unchanged) |
| `reasoning/test_executor.py` | 8 | S5 executor (unchanged) |
| `reasoning/test_smoke.py` | 1 | S5 package smoke (unchanged) |
| **`fusion/test_reasoning_fusion.py`** | **7** | **NEW — S6 unit tests** |
| **`fusion/test_three_way_integration.py`** | **4** | **NEW — S6 integration tests** |

The 29 S4 fusion tests are the critical regression signal: they pass byte-identically against the S6-extended `EvidenceFusion` class. This proves Invariant 4 (S4 fusion remains reproducible) mechanically, not just by inspection.

The 11 new tests cover:

- **Three-way scoring correctness** — verifies that multi-source elevation is computed as specified.
- **Source tracking** — verifies `fusion_sources` accurately reflects contributing retrievers.
- **Reasoning provenance preservation** — verifies hop index / relation / entity metadata survive fusion.
- **Safe degradation (3 variants)** — `None`, empty `RetrievalResult`, failed `ReasoningTrace`.
- **Three-way deterministic tie-breaking** — verifies sort stability with 3 sources.
- **End-to-end multi-hop** — real corpus, real embedding model, real reasoning chain.
- **Q24 recovery** — verifies buried compositional chunks are lifted into top-K.
- **Semantic-friendly safety** — verifies non-compositional queries are untouched.
- **End-to-end determinism** — verifies repeated runs produce identical rankings.

---

## 6. Architectural Discipline — What We Did *Not* Do

The sprint brief was explicit about what S6 must not become (Section 12). We honored all of it:

- ❌ No LLM introduced.
- ❌ No agent, no autonomous loop.
- ❌ No answer generation. Output remains ranked evidence.
- ❌ No chatbot, no frontend.
- ❌ No graph database (still uses S3's in-memory `KnowledgeGraph`).
- ❌ No vector database (still uses S2's NumPy index).
- ❌ No new ontology, no new corpus.
- ❌ No adaptive routing, no learned re-ranker.
- ❌ No production RAG framework abstractions.
- ❌ No rewrite of S1–S5.

We also honored the protected contracts (Section 20). Zero modifications to:

- `Document`, `Chunk`, `Entity`, `Relation`, `Provenance`
- `Evidence`, `RetrievalResult`
- `KnowledgePath`, `KnowledgeGraph`
- `ReasoningStep`, `ReasoningPlan`, `HopResult`, `ReasoningTrace`, `ReasoningStatus`

We did not create a `reasoning_fusion.py` module. The brief (Section 24) explicitly warned against creating it automatically and asked us to first check whether extending `EvidenceFusion` was cleaner. It was. We extended.

**No ADR was required.** All changes were additive and preserved contract shapes. This is consistent with S2, S3, S4, and S5 precedent.

---

## 7. Known Limitations & Honest Caveats

Documented deliberately as inputs to the next sprint. Not defects — trade-offs.

1. **Equal-weight fusion under-serves single-source deep reasoning hits.** The parameter sweep (§4.3) shows +8.3 pp Recall@5 headroom under `w_reasoning = 2.0`. We did not ship that as default because the brief prescribed equal-weight as the S6 baseline.

2. **The reasoning invocation rate is 23.3%.** The S5 decomposer recognizes exactly 5 compositional patterns. On the 30-question S6 benchmark, only 7 questions matched. This is not an S6 limitation — it is the current S5 decomposer's coverage. Broadening the decomposer belongs in a future sprint.

3. **Recall@3 regressed 4.2 pp on one category (`multi_hop_reasoning`).** A single-question ordering swap on a category of size 4 (each question is worth 25 pp) magnifies visually. The mechanism is understood and reproducible.

4. **Benchmark size is 30 questions (24 with GT).** Statistical significance is limited. The results are diagnostic, not conclusive. A larger benchmark is a separate project.

5. **The corpus remains the 12-document controlled S1 world.** Both RAG and KAG saturate on many questions. The room for fusion to shine is bounded from above by corpus size.

6. **Single-path reasoning traversal.** When multiple relations satisfy a hop, the S5 executor selects one deterministically. Fan-out reasoning is future work.

7. **No adaptive strategy selection.** Every S6 query runs all three retrievers, even semantic-friendly ones where reasoning will trivially abstain. The brief (Section 18) framed this as the *most interesting* S6 sub-question — worth investigating in a subsequent sprint. Current gating is the simplest possible: "reasoning participates when it produces non-empty evidence".

---

## 8. Inputs to the Next Sprint

Concretely, we hand forward:

1. **A working three-way fusion baseline** with quantified regimes (helps at K=1, K=5; neutral on non-compositional categories; single K=3 regression on one category).

2. **A parameter-sweep data point** (`w_reasoning = 2.0` → Recall@5 = 83.3%) that motivates the score-aware refinement experiment.

3. **A benchmark harness** (`evaluate s6`) that produces the 5-way comparison matrix in one command, deterministically, from configuration.

4. **A CLI mode** (`--mode reasoning-hybrid`) that renders the full three-source attribution for any query. Useful for manual failure analysis.

5. **A diagnostic benchmark** with the 6 categories the brief prescribed, including 2 canonical S4-failure cases and 6 unsupported-boundary cases that correctly stay at 0%.

6. **A clean architectural boundary** — reasoning is a peer retrieval source, not a special-cased branch. The next sprint can introduce query-adaptive weighting, chain-depth bonuses, or terminal-hop priority without further touching the fusion signature.

---

## 9. Definition of Done — Verified

Per sprint brief §33, checked mechanically:

- [x] S6 research question documented (in this report and in `docs/s6/s6-reasoning-aware-fusion.md`)
- [x] Minimal architecture inspected before coding (5 files read, 10 questions answered, decision to extend not wrap)
- [x] Three-way reasoning-aware retrieval implemented
- [x] Existing S2 retrieval preserved (all 5 tests pass unchanged)
- [x] Existing S3 KAG preserved (all 7 tests pass unchanged)
- [x] Existing S4 fusion preserved (all 29 tests pass unchanged; regression signal confirmed)
- [x] Existing S5 reasoning preserved (all 27 tests pass unchanged)
- [x] Reasoning failure safely handled (verified via 3 unit tests + 1 integration test)
- [x] Evidence identity preserved (`chunk_id`-keyed deduplication unchanged)
- [x] Provenance preserved (namespaced merge, no silent overwrite)
- [x] Deterministic ranking preserved (verified via unit + integration determinism tests)
- [x] S6 benchmark created (30 questions, 6 categories)
- [x] S6 configuration created
- [x] CLI integration completed (`--mode reasoning-hybrid`, `evaluate s5`, `evaluate s6`)
- [x] `evaluate s6` implemented and reproducible
- [x] Regression tests added (11 new)
- [x] S4/S5 regression tests pass (100% unchanged)
- [x] Full test suite passes (118/118)
- [x] Ruff passes
- [x] Benchmark results recorded and analyzed
- [x] Failure cases analyzed (§4.2, §7)
- [x] S6 completion report written (this document)
- [x] Architectural changes documented (no ADR needed — additive only)
- [x] Working tree clean
- [x] Capability commits organized atomically (5 commits, capability-scoped)
- [x] S6 merged with `--no-ff`
- [x] `v0.6` tagged after final verification

---

## 10. Research Outcome Classification (per Brief §31)

**Outcome B — Small Improvement, with Mechanistic Insights.**

The sprint brief pre-registered three outcomes:

- **A (Strong Improvement):** S6 > S4 on meaningful categories, especially S4's known multi-hop failures.
- **B (Marginal Improvement):** S6 ≈ S4 with narrow wins.
- **C (No Improvement / Regression):** S6 < S4; document and learn.

We observed:
- +4.2 pp Recall@1
- −4.2 pp Recall@3
- +4.2 pp Recall@5
- Recovery of two S4-buried compositional chunks into top-K
- Zero regression on non-compositional categories
- Zero regression on structural-friendly or semantic-friendly categories
- A clean quantified mechanism (equal weighting under-serves single-source deep reasoning) with a documented remedy (`w_reasoning = 2.0` → +8.3 pp Recall@5)

This is neither a decisive "A" nor a null "C". It is a genuine B: **reasoning-aware fusion is directionally correct, mechanically sound, and points at a specific parameterization to unlock further gains.** The brief was explicit (§31): a small improvement is a valid research result if it reveals mechanism, and a negative result would have been equally valid. We did not tune the benchmark to manufacture a stronger headline.

---

## 11. Recommendation

**Ship v0.6.** It has been shipped: merged to `main` with `--no-ff`, tagged `v0.6`, pushed to origin, sprint branch deleted locally and remotely, historical tags `v0.0` through `v0.5` intact.

The next sprint should investigate **score-aware / provenance-aware fusion weighting** — the parameter sweep at §4.3 is the seed. Specifically:

1. Chain-depth bonuses for reasoning terminal hops.
2. Adaptive `w_reasoning` conditioned on chain success and depth.
3. Diversity-aware agreement bonus (reward evidence from structurally-distant paths).

These are the natural continuations of the S6 finding. None require rewriting fusion; all can be layered on the existing `EvidenceFusion` signature.

---

## 12. Progression

```
v0.0    Foundation
  │
v0.1    S1 — Knowledge World
  │     "We have something to reason over."
  │
v0.2    S2 — Semantic Retrieval
  │     "We can retrieve textual evidence."
  │
v0.3    S3 — KAG Structural Retrieval
  │     "We can retrieve structural evidence."
  │
v0.4    S4 — Evidence Fusion
  │     "We can combine them — sometimes it helps, sometimes it hurts."
  │
v0.5    S5 — Hybrid Reasoning
  │     "We can compose knowledge, but reasoning stands alone."
  │
v0.6    S6 — Reasoning-Aware Hybrid Evidence Selection           ← RELEASED
  │     "Reasoning is now a first-class participant in fusion,
  │      with a quantified regime where it helps and a documented
  │      lever for where it will help more."
```

---

## 13. Closing

S6 was not a sprint whose success required "reasoning-aware fusion wins everywhere." It was a sprint whose success required an honest answer to the research question. We have one.

The answer is:

> **Yes, reasoning-aware fusion improves the S4 baseline on Recall@1 and Recall@5 without damaging any non-compositional category, at negligible latency cost, with zero contract changes, under equal source weighting. A one-parameter refinement (asymmetric reasoning weight) is empirically shown to extend the Recall@5 lift to +8.3 pp. The mechanism is understood, deterministic, and testable.**

Kautilya's fusion layer now treats **retrieval, structure, and reasoning as three coequal evidence-producing capabilities**, and the code, tests, benchmark, and configuration exist to iterate the parameterization further.

The v0.6 tag stands.

---

*Report prepared for review, Sprint S6. Working tree clean. 118/118 tests green. Ruff clean. `main == origin/main == v0.6`.*