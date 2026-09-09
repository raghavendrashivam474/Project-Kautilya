# Project Kautilya — S3 Completion Report

**Sprint:** S3 — KAG Structural Retrieval Baseline
**Baseline Entry:** `v0.2` (S2 — Semantic Retrieval Baseline)
**Release Tag:** `v0.3`
**Status:** ✅ Complete
**Branch Lifecycle:** `sprint/s3-kag-baseline` → merged into `main` (`--no-ff`) → deleted
**Primary Deliverable:** A deterministic, provenance-backed structural retrieval engine (KAG) with in-memory graph indexing, non-overlapping entity span resolution, bounded multi-hop BFS traversal, a dedicated 30-question structural benchmark, and a unified evaluation harness — delivered without modifying any S1 or S2 contract.

---

## 1. Executive Summary

S3 established Kautilya's second retrieval capability: **structural retrieval over the explicit entity/relation graph** produced in S1. Where S2 answers questions by embedding similarity across text chunks, S3 answers them by navigating the graph itself — resolving named entities in the query, traversing bounded relational paths, and returning provenance-grounded `Evidence` compatible with the S2 retrieval contract.

The sprint answered a single, deliberately narrow research question:

> **Can explicit knowledge structure retrieve relevant evidence and multi-hop relationships that semantic retrieval alone may miss or represent poorly?**

The answer, on the current controlled corpus and a purpose-built 30-question benchmark, is: **yes — structurally, completely, and reproducibly. But the shape of KAG's failure mode is fundamentally different from RAG's, and it points directly at why fusion (S4) is the next credible step.**

Against the S3 benchmark, KAG achieved:

| Metric | Result |
|---|---|
| **Recall@1** | **60.0%** (18/30) |
| **Recall@3** | **100.0%** (30/30) |
| **Recall@5** | **100.0%** (30/30) |
| **Path Discovery** | **100.0%** (30/30) |
| **Provenance Validity** | **100.0%** (30/30) |
| **Failures** | **0** |

Every question resolved to at least one seed entity. Every question produced at least one knowledge path. Every returned Evidence item carried valid `document_id`/`chunk_id` provenance. And every question's expected chunk appeared within the top-3.

The gap between Recall@1 (60%) and Recall@3 (100%) is not a defect — it is the signature of correct structural retrieval and precisely the phenomenon S4 is designed to resolve. §7 discusses this at length.

Critically, **S2 was not disturbed**. All 22 pre-existing S1/S2 tests continue to pass unchanged. The S2 semantic retriever, its benchmark, and its CLI behavior are byte-identical to `v0.2`. S3 is a *peer* capability, not a replacement.

---

## 2. Sprint Objectives — Original vs. Delivered

The S3 brief specified capabilities across knowledge indexing, entity resolution, traversal, evidence construction, benchmark, evaluation, and CLI. All were delivered.

| # | Objective | Status |
|---|-----------|--------|
| 1 | In-memory structural knowledge index derived from S1 | ✅ Delivered |
| 2 | Deterministic entity resolution (ID, name, alias) | ✅ Delivered |
| 3 | Bounded multi-hop traversal (0/1/2-hop + configurable) | ✅ Delivered |
| 4 | `KnowledgePath` domain contract | ✅ Delivered (elevated to `contracts/`) |
| 5 | `KAGRetriever` producing S2-compatible `Evidence` | ✅ Delivered |
| 6 | 30-question structural benchmark with categorized ground truth | ✅ Delivered |
| 7 | CLI: `kautilya retrieve --mode kag` | ✅ Delivered |
| 8 | CLI: `kautilya evaluate s3` (S2 evaluation preserved) | ✅ Delivered |
| 9 | Full test coverage (unit, integration, contract, regression) | ✅ Delivered (47/47 passing) |
| 10 | Documentation (spec + completion report) | ✅ Delivered |

The sprint also honored the guardrails in the brief: **no graph database, no NetworkX, no Neo4j, no LangChain, no additional vector database, no LLM, no agent framework, no frontend, no distributed architecture, no silent modification of S1 contracts, no modification of S2 contracts, no rewriting of `SemanticRetriever`.**

---

## 3. Architecture Delivered

