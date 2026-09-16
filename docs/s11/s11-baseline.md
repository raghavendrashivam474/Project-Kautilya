# S11 Baseline Execution Map

**Status:** COMPLETE — populated from v1.0 source inspection.
**Deliverable of:** S11.1 — Baseline Mapping
**Baseline commit:** `0f2d37a` (tag: v1.0)

---

## Purpose

Document how Kautilya (v1.0) currently executes a query end-to-end,
from CLI entry to resolution, **before** any adaptive strategy
selection is introduced.

---

## 1. Entry Point

**File:** `src/kautilya/cli/__main__.py`
**Function:** `_cmd_retrieve(args)`

The CLI dispatches by `--mode` flag:

| Mode               | Capabilities Invoked                              | Output              |
|--------------------|---------------------------------------------------|---------------------|
| `semantic`       | SemanticRetriever                                 | RetrievalResult     |
| `kag`            | KAGRetriever                                      | RetrievalResult     |
| `hybrid`         | Semantic + KAG + EvidenceFusion                   | RetrievalResult     |
| `reasoning`      | QueryDecomposer + ReasoningExecutor               | ReasoningTrace      |
| `reasoning-hybrid`| Semantic + KAG + Reasoning + ReasoningFusion      | RetrievalResult     |
| `explore`        | KnowledgeExplorationEngine (ALL of the above)     | ExplorationResult   |
| `resolve`        | KnowledgeExplorationEngine + KnowledgeResolutionEngine | ResolutionResult |

**Key observation:** The `explore` and `resolve` modes (used by S8–S10
benchmarks) invoke **every capability unconditionally**. This is the
"always-on hybrid" that S11 investigates.

---

## 2. Retrieval Capabilities

### 2a. Semantic Retrieval

**File:** `src/kautilya/retrieval/semantic.py`
**Class:** `SemanticRetriever`
**Signature:** `retrieve(query: str, top_k: int | None) -> RetrievalResult`

**Flow:**

> Query → EmbeddingProvider.embed_text() → VectorIndex.search() → Top-K Evidence

**Cost:** 1 query embedding + 1 vector similarity search over all chunks.

**Always succeeds:** Returns results even when no entities exist in the query.

**Frozen contract:** Returns `RetrievalResult` with `retrieval_method="semantic"`.

### 2b. Structural (KAG) Retrieval

**File:** `src/kautilya/retrieval/structural.py`
**Class:** `KAGRetriever`
**Signature:** `retrieve(query: str, top_k: int | None, max_hops: int | None) -> RetrievalResult`

**Flow:**

>Query → KnowledgeGraph.extract_entities()
```
→ (fallback) KnowledgeGraph.resolve_entity()
→ Graph traversal (neighborhood + connecting paths)
→ KnowledgePath construction
→ Evidence from relation provenance
```
**Cost:** Entity resolution + O(seeds²) connecting-path search + O(seeds × hops) neighborhood traversal.

**Can return empty:** If `extract_entities()` and `resolve_entity()` both find nothing, returns empty `RetrievalResult` with `paths_found=0`.

**Frozen contract:** Returns `RetrievalResult` with `retrieval_method="structural"`.

**S11-relevant signal:** The entity resolution step is a natural gating mechanism.
If no entities are found, KAG cannot contribute — making it a candidate for skipping.

---

## 3. Reasoning

**Files:**
- `src/kautilya/reasoning/decomposer.py` — `QueryDecomposer`
- `src/kautilya/reasoning/executor.py` — `ReasoningExecutor`

**Flow:**

> Query → QueryDecomposer.decompose() → ReasoningPlan | None
```
→ ReasoningExecutor.execute(plan) → ReasoningTrace
```

**Cost:** Plan construction (pattern matching) + per-hop graph traversal.

**Can fail gracefully:** Returns `ReasoningTrace` with status codes:
- `ENTITY_RESOLUTION_FAILURE` — seed entity not found
- `RELATION_FAILURE` — expected relation type not found
- `TRAVERSAL_FAILURE` — cycle detected or max hops exceeded
- `SUCCESS` — all hops completed

**S11-relevant signal:** The decomposer returns `None` when no reasoning
pattern is recognized. This is a strong indicator that reasoning invocation
would be wasted work.

---

## 4. Fusion

**File:** `src/kautilya/fusion/evidence_fusion.py`
**Class:** `EvidenceFusion`
**Signature:** `fuse(semantic_result, structural_result, reasoning_result=None, top_k) -> RetrievalResult`

**Algorithm:** Rank-based normalization + weighted sum + agreement bonus.
**Deterministic sort:** `(-fusion_score, -agreement, best_rank, chunk_id)`

**S11-relevant observation:** Fusion already handles `reasoning_result=None`
gracefully (S4 two-way fallback). This means S11 can safely omit reasoning
from the fusion input without modifying the fusion engine.

---

## 5. Exploration

**File:** `src/kautilya/exploration/exploration_engine.py`
**Class:** `KnowledgeExplorationEngine`
**Signature:** `explore(query: str, top_k: int | None, max_hops: int | None) -> ExplorationResult`

**This is the critical always-on hybrid path.** Internal flow:

1. graph.extract_entities(query) ← entity resolution
2. decomposer.decompose(query) ← reasoning plan construction
3. executor.execute(plan) ← reasoning execution (if plan exists)
4. structural_retriever.retrieve(query) ← KAG retrieval
5. graph.traverse(seed.id) per seed ← additional graph traversal
6. semantic_retriever.retrieve(query) ← semantic retrieval
7. fusion.fuse(sem, kag, reasoning) ← evidence fusion
8. Status assessment ← SUCCESS / PARTIAL / UNSUPPORTED / NO_EVIDENCE

**Steps 1–8 run unconditionally for every query.** This is the primary
target for S11 adaptive strategy selection.

---

## 6. Resolution

**File:** `src/kautilya/resolution/resolution_engine.py`
**Class:** `KnowledgeResolutionEngine`
**Signature:** `resolve(exploration_result: ExplorationResult) -> ResolutionResult`

**Flow:**

ExplorationResult

→ UNSUPPORTED boundary check
→ Unsupported property keyword check
→ Ambiguity detection
→ Claim extraction (from paths + reasoning trace)
→ Single-valued predicate conflict detection
→ Query-scoped predicate filtering (ADR-0010)
→ Final status: CONSISTENT | CONFLICTING | AMBIGUOUS | INSUFFICIENT | UNSUPPORTED

**Frozen contract:** Resolution operates on `ExplorationResult` and returns
`ResolutionResult`. S11 must not modify this boundary.

---

## 7. Current Execution Flow (Full Pipeline)
```text

                    Query
                      │
                      ▼
                CLI _cmd_retrieve()
                      │
          ┌───────────┼───────────────┐
          │           │               │
     mode=semantic  mode=kag    mode=explore/resolve
          │           │               │
          ▼           ▼               ▼
     SemanticRet   KAGRet      KnowledgeExplorationEngine
          │           │          │
          │           │          ├─ extract_entities()
          │           │          ├─ decompose() → plan?
          │           │          ├─ execute(plan) → trace
          │           │          ├─ KAGRetriever.retrieve()
          │           │          ├─ graph.traverse() per seed
          │           │          ├─ SemanticRetriever.retrieve()
          │           │          └─ EvidenceFusion.fuse()
          │           │               │
          │           │               ▼
          │           │         ExplorationResult
          │           │               │
          │           │               ▼ (if mode=resolve)
          │           │         KnowledgeResolutionEngine.resolve()
          │           │               │
          ▼           ▼               ▼
     RetrievalResult  RetrievalResult  ResolutionResult

```
---

## 8. Observed Potentially-Unnecessary Work

Based on source inspection (not speculation):

### 8a. Reasoning on non-compositional queries

When `QueryDecomposer.decompose()` returns `None`, the exploration
engine skips reasoning execution. However, the decomposer is still invoked
for every query. If the decomposer is cheap (pattern matching), this is
acceptable. If it becomes expensive, S11 could gate it.

### 8b. KAG retrieval on entity-free queries

When `extract_entities()` returns empty AND `resolve_entity()` returns
empty, KAG retrieval returns an empty `RetrievalResult`. The graph
traversal loop (step 5) also produces nothing. Yet both are invoked.

**Example:** A purely conceptual query like "What is machine learning?"
would trigger KAG entity resolution, find nothing, traverse nothing, and
return empty — while semantic retrieval alone would suffice.

### 8c. Semantic retrieval on pure structural queries

For a query like "Who founded Nova AI?" where KAG finds the FOUNDED_BY
relation directly with high confidence, semantic retrieval may add
redundant evidence that fusion then deduplicates. The fusion `dedup_rate`
metric captures this.

### 8d. Full exploration on simple factual lookups

The `resolve` mode runs the complete exploration pipeline (all 7 steps)
even for queries that could be answered by a single KAG hop. This is the
primary efficiency target for S11.

---

## 9. Notes for S11 Design

1. **The StrategySelector should sit above KnowledgeExplorationEngine**,
   not inside it. The exploration engine is the "always-on" orchestrator;
   S11 adds a "selective" orchestrator above it.

2. **Existing capability APIs are clean and composable.**
   `SemanticRetriever.retrieve()`, `KAGRetriever.retrieve()`,
   `EvidenceFusion.fuse()` all accept/return frozen contracts.
   No modification needed.

3. **Fusion already handles missing inputs.** `reasoning_result=None`
   is a supported S4 fallback. S11 can pass `None` for any capability
   it decides to skip.

4. **Entity resolution is the strongest routing signal.**
   `graph.extract_entities(query)` returning empty vs. non-empty
   is a deterministic, cheap, and meaningful discriminator.

5. **The decomposer is the second strongest signal.**
   `decomposer.decompose(query)` returning `None` vs. a plan
   distinguishes compositional from non-compositional queries.

6. **Resolution must receive an ExplorationResult.** S11 cannot bypass
   the exploration→resolution boundary. If S11 uses selective retrieval,
   it must still construct a valid `ExplorationResult` to feed into
   `KnowledgeResolutionEngine.resolve()`.

7. **Benchmark modes `explore` and `resolve` are the S11 targets.**
   The `semantic`, `kag`, `hybrid`, and `reasoning` modes are
   already selective by design (user chooses). S11 automates that choice.
