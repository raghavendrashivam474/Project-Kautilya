---

# Project Kautilya — Sprint 7 Completion Report

**To:** Senior Development Lead
**From:** S7 Implementation Team
**Date:** 2026-09-09
**Sprint:** S7 — Score-Aware Reasoning Fusion
**Baseline:** v0.6 (`e23ec15`, `main`)
**Branch:** `sprint/s7-score-aware-reasoning-fusion`
**Outcome Classification:** **Outcome A — Strong Improvement**

---

## 1. Executive Summary

Sprint 7 investigated a specific performance anomaly surfaced during S6: equal-weight three-way fusion (semantic + structural + reasoning) achieved 75.0% Recall@5, yet a brute-force experiment inflating `w_reasoning` to 2.0 reached 83.3% Recall@5. This +8.3 percentage-point gap indicated that equal-weight rank normalization was systematically undervaluing reasoning-derived evidence, but the mechanism was unknown.

S7 isolated the root cause to a **single ordering inversion in the evidence adapter**. The S6 adapter emitted reasoning hops in chronological order (Hop 1 → Hop 2 → … → Terminal), causing downstream rank normalization to assign the terminal hop — the actual compositional answer — the *lowest* normalized score within the reasoning result set. By reversing the adapter to emit terminal-hop evidence first, rank normalization naturally awards it the maximum score (`norm = 1.0`), closing the entire performance gap at standard equal weighting (`w_reasoning = 1.0`) without any fusion-layer modifications, weight tuning, or architectural additions.

**Headline result:** Hybrid Recall@5 improved from **75.0% → 83.3%** (+8.3 pp). Standalone reasoning Recall@1 improved from **4.2% → 20.8%** (+16.6 pp). Implementation surface: one file, one logical change.

---

## 2. Research Question & Hypothesis

### Primary Research Question

> Can score/provenance-aware weighting distinguish shallow multi-source agreement from deeper reasoning-derived evidence and improve evidence ranking over the v0.6 equal-weight baseline?

### Hypothesis

Reasoning evidence contains structural information (hop depth, terminal status, chain success) that ordinary rank normalization does not capture. A small deterministic refinement to how reasoning evidence is presented to the fusion layer should improve deep multi-hop evidence ranking without harming semantic-friendly or structural-friendly queries.

### Null Hypothesis

Equal-weight three-way fusion already captures the available benefit from reasoning, and additional scoring complexity is not justified.

---

## 3. Root Cause Analysis

### 3.1 The S6 Adapter Ordering Problem

The S6 evidence adapter (`src/kautilya/reasoning/evidence_adapter.py`) iterated over `trace.hops` in natural order:

```
Hop 1 (seed-adjacent)  → emitted first  → rank 1 → norm = 1.0
Hop 2 (terminal/answer) → emitted second → rank 2 → norm = 0.5
```

For a 2-hop compositional query like *"Who founded the company that acquired Vector Labs?"*:

- **Hop 1** discovers the intermediate entity (Nova Systems acquired Vector Labs) → `chunk_005_001`
- **Hop 2** discovers the terminal answer (Rohan Kapoor founded Nova Systems) → `chunk_001_001`

Under S6 ordering, the *intermediate* evidence received `norm_rea = 1.0` while the *answer* evidence received `norm_rea = 0.5`. This is semantically backwards: the terminal hop is the information the query actually seeks.

### 3.2 Why `w_reasoning = 2.0` Masked the Problem

Inflating the reasoning weight to 2.0 partially compensated for the inverted ranking by amplifying all reasoning scores, including the underweighted terminal evidence. This was a symptom-level fix that obscured the structural cause.

### 3.3 The S7 Fix

S7 reverses the hop iteration order in the adapter:

```python
# S6: for hop in trace.hops:
# S7:
ordered_hops = sorted(trace.hops, key=lambda h: h.hop_index, reverse=True)
for hop in ordered_hops:
```

This produces:

```
Hop 2 (terminal/answer) → emitted first  → rank 1 → norm = 1.0
Hop 1 (seed-adjacent)  → emitted second → rank 2 → norm = 0.5
```

The terminal answer now receives the maximum normalized reasoning score under standard equal weighting. No fusion-layer changes required.

---

## 4. Implementation Summary

### 4.1 Files Modified