The structural pipeline mirrors S2's shape deliberately — same input, same output contract, different retrieval mechanism.

```
                    ┌──────────────┐
                    │   Question   │
                    └──────┬───────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Entity Extraction    │  ← non-overlapping span consumption
                │ + Resolution         │    (name / alias / ID, case-insensitive)
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ KnowledgeGraph       │  ← in-memory adjacency
                │ Bounded BFS + Path   │    (bidirectional, deterministic)
                │ Discovery            │
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ KnowledgePath        │  ← immutable domain contract
                │ Construction         │    (entities, relations, directions)
                └──────────┬───────────┘
                           │
                           ▼
                ┌──────────────────────┐
                │ Provenance-backed    │  ← same Evidence contract as S2
                │ Evidence Generation  │    method="structural"
                └──────────┬───────────┘    origin="entity/relation"
                           │
                           ▼
                    RetrievalResult
```

### 3.1 Contracts — `KnowledgePath` (new)

The single new domain contract introduced by S3 is `KnowledgePath` (`src/kautilya/contracts/knowledge_path.py`):

- Frozen dataclass, consistent with the S1/S2 immutability convention.
- Fields: `entities: tuple[Entity, ...]`, `relations: tuple[Relation, ...]`, `directions: tuple[str, ...]`.
- Convenience properties: `hops`, `document_ids`, `chunk_ids`.
- Methods: `format_path()` for human-readable string rendering (e.g. `Nova Systems --ACQUIRED--> Vector Labs --DEVELOPED--> HelixDB`), and `to_dict()` for serialization into retrieval traces.

**Architectural note:** Per §12 of the brief, `KnowledgePath` was elevated to `src/kautilya/contracts/` rather than being buried inside the retriever module. It is a first-class domain object because it will be consumed by S4 fusion logic and eventually by the reasoning layer.

### 3.2 Existing Contracts — Zero Modification

- `Entity`, `Relation`, `Provenance`, `Document`, `Chunk` — **unchanged**.
- `Evidence`, `RetrievalResult` — **unchanged**.

The S2 team had the foresight to include `retrieval_method` and `evidence_origin` fields on `Evidence` with default `"semantic"`/`"document/chunk"`. S3 simply populates them with `"structural"`/`"entity/relation"`. **No contract extension was necessary.** This is the single most important architectural finding of the sprint and is discussed in §6.

### 3.3 Knowledge Graph — `KnowledgeGraph`

`src/kautilya/knowledge/graph.py` provides the runtime structural index.

- **Construction:** `KnowledgeGraph.from_corpus(corpus)` builds `outgoing` and `incoming` adjacency dictionaries from `corpus.relations`. Relation lists are sorted by `(relation_type, target/source_entity_id, relation_id)` to guarantee deterministic traversal order.
- **Storage model:** Plain Python `dict[str, tuple[Relation, ...]]`. No NetworkX, no graph DB, no external dependencies. The S1 corpus remains the single source of truth; the graph is a derived, in-memory structure rebuilt on every load.
- **Bidirectional access:** Both `get_outgoing(entity_id)` and `get_incoming(entity_id)` are O(1).
- **Determinism:** Same corpus + same query + same config → bit-identical output ordering. Verified by tests.

### 3.4 Entity Resolution & Span Extraction

Two resolution modes coexist:

1. **`resolve_entity(query)`** — exact-match resolution for CLI-style single-term queries. Priority: entity ID → entity name (case-insensitive) → alias (case-insensitive). Returns matches sorted by ID.
2. **`extract_entities(text)`** — full-text extraction from natural-language questions. This is where the sprint's most interesting bug was found and fixed (see §5).

### 3.5 Bounded Traversal

`KnowledgeGraph.traverse(start_entity_id, max_hops)` performs a bounded BFS:

- Explores both outgoing and incoming edges — the graph is directed, but structural questions ("Who acquired X?", "Who founded X?") require the ability to reverse-traverse relations.
- Prevents cycles by tracking visited entity IDs per path.
- Emits every valid path from 0-hop (the seed entity alone) up to `max_hops`.
- Default `max_hops = 2`, configurable per call.

`find_paths_between(source_id, target_id, max_hops)` returns only paths whose terminal entity matches the target — used when the query resolves to two or more seed entities.