| File | Change Type | Scope |
|---|---|---|
| `src/kautilya/reasoning/evidence_adapter.py` | **Core S7 change** | Terminal-first hop ordering + `is_terminal_hop` provenance field |
| `src/kautilya/cli/__main__.py` | Feature addition | `_evaluate_s7()` function + `"s7"` CLI registration |
| `tests/reasoning/test_s7_score_aware_fusion.py` | **New file** | 4 regression tests for S7 behavior |
| `experiments/configs/s7_score_aware_fusion.yaml` | **New file** | S7 experiment configuration |
| `docs/s7/s7-score-aware-fusion.md` | **New file** | S7 specification |
| `docs/s7/post_s7_report.md` | **New file** | This report |
| 48 other files | Formatting only | Ruff auto-format (CRLF normalization, line length) |

### 4.2 Files Explicitly NOT Modified

Per the S7 brief's protected invariants:

- `src/kautilya/contracts/` — All data models unchanged
- `src/kautilya/knowledge/` — Corpus, graph, entity resolution unchanged
- `src/kautilya/retrieval/` — Semantic and structural retrievers unchanged
- `src/kautilya/fusion/evidence_fusion.py` — Fusion scoring algorithm unchanged
- `src/kautilya/reasoning/executor.py` — Graph traversal unchanged
- `src/kautilya/reasoning/decomposer.py` — Query decomposition unchanged

### 4.3 The Core Diff (Semantic)

The entire S7 behavioral change reduces to:

```diff
- for hop in trace.hops:
+ ordered_hops = sorted(trace.hops, key=lambda h: h.hop_index, reverse=True)
+ for hop in ordered_hops:
```

Plus two new provenance/metadata fields per evidence item:

```python
"is_terminal_hop": hop.hop_index == trace.plan.num_hops
```

And one new result-level metadata field:

```python
"hop_ordering": "terminal_first"
```

---

## 5. Benchmark Results

### 5.1 Aggregate Performance

Evaluation on the authoritative 30-question benchmark (`data/benchmarks/s6_questions.yaml`), 24 queries with ground truth.

| Mode | Recall@1 | Recall@3 | Recall@5 |
|---|:---:|:---:|:---:|
| Semantic (S2) | 25.0% | 54.2% | 79.2% |
| Structural KAG (S3) | 25.0% | 37.5% | 45.8% |
| S4 Hybrid Fusion | 29.2% | 58.3% | 70.8% |
| Reasoning Standalone (S6 ordering) | 4.2% | 20.8% | 20.8% |
| **Reasoning Standalone (S7 ordering)** | **20.8%** | **20.8%** | **20.8%** |
| S6 Equal-Weight Fusion | 33.3% | 54.2% | 75.0% |
| **S7 Score-Aware Fusion** | **33.3%** | **54.2%** | **83.3%** |

### 5.2 Delta Analysis

| Comparison | Δ R@1 | Δ R@3 | Δ R@5 |
|---|:---:|:---:|:---:|
| S7 Fusion vs S6 Fusion | 0.0 pp | 0.0 pp | **+8.3 pp** |
| S7 Fusion vs S4 Fusion | +4.2 pp | -4.2 pp | **+12.5 pp** |
| S7 Reasoning vs S6 Reasoning (standalone) | **+16.6 pp** | 0.0 pp | 0.0 pp |

### 5.3 Per-Category Recall@3

| Category | Semantic | KAG | S4 | S7 | n |
|---|:---:|:---:|:---:|:---:|:---:|
| `ambiguous_hub` | 66.7% | 50.0% | 66.7% | 66.7% | 6 |
| `multi_hop_reasoning` | 50.0% | 50.0% | 75.0% | 50.0% | 4 |
| `s4_failure_recovery` | 0.0% | 0.0% | 0.0% | 0.0% | 2 |
| `semantic_friendly` | 50.0% | 0.0% | 50.0% | 50.0% | 6 |
| `structural_friendly` | 66.7% | 66.7% | 66.7% | 66.7% | 6 |
| `unsupported_boundary` | — | — | — | — | 6 |

**Key observation:** No category regressed. All semantic-friendly, structural-friendly, and ambiguous-hub queries produce identical rankings to S6. The improvement is concentrated entirely in the reasoning-participating queries.

---

## 6. Query-Level Diagnostic Analysis

### 6.1 S4 Failure Recovery Queries (Previously 0% Hit@5)

**`s6_q01`** — *"Who founded the company that acquired Vector Labs?"*
- Ground truth: `chunk_001_001`
- S4: Not in top-5. S6: Not in top-5. **S7: Rank 5, score=1.0, rea_rank=1, rea_norm=1.0** ✅
- Mechanism: Terminal-hop chunk (`chunk_001_001`, Rohan Kapoor founding Nova Systems) now receives `norm_rea = 1.0` instead of `0.5`, lifting it above the cutoff.

**`s6_q02`** — *"Who co-founded the company that Nova Systems acquired?"*
- Ground truth: `chunk_002_001`
- S4: Not in top-5. S6: Not in top-5. **S7: Rank 4, score=1.7, rea_rank=1, rea_norm=1.0** ✅
- Mechanism: Same terminal-first promotion, compounded by structural agreement (`source_count=2`).

### 6.2 Multi-Hop Compositional Queries

**`s6_q05`** — *"What technology was developed by the company that Nova Systems acquired?"*
- Ground truth: `chunk_002_001`, `chunk_005_001`
- S4: Hit@5=True, Hit@1=False. **S7: Hit@5=True, Hit@1=True** ✅
- Mechanism: `chunk_005_001` (three-source agreement: semantic + structural + reasoning) promoted to rank 1 with `score=2.6`.

**`s6_q26`** — *"Who founded the company that acquired Vector Labs?"*
- Ground truth: `chunk_001_001`
- S4: Not in top-5. **S7: Rank 5, score=1.0, rea_rank=1** ✅
- Reasoning-only evidence (no semantic or structural hit) now surfaces at the boundary of top-5.

### 6.3 Non-Reasoning Queries (Safety Verification)

All 17 queries where reasoning was not invoked (empty `ReasoningResult`) produced **identical** top-5 rankings under S7 as under S6 and S4. Zero interference confirmed.

---

## 7. Regression & Invariant Verification

### 7.1 Test Suite

| Metric | S6 Baseline | S7 Current |
|---|:---:|:---:|
| Total tests | 118 | **122** |
| Passed | 118 | **122** |
| Failed | 0 | **0** |
| New S7-specific tests | — | **4** |

### 7.2 S7-Specific Test Coverage

| Test | Validates |
|---|---|
| `test_s7_terminal_first_ordering` | Terminal hop chunk emitted at rank 1 with `is_terminal_hop=True` |
| `test_s7_fusion_terminal_chunk_gets_max_norm_score` | Downstream fusion assigns `norm_rea=1.0` to terminal, `0.5` to intermediate |
| `test_s7_safe_degradation_on_failed_trace` | F2 failure trace produces empty result without invalid confidence |
| `test_s7_determinism_across_runs` | Identical chunk IDs, scores, and metadata across repeated executions |

### 7.3 Protected Invariants

- ✅ S1 contracts (`Document`, `Chunk`, `Entity`, `Relation`, `Provenance`) — unchanged
- ✅ S2 contracts (`Evidence`, `RetrievalResult`) — unchanged
- ✅ S3 contracts (`KnowledgePath`, `KnowledgeGraph`) — unchanged
- ✅ S5 contracts (`ReasoningStep`, `ReasoningPlan`, `HopResult`, `ReasoningTrace`, `ReasoningStatus`) — unchanged
- ✅ S4 backward compatibility — `reasoning_result=None` produces identical output
- ✅ Deterministic total ordering — `(-fusion_score, -agreement, best_rank, chunk_id)` preserved
- ✅ No stochastic components introduced
- ✅ No external dependencies added

### 7.4 Code Hygiene

- ✅ `ruff check .` — All checks passed
- ✅ `ruff format --check .` — 71 files already formatted

---

## 8. Latency Analysis

| Pipeline Stage | S6 (ms) | S7 (ms) | Δ |
|---|:---:|:---:|:---:|
| Semantic retrieval | 17.81 | 14.09 | -3.72 (variance) |
| Structural KAG | 0.25 | 0.20 | -0.05 |
| Reasoning execution | 0.56 | 0.47 | -0.09 |
| Fusion | 0.16 | 0.13 | -0.03 |
| **Total hybrid pipeline** | **18.78** | **14.89** | **-3.89** |

Latency differences are within normal measurement variance for local embedding inference. The S7 adapter change (a single `sorted()` call over 2 elements) adds negligible overhead. No performance regression.

---

## 9. Architectural Impact Assessment

### 9.1 Complexity Budget

| Metric | S6 | S7 | Δ |
|---|:---:|:---:|:---:|
| New classes | — | **0** | 0 |
| New modules | — | **0** | 0 |
| New dependencies | — | **0** | 0 |
| Modified source files (behavioral) | — | **1** | 1 |
| Lines of behavioral change | — | **~5** | ~5 |
| New configuration surface | — | **0** | 0 |

### 9.2 Architectural Decision Record

No ADR was required. The change is a local implementation refinement within the existing adapter boundary that preserves all contracts, interfaces, and data flow topology. The fusion layer, retrieval layer, knowledge layer, and reasoning executor are entirely unaware of the change.