### 3.6 `KAGRetriever`

`src/kautilya/retrieval/structural.py` composes the graph and produces the retrieval result.

**Retrieval algorithm:**

1. **Entity resolution.** `extract_entities(query)` is attempted first; if it returns nothing, `resolve_entity(query)` is used as a fallback for degenerate single-term queries.
2. **Path collection.**
   - If ≥ 2 entities resolve, `find_paths_between()` is called for each pair to discover *connecting paths* (scored `1.0 / (1.0 + 0.1 × hops)`).
   - For every resolved entity, `traverse()` is called to discover *neighborhood paths* (scored `1.0 / (1.0 + 0.2 × hops)`, deliberately dampened relative to connecting paths).
   - Path signatures `(entity_ids, relation_ids)` deduplicate across the two collection strategies.
3. **Sorting.** Paths are sorted by `(not is_connecting, -score, hops, [entity_ids])`. Connecting paths always rank above neighborhood paths at the same score. Within each class, higher score → fewer hops → deterministic entity-ID tiebreak.
4. **Evidence construction.** The retriever iterates sorted paths, emitting one `Evidence` per unique chunk encountered in any path relation's provenance, until `top_k` is reached. Each Evidence carries:
   - `retrieval_method="structural"`
   - `evidence_origin="entity/relation"`
   - Provenance dict including `relation_id`, `relation_type`, `source_entity_id`, `target_entity_id`
   - Metadata including the formatted path (`path_formatted`) and hop count — making every evidence item traceable back to the exact structural reason it was retrieved.
5. **Result metadata.** `RetrievalResult.metadata` includes `entities_resolved`, `paths_found`, `max_hops`, `top_k`, and a serialized `paths` list. Every KAG result is fully inspectable.

### 3.7 CLI

`src/kautilya/cli/__main__.py` was extended, not rewritten:

- **`kautilya retrieve <query> [--mode semantic|kag] [--top-k N] [--max-hops N] [--trace <path>]`** — mode-dispatched. `--mode semantic` (default) preserves S2 CLI behavior identically. `--mode kag` invokes the new structural pipeline and prints resolved entities, discovered paths (with human-readable arrows), and evidence with the `via:` path that produced it.
- **`kautilya evaluate s2`** — unchanged from S2. Preserved verbatim.
- **`kautilya evaluate s3`** — new. Loads `data/benchmarks/s3_questions.yaml`, runs KAG over every question, and reports Recall@1/3/5, Path Discovery rate, Provenance Validity rate, and per-question failure detail.

S1 commands (`corpus inspect`, `corpus entity <name>`) are preserved unchanged.

---

## 4. The S3 Benchmark

Rather than reuse the S2 benchmark (where 100% recall provides no discrimination), a **purpose-built structural benchmark** was authored: `data/benchmarks/s3_questions.yaml`, 30 questions with per-question ground truth expressed as `(document_id, chunk_id)` pairs, `seed_entities`, and `expected_relations`.

### 4.1 Distribution

| Category | Count |
|----------|------:|
| Entity / relation lookup | 4 |
| 1-hop structural | 8 |
| 2-hop structural | 8 |
| Multi-hop relational | 6 |
| Structural edge cases | 4 |
| **Total** | **30** |

| Complexity | Count |
|------------|------:|
| 1-hop | 20 |
| 2-hop | 8 |
| multi-hop | 6 |
| **Total** | **34*** |

*Sum exceeds 30 because certain multi-hop questions are also labeled 2-hop in the category distribution — categorization and hop-complexity are orthogonal labels.

### 4.2 Ground-Truth Discipline

Every question was written against the actual S1 corpus content — the 15 entities, 23 relations, and 12 chunks that exist in `data/knowledge/*.yaml`. No question refers to speculative entities. This is the same discipline S2 arrived at after its own benchmark iteration and is now standard practice.

### 4.3 What the Benchmark Deliberately Does Not Do

- It does not attempt to prove KAG > RAG. Directly comparing the two systems requires a benchmark constructed to be adversarial to *both* — that is an S4 concern.
- It does not extend the S1 corpus. Per §16 of the brief, the corpus was left untouched. The 12-document world is sufficient to exercise 1-hop, 2-hop, and 3-hop structural questions.

---

## 5. Notable Bugs Found & Fixed During Implementation

Two implementation problems surfaced that are worth recording, because both are subtle and both will re-emerge in future sprints if not remembered.

### 5.1 The "Nova" Alias Bug

**Symptom:** For the query *"What product did the Nova AI Division develop?"*, KAG initially returned 5 evidence items, none of which contained the expected `chunk_009_001`. Recall@1 was stuck at ~53%.

**Root cause:** `extract_entities()` matched both:
- `ent_040` — **Nova AI Division** (entity name match)
- `ent_001` — **Nova Systems** (alias "Nova" matches the substring "Nova" inside "Nova AI Division")

Both entities passed the initial word-boundary check because "Nova" is followed by a space in the query. `ent_001` is a much higher-connectivity hub in the graph, so its neighborhood traversal flooded the top-K, pushing the actual answer (`chunk_009_001`) out of the top 5.

**Fix:** Non-overlapping span consumption. The algorithm now tracks `consumed_spans: list[tuple[int, int]]`. Because candidates are sorted longest-term-first, "Nova AI Division" consumes characters `[13, 29]` before "Nova" is even considered. When the "Nova" candidate is evaluated at position `[13, 17]`, the overlap check rejects it. Only `ent_040` is resolved. The correct chunk climbs into the top-K.

**Result:** Recall@1: 53.3% → 60.0%. Recall@3: 93.3% → 100.0%. Recall@5: 93.3% → 100.0%. Two failures eliminated.

**Lesson:** Longer-substring precedence is necessary but not sufficient. Overlap tracking is what actually enforces the "one match per span" semantic.

### 5.2 Ruff `PLC0206` on Dict Iteration

Minor. During the initial `KnowledgeGraph` implementation, sort loops were written as `for eid in out: out[eid].sort(...)`. Ruff correctly flagged this as inefficient value extraction. Rewritten as `for rel_list in out.values(): rel_list.sort(...)`. No functional impact — clean lint.

---

## 6. The Contract-Reuse Finding

This deserves its own section because it is the single most consequential architectural discovery of the sprint.

**Finding:** S3 required *zero* modification to any existing contract.

The S2 brief and implementation had already established:

```python
@dataclass(frozen=True)
class Evidence:
    ...
    retrieval_method: str = "semantic"
    evidence_origin: str = "document/chunk"
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

Those fields were not decorative. They anticipated exactly this sprint. KAG populates them with `"structural"`, `"entity/relation"`, a provenance dict containing relation metadata, and a metadata dict containing path metadata. The type is preserved. The downstream contract is preserved. Any consumer that speaks `Evidence` in S2 speaks `Evidence` in S3 without change.

This is why the S3 spec (§13, §14, §25) was insistent that contracts should be extended only if genuinely required. It turned out none were required. The architectural investment made in S2 paid off in S3.

**Implication for S4:** Fusion will not need new types either. Fusion consumes a list of `Evidence` (from either origin) and produces a fused, re-ranked list of `Evidence`. Provenance and origin are already preserved through the type. **This is the shape of a healthy contract layer.**

---

## 7. Interpreting the Recall Numbers Honestly

### 7.1 The Headline

| Metric | Result |
|---|---|
| Recall@1 | 60.0% |
| Recall@3 | 100.0% |
| Recall@5 | 100.0% |

At first glance the 60% Recall@1 looks weaker than S2's 100%. It is not. It is a *different metric on a different benchmark measuring a different retrieval mechanism*.

### 7.2 Why Recall@1 is 60% and Recall@3 is 100%

Consider `s3_q07`: *"What technology did Vector Labs develop?"*

- Only one entity resolves: Vector Labs (`ent_002`).
- Traversal from `ent_002` yields multiple 1-hop paths, including:
  - `Vector Labs --DEVELOPED--> HelixDB` (from `doc_002`, chunk_002_001) ✅
  - `Vector Labs --DEVELOPED--> HelixDB` (from `doc_003`, chunk_003_001) ✅ (duplicate relation, different provenance)
  - `Vector Labs --HEADQUARTERED_IN--> Pune` (from `doc_002`) — different relation, same starting node
  - `Vector Labs <--CO_FOUNDED-- Mira Sharma` (from `doc_002`)
  - `Vector Labs <--CO_FOUNDED-- Anand Iyer` (from `doc_002`)
  - `Vector Labs <--ACQUIRED-- Nova Systems` (from `doc_005`)

All of these are **structurally correct 1-hop facts about Vector Labs.** The graph does not know which fact the question is asking about — because the question's *semantic intent* is nowhere in the graph. It is in the natural language.

KAG's sort key ranks all 1-hop paths equally (they all have `hops=1`, all get the same neighborhood score), and then falls back to deterministic tiebreak. The correct chunk lands somewhere in positions 1–3 depending on relation-type alphabetical order. That gives us **100% Recall@3, 60% Recall@1**.

This is not a defect. This is the honest signature of pure structural retrieval on questions with lexical intent but no additional graph constraints.

### 7.3 What This Means for S2 vs. S3

| Question Style | RAG (S2) | KAG (S3) |
|---|---|---|
| Lexical, single-chunk answer | ✅ Excellent (100%) | ✅ Correct, sometimes under-ranked |
| Explicit multi-hop path | ⚠️ Works by lexical accident on current corpus | ✅ Exact path, exact provenance |
| Hub entity with many relations | ✅ Ranks by semantic similarity | ⚠️ All 1-hop facts tie structurally |
| Question with two named entities | ⚠️ Depends on chunk co-mention | ✅ Direct connecting path discovery |

**Neither retriever is universally superior on this corpus.** They are complementary. That is exactly the S4 hypothesis, and S3 has now provided the experimental scaffolding to test it.

### 7.4 What Would Change These Numbers

- **A larger corpus with disjoint documents per entity** — S2's 100% recall would begin to degrade as related facts spread across chunks with disjoint vocabulary. KAG's numbers would remain stable.
- **Multi-hop questions where the answer chunk contains no lexical overlap with the question** — S2 would fail; KAG would succeed.
- **Fusion (S4)** — semantic re-ranking of KAG's top-K would resolve the Recall@1 tie-break problem directly.

---

## 8. Test Suite Summary

| File | Tests | Purpose |
|------|------:|---------|
| `tests/contracts/test_contracts.py` | 4 | S1 contract construction (unchanged) |
| `tests/contracts/test_retrieval_contracts.py` | 2 | S2 Evidence/RetrievalResult (unchanged) |
| `tests/contracts/test_knowledge_path.py` | 3 | **New** — KnowledgePath contract |
| `tests/knowledge/test_corpus.py` | 7 | S1 corpus loading & validation (unchanged) |
| `tests/knowledge/test_graph.py` | 15 | **New** — KnowledgeGraph, resolution, span extraction, traversal |
| `tests/retrieval/test_index.py` | 4 | S2 vector index (unchanged) |
| `tests/retrieval/test_semantic.py` | 5 | S2 semantic retriever integration (unchanged) |
| `tests/retrieval/test_structural.py` | 7 | **New** — KAGRetriever integration & determinism |
| **Total** | **47** | |

- `uv run pytest -v` → **47 passed** in ~19s.
- `uv run ruff check .` → **All checks passed.**
- All 22 pre-existing S1/S2 tests unchanged and green.
- No test was deleted, disabled, or weakened.

---

## 9. Deviations from the Brief

Three deliberate deviations, all justifiable:

1. **`KnowledgePath` was implemented in the first pass, not deferred.** The brief left the decision open ("determined after inspecting the existing contracts"). Inspection made it obvious that structured paths would be needed immediately for the CLI, evaluation metadata, and eventual fusion. It was cheaper to introduce the contract properly than to inline structured path data into ad-hoc dicts and refactor later.

2. **Connecting-path priority in the sort key.** The brief specified bounded traversal and deterministic ordering; it did not specify how to *rank* paths. During implementation it became clear that when two seed entities resolve from a query (e.g. "Nova Systems and HelixDB"), the connecting path is a much stronger structural signal than either entity's neighborhood. The sort key `(not is_connecting, -score, hops, [entity_ids])` was introduced to reflect this. This is an implementation refinement, not a contract change.

3. **No ADR was created.** No S1 or S2 contract was modified. Per project convention, an ADR is only required when architecture actually changes. The additive introduction of `KnowledgePath` (new file, new type, no modification of existing types) does not qualify. This mirrors S2's reasoning for not adding an ADR.

None of these affect the definition of done.

---

## 10. Git History

S3 was implemented on `sprint/s3-kag-baseline`, branched from `v0.2`. The sprint used incremental commit discipline consistent with S1/S2:

```
[graph]       feat(s3): add structural knowledge graph index with entity resolution
[contract]    feat(s3): add KnowledgePath contract + KAGRetriever with bounded traversal
[cli+bench]   feat(s3): add S3 benchmark, CLI --mode kag, and evaluate s3 command
[fix]         fix(s3): non-overlapping span consumption in entity extraction
[docs]        docs(s3): add S3 KAG baseline specification and completion report
        ↓