### 9.3 Why This Approach Over Alternatives

| Alternative Considered | Rejected Because |
|---|---|
| Increase `w_reasoning` to 2.0 globally | Symptom-level fix; no mechanistic explanation; brittle across corpora |
| Add depth-based scoring multiplier in fusion | Unnecessary complexity; the signal already exists in the adapter output |
| Add a `ReasoningScorer` class between adapter and fusion | Violates controlled hybridism; adds abstraction without evidence |
| Modify rank normalization formula | Would affect semantic and structural evidence; too broad |
| Add terminal-hop bonus in fusion | Requires new fusion parameters; the adapter ordering fix is simpler and more principled |

---

## 10. Limitations & Open Questions

1. **Corpus scale:** The current corpus (12 documents, 12 chunks, 15 entities) is small. The terminal-first ordering benefit may behave differently at scale where reasoning traces produce 5+ hops and dozens of chunks. This should be validated when the corpus expands.

2. **Multi-hop depth > 2:** All current reasoning traces are exactly 2 hops. For 3+ hop traces, the intermediate hops will be ordered between terminal and seed. Whether this intermediate ordering is optimal is an open question for future sprints.

3. **`s4_failure_recovery` Recall@3 remains 0%:** While S7 recovered Hit@5 on both failure-recovery queries, Recall@3 remains 0%. The ground-truth chunks are surfacing at ranks 4–5, just outside the top-3 window. This may require either a larger top-k or improved semantic retrieval for these compositional patterns.

4. **`multi_hop_reasoning` Recall@3 dropped from 75% (S4) to 50% (S7):** This is inherited from S6 and is not a regression introduced by S7. The S4 advantage on this category was driven by agreement bonuses on shallow hub evidence that S6/S7 reasoning correctly deprioritizes. Whether this represents a genuine quality trade-off or a benchmark artifact requires further investigation.

5. **Reasoning invocation rate is low (23.3%):** Only 7 of 30 questions trigger reasoning decomposition. Expanding the decomposer's pattern coverage would increase the surface area where S7's terminal-first ordering can contribute.

---

## 11. Outcome Classification

**Outcome A — Strong Improvement** ✅

S7 materially improved hybrid Recall@5 (+8.3 pp) and standalone reasoning Recall@1 (+16.6 pp) with no regression in any category, no architectural complexity, and a clear mechanistic explanation. The improvement is achieved through a single principled change that corrects a semantic inversion in the adapter layer.

The null hypothesis (that equal-weight fusion already captures the available benefit) is **rejected**. The S6 performance gap was real, and its cause was structural rather than parametric.

---

## 12. Recommendations for S8

Based on the S7 findings, the following directions are suggested for S8 consideration:

1. **Expand decomposer pattern coverage** to increase reasoning invocation rate beyond 23.3%. The current 5 patterns (A–E) cover only a fraction of compositional query structures.

2. **Investigate the `multi_hop_reasoning` Recall@3 gap** between S4 (75%) and S6/S7 (50%). Determine whether this is a benchmark artifact or a genuine trade-off requiring a more nuanced agreement-vs-depth weighting scheme.

3. **Validate terminal-first ordering at scale** with a larger corpus and deeper reasoning traces (3+ hops).

4. **Consider corpus expansion** to stress-test the fusion layer under more realistic evidence density conditions.

---

## 13. Definition of Done Checklist

- [x] S7 research question documented
- [x] v0.6 baseline reproduced (33.3 / 54.2 / 75.0)
- [x] Minimal architecture inspected (adapter, fusion, executor, contracts)
- [x] S6 behavior preserved (all 118 original tests pass)
- [x] Candidate weighting implemented (terminal-first ordering)
- [x] Deterministic behavior preserved (sort key unchanged)
- [x] Reasoning failure degradation preserved (F1–F5 → empty result)
- [x] Provenance preserved and enhanced (`is_terminal_hop` field)
- [x] S1–S6 tests pass (118/118)
- [x] S7 tests added (4 new, 122/122 total)
- [x] Benchmark executed (`uv run kautilya evaluate s7`)
- [x] S6 vs S7 comparison recorded
- [x] Per-category results recorded
- [x] Latency measured
- [x] Rank changes analyzed (query-level diagnostics)
- [x] Limitations documented
- [x] Research outcome classified: **Outcome A**
- [x] No architectural changes requiring ADR
- [x] Ruff clean
- [x] Full test suite green (122/122)
- [x] Working tree ready for commit
- [x] Completion report written

---

**Prepared for review and merge to `main` as v0.7.**