merge(s3): merge sprint/s3-kag-baseline into main   [--no-ff]
        ↓
tag: v0.3 — S3 KAG Structural Retrieval Baseline
        ↓
sprint/s3-kag-baseline: deleted
```

`v0.1` and `v0.2` remain intact and untouched. `main` is clean. `v0.3` points at the merge commit.

---

## 11. Definition of Done — Checklist

### Knowledge
- [x] Existing S1 knowledge world is reused (zero data changes)
- [x] Structural index exists (`KnowledgeGraph`)
- [x] Entity resolution works (exact + span-based)
- [x] Relation traversal works (bidirectional)
- [x] Bounded multi-hop traversal works (default 2, configurable)
- [x] Traversal is deterministic (verified by test)
- [x] Provenance is preserved on every Evidence item

### Retrieval
- [x] `KAGRetriever` exists
- [x] KAG uses the existing `Evidence`/`RetrievalResult` contracts unchanged
- [x] Structural evidence is inspectable (via `metadata.paths` and `metadata.path_formatted`)
- [x] Knowledge paths are inspectable (`KnowledgePath.format_path()`, `to_dict()`)
- [x] S2 semantic retriever remains intact and byte-identical

### Benchmark
- [x] S3 benchmark exists (`data/benchmarks/s3_questions.yaml`)
- [x] Structural questions represented (16 of 30)
- [x] Multi-hop cases present (6 of 30)
- [x] Ground truth explicit (per-question `expected_evidence` + `expected_relations`)
- [x] Evaluation reproducible (deterministic, single-command)

### CLI
- [x] KAG retrieval runs manually (`uv run kautilya retrieve "<q>" --mode kag`)
- [x] S3 evaluation runs manually (`uv run kautilya evaluate s3`)
- [x] Existing S2 CLI behavior still works (`uv run kautilya evaluate s2` → 100.0%)

### Tests
- [x] Unit tests pass (graph, contracts)
- [x] Integration tests pass (KAG end-to-end)
- [x] Contract tests pass (Evidence, RetrievalResult, KnowledgePath)
- [x] S1 tests still pass (unchanged)
- [x] S2 tests still pass (unchanged)
- [x] Ruff passes (zero warnings)

### Documentation
- [x] S3 specification exists (`docs/s3/s3-kag-baseline.md`)
- [x] Post-sprint report exists (this document)
- [x] Benchmark methodology documented
- [x] Results documented
- [x] Limitations documented (§12)
- [x] No architectural changes required no ADR

### Git
- [x] Sprint branch used (`sprint/s3-kag-baseline`)
- [x] Meaningful, capability-scoped commits
- [x] Merged into `main` with `--no-ff`
- [x] Sprint branch deleted after merge
- [x] `main` clean, working tree clean
- [x] Release tagged `v0.3`
- [x] `v0.1`, `v0.2` intact

---

## 12. Known Limitations

Recorded deliberately, as inputs to S4 and beyond.

1. **Recall@1 tie-break weakness on hub entities.** When a single seed entity has multiple 1-hop relations and the question does not further constrain which relation is intended, KAG cannot distinguish them structurally. All valid facts are returned, and the correct one may not be first. Fusion (S4) is the intended remedy.

2. **Corpus is small.** 15 entities, 23 relations, 12 chunks. The graph is dense enough to exercise multi-hop traversal but too small to stress-test scale characteristics. `NumpyVectorIndex` and dict-based adjacency are both trivially adequate here; both will need re-examination if the corpus grows an order of magnitude.

3. **Entity resolution is deterministic string matching, not NLP.** Coreference ("the company", "they"), morphology ("developing", "developed"), and paraphrase ("built", "created") are not handled. Questions must reference entities by name, alias, or ID. This is per §9 of the brief and is intentional for the KAG baseline.

4. **Traversal is uniformly bounded, not intent-guided.** Every seed entity gets the same `max_hops` treatment. The retriever does not attempt to infer from the question that "founded" implies a 1-hop query while "connected through" implies multi-hop. Any such inference is fusion or reasoning territory.

5. **Scoring is structural-heuristic, not learned.** The scores `1.0 / (1.0 + 0.1 × hops)` (connecting) and `1.0 / (1.0 + 0.2 × hops)` (neighborhood) are hand-chosen decay functions. They are monotonic in hop count, deterministic, and interpretable — but they are not calibrated against any ground truth. S4 fusion will likely replace or supplement them.

6. **No question-answer generation.** S3, like S2, retrieves evidence. It does not synthesize answers. That remains explicitly out of scope until the reasoning sprint.

7. **No hybrid retrieval yet.** RAG and KAG are peers but do not currently talk to each other. That is precisely what S4 exists to build.

---

## 13. Inputs to S4 (Evidence Fusion)

S3 hands S4 the following:

1. **Two independent retrievers** with the same `Question → RetrievalResult[Evidence]` shape.
2. **A common `Evidence` contract** that already carries `retrieval_method` and `evidence_origin` — fusion can concatenate, deduplicate, and re-rank without any type gymnastics.
3. **`KnowledgePath` as a first-class contract** — fusion logic can reason about hop counts, relation types, and connecting-vs-neighborhood structure without parsing metadata dicts.
4. **Two comparable benchmarks** — S2's 30-question semantic benchmark and S3's 30-question structural benchmark. Fusion should be evaluated against *both*, and eventually against a purpose-built hybrid benchmark that exercises questions where neither retriever alone is sufficient.
5. **Empirical evidence that neither retriever dominates.** S2's 100% recall on lexically-aligned questions and S3's 60/100/100 recall pattern on structural questions together demonstrate exactly the complementarity S4 is designed to exploit.
6. **A clean CLI boundary** (`--mode semantic|kag`) that S4 can extend with `--mode hybrid`.

S4 must not modify the S2 semantic retriever, the S3 structural retriever, the corpus, or any existing contract. It is additive — a fusion layer that consumes the outputs of both.

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
v0.3    S3 — KAG Structural Retrieval Baseline      ← YOU ARE HERE
  │       "We can retrieve structural evidence."
  │
v0.4    S4 — Evidence Fusion
  │       "We can combine them."
  │
v0.5    S5 — Hybrid Reasoning
  │       "Can the combination actually help?"
  │
        Evaluation → V0 Research Result
```

---

## 15. Closing Note

S3 was a genuinely research-shaped sprint: the goal was not to build the most sophisticated graph system possible, but to build the **smallest scientifically credible structural retrieval baseline** that could be inspected, demonstrated, measured, and honestly compared against S2.

What we now have:

- A structural retriever that emits the same `Evidence` type as the semantic retriever.
- A benchmark that isolates structural retrieval capability.
- Metrics that show KAG is complete (100% Recall@3), provenance-perfect (100% valid), and structurally sound (100% path discovery) — but tie-limited at Recall@1 in exactly the way that motivates fusion.
- A test suite that guarantees this system is deterministic and that S1/S2 remain untouched.
- Documentation that records not just what was built, but *why* the numbers look the way they do.

The 100%-vs-60% headline story between S2 and S3 is not a comparison of quality. It is a comparison of *what each retriever knows*. S2 knows text. S3 knows structure. Neither knows the other's knowledge.

**S4 will teach them to.**

---

*Report generated for Project Kautilya, post-S3 milestone. Baseline `v0.3` established, tagged, and merged.*
*47/47 tests passing. Ruff clean. Working tree clean. Ready for S4.*