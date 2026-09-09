# Project Kautilya — S2 Completion Report

**Sprint:** S2 — Semantic Retrieval Baseline
**Baseline Entry:** `v0.1` (S1 — Knowledge World)
**Release Tag:** `v0.2`
**Status:** ✅ Complete
**Branch Lifecycle:** `sprint/s2-semantic-retrieval` → merged into `main` → deleted
**Primary Deliverable:** A deterministic, reproducible semantic retrieval pipeline operating over the S1 knowledge corpus, with a benchmark, evaluation harness, and inspectable retrieval trace.

---

## 1. Executive Summary

S2 established Kautilya's first retrieval capability. Where S1 produced a validated, immutable knowledge world, S2 gave the system the ability to **look into that world and retrieve textual evidence** in response to a natural-language question.

The sprint was intentionally scoped to answer a single research question:

> **Can semantic similarity reliably retrieve relevant textual evidence from Kautilya's controlled knowledge corpus?**

The answer, as measured against a manually curated 30-question benchmark, is **yes**—for the current corpus and the current question distribution. Semantic retrieval using `all-MiniLM-L6-v2` (384-dim, cosine similarity, L2-normalized) achieved:

| Metric      | Result           |
| ----------- | ---------------- |
| Recall@1    | **100.0%** (30/30) |
| Recall@3    | **100.0%** (30/30) |
| Recall@5    | **100.0%** (30/30) |
| Failures    | 0                |

This result is significant but must be interpreted with appropriate honesty (see §7 — *Interpreting the Recall Numbers*). It does **not** mean semantic retrieval is universally sufficient; it means the S1 corpus, at its current size and topical separation, is well-suited to a strong sentence embedding. The failures we expect from semantic retrieval will re-emerge as the corpus grows and as multi-hop questions require true relational traversal—precisely the territory S3 (KAG) will address.

S2 also delivered the underlying architectural scaffolding for all future retrieval work: replaceable `EmbeddingProvider` and `VectorIndex` abstractions, a common `Evidence`/`RetrievalResult` contract designed for future fusion, and a CLI that makes the retrieval process visible and auditable.

---

## 2. Sprint Objectives — Original vs. Delivered

The S2 engineering brief specified five major deliverables. All five were completed.

| # | Objective                                       | Status    |
| - | ----------------------------------------------- | --------- |
| 1 | Question benchmark (~30 curated questions)      | ✅ Delivered |
| 2 | Embedding abstraction + one local implementation | ✅ Delivered |
| 3 | Local vector index                              | ✅ Delivered |
| 4 | Semantic retriever                              | ✅ Delivered |
| 5 | Retrieval inspection / evaluation output        | ✅ Delivered |

In addition, the sprint honored the guardrails set out in §33 of the brief: no LLM answer generation, no KAG, no hybrid retrieval, no fusion, no vector database service, no production framework, no multiple embedding providers, no rewritten S1 architecture.

---

## 3. Architecture Delivered

The retrieval pipeline follows the shape prescribed in the brief:

```
                 ┌──────────────┐
                 │   Question   │
                 └──────┬───────┘
                        │
                        ▼
               ┌─────────────────┐
               │ Embedding       │  ← replaceable abstraction
               │ Provider        │    (SentenceTransformerProvider)
               └──────┬──────────┘
                      │
                      ▼
               ┌─────────────────┐
               │ Vector Index    │  ← replaceable abstraction
               └──────┬──────────┘    (NumpyVectorIndex)
                      │
                      ▼
               ┌─────────────────┐
               │ Retriever       │  ← SemanticRetriever
               └──────┬──────────┘
                      │
                      ▼
               ┌─────────────────┐
               │ Evidence        │  ← common contract
               └─────────────────┘    (shared across future RAG/KAG/Hybrid)
```

### 3.1 Contracts (`src/kautilya/contracts/retrieval.py`)

Two immutable dataclasses were introduced:

- **`Evidence`** — a single atomic unit of retrieved evidence, carrying `chunk_id`, `document_id`, `text`, `score`, `retrieval_method`, `evidence_origin`, `provenance`, and `metadata`. Deliberately designed as a **common contract** rather than `RAGEvidence` / `KAGEvidence` / `HybridEvidence`. Origin and method flags distinguish source without fragmenting the type.
- **`RetrievalResult`** — a container preserving the query, ranked evidence list, retrieval method, and machine-readable metadata (embedding model, dimension, similarity metric, top-k, index size). Serializable via `to_dict()` for retrieval traces.

Both are `@dataclass(frozen=True)` and consistent with the S1 contract style. Existing S1 contracts (`Document`, `Chunk`, `Entity`, `Relation`, `Provenance`, `Corpus`) were **not modified**; retrieval state is kept entirely separate from corpus state per §25 of the brief.

### 3.2 Embedding Provider (`src/kautilya/infrastructure/embeddings/`)

- **`EmbeddingProvider`** — abstract base class exposing `embed_text`, `embed_texts`, `dimension`, and `model_name`. The rest of the codebase depends only on this interface.
- **`SentenceTransformerProvider`** — the single concrete implementation, using `sentence-transformers` with `all-MiniLM-L6-v2`. Chosen for its small footprint (~23 MB), 384-dim output, cosine-friendly normalization, no API dependency, and compatibility with Python 3.13.

Per §8 of the brief, **no other providers were implemented**. The abstraction exists so replacement is possible; the alternatives are not built now.

### 3.3 Vector Index (`src/kautilya/retrieval/index.py`)

- **`VectorIndex`** — abstract base class with `add(ids, vectors)` and `search(query_vector, top_k)`.
- **`NumpyVectorIndex`** — a lightweight in-process implementation using NumPy. Cosine similarity is computed as a dot product against L2-normalized vectors. Suitable for the current corpus size (12 chunks) and comfortably scalable to tens of thousands.

Again, per §11, no vector database service (FAISS, Chroma, Qdrant, Pinecone, Weaviate, Milvus) was introduced. The corpus does not require one, and the abstraction preserves the option for later.

### 3.4 Semantic Retriever (`src/kautilya/retrieval/semantic.py`)

`SemanticRetriever` composes a corpus, an embedding provider, and an optional vector index. On construction, it embeds all corpus chunks and populates the index. On `retrieve(query, top_k)`, it embeds the query, searches the index, and returns a `RetrievalResult` whose `Evidence` items carry full provenance back to the originating chunk and document.

Determinism is guaranteed by:
- Deterministic embedding under identical model configuration.
- Deterministic cosine ranking in NumPy.
- No randomness introduced anywhere in the pipeline.

### 3.5 CLI (`src/kautilya/cli/__main__.py`)

Two new commands were added alongside the preserved S1 commands:

- **`kautilya retrieve <query> [--top-k N] [--trace <path>]`** — runs semantic retrieval and prints ranked evidence, retrieval method, embedding model, and similarity metric. With `--trace`, writes a full YAML trace to disk.
- **`kautilya evaluate s2`** — loads the benchmark, runs retrieval on every question, and reports Recall@1/@3/@5 with per-question failure detail.

The S1 command surface (`kautilya corpus inspect`, `kautilya corpus entity <name>`) was preserved unchanged.

---

## 4. The Benchmark

The benchmark lives at `data/benchmarks/s2_questions.yaml` and contains **30 manually curated questions**, each carrying:

- `id`
- `question`
- `knowledge_requirement` — `semantic` | `structural` | `hybrid`
- `reasoning_complexity` — `0-hop` | `1-hop` | `2-hop` | `multi-hop`
- `expected_evidence` — one or more `(document_id, chunk_id)` pairs

### 4.1 Distribution

| Knowledge Requirement | Count |
| --------------------- | ----- |
| semantic              | 15    |
| structural            | 10    |
| hybrid                | 5     |
| **Total**             | **30** |

| Reasoning Complexity | Count |
| -------------------- | ----- |
| 0-hop                | 10    |
| 1-hop                | 12    |
| 2-hop                | 3     |
| multi-hop            | 5     |
| **Total**            | **30** |

### 4.2 Ground-Truth Alignment

The benchmark was iterated during S2 after directly inspecting all 12 chunks of the S1 corpus. Initial drafts referred to entities and technologies not present in the corpus (a legacy of speculative brief-writing), and were re-authored against actual S1 content: Nova Systems, Vector Labs, HelixDB, Orion Analytics, Kaveri, Meridian Cloud, Mira Sharma, Anand Iyer, Arjun Mehta, and Rohan Kapoor.

This iteration was necessary and worthwhile. It also produced a useful lesson recorded in §7 below: **benchmarks must be written against the actual corpus, not against the corpus one imagined**.

---

## 5. Evaluation Results

### 5.1 Headline Metrics

Executed via `uv run kautilya evaluate s2`:

```
Project Kautilya
S2 Semantic Retrieval Evaluation
==================================================

Questions : 30
Recall@1  : 100.0%
Recall@3  : 100.0%
Recall@5  : 100.0%
Failures  : 0
```

### 5.2 Breakdown by Knowledge Requirement

| Requirement | Count | Recall@1 | Recall@3 | Recall@5 |
| ----------- | ----- | -------- | -------- | -------- |
| semantic    | 15    | 100.0%   | 100.0%   | 100.0%   |
| structural  | 10    | 100.0%   | 100.0%   | 100.0%   |
| hybrid      | 5     | 100.0%   | 100.0%   | 100.0%   |

### 5.3 Breakdown by Reasoning Complexity

| Complexity | Count | Recall@1 | Recall@3 | Recall@5 |
| ---------- | ----- | -------- | -------- | -------- |
| 0-hop      | 10    | 100.0%   | 100.0%   | 100.0%   |
| 1-hop      | 12    | 100.0%   | 100.0%   | 100.0%   |
| 2-hop      | 3     | 100.0%   | 100.0%   | 100.0%   |
| multi-hop  | 5     | 100.0%   | 100.0%   | 100.0%   |

Full per-question detail is preserved in `docs/s2-semantic-retrieval.md`.

---

## 6. Testing & Quality

### 6.1 Test Suite

The final test count is **22 tests**, all passing. Coverage layers include:

- **Contract tests** (`tests/contracts/test_retrieval_contracts.py`) — Evidence immutability (`FrozenInstanceError`), RetrievalResult properties, serialization.
- **Index unit tests** (`tests/retrieval/test_index.py`) — empty index, add/search, top-k overflow, determinism.
- **Integration tests** (`tests/retrieval/test_semantic.py`) — end-to-end retrieval against the real S1 corpus with the real embedding model. Verifies contract compliance, metadata presence, descending scores, and repeatability.
- **S1 tests preserved** — All 11 pre-existing S1 tests continue to pass unchanged.

```
tests\contracts\test_contracts.py .............. 4 passed
tests\contracts\test_retrieval_contracts.py .... 2 passed
tests\knowledge\test_corpus.py ................. 7 passed
tests\retrieval\test_index.py .................. 4 passed
tests\retrieval\test_semantic.py ............... 5 passed

22 passed
```

### 6.2 Linting

`uv run ruff check .` — **All checks passed.**

### 6.3 Determinism

The `test_retrieve_deterministic` test verifies that repeated retrieval under identical configuration produces bit-identical rankings and scores.

---

## 7. Interpreting the Recall Numbers Honestly

A 100% Recall@1/3/5 headline should never be reported without context. Three points must accompany it.

**First, the corpus is small.** With 12 chunks in the index and top_k=5, the search space is unusually forgiving. Each chunk is topically distinct—one per document, each about a different entity or event—so semantic separation is high and the embedding model rarely faces genuine confusion.

**Second, the benchmark was authored against the corpus.** After the initial benchmark referred to fictional entities not present in S1, we re-authored questions to match actual chunk content. This is correct methodology (questions must have answers), but it also means the benchmark is calibrated to what the corpus already covers well. It is not adversarial. It does not probe the boundaries of what semantic retrieval fails at—because at this corpus size, those boundaries are barely visible.

**Third, semantic retrieval genuinely handled multi-hop questions here, but not for the reasons that will matter later.** When the question was *"Who acquired the company that developed HelixDB?"*, semantic retrieval succeeded because the acquisition chunk (`chunk_005_001`) literally contains the words *"Nova Systems acquired Vector Labs"* and *"HelixDB"*. The multi-hop chain was resolved by lexical proximity in a single chunk, not by traversing a relational graph. As soon as the acquisition, the technology, and the founder are described in three separate documents with no shared vocabulary, semantic retrieval will lose that ability. **KAG (S3) exists for exactly that case.**

So: the number is real, but the number is not the point. What matters is that the pipeline works, the contracts are stable, the evaluation harness is real, and we now have a baseline against which S3 and beyond can be measured.

---

## 8. Deviations from the Brief

The sprint adhered closely to the S2 brief. Three minor deviations are worth noting.

1. **Benchmark iterated during development.** The brief instructed us to author the benchmark before implementing retrieval. We did, but the first draft referenced entities not present in the S1 corpus. After running the pipeline once, we rewrote the benchmark against actual chunk content. This was the correct response but represents an ordering deviation.

2. **No ADR was created.** The brief instructed that architectural changes require an ADR. No changes to S1 contracts or architecture were needed, so no ADR was written. `ADR-001` (flat-file / in-memory corpus) remains the only ADR.

3. **CLI subcommand structure preserved from S1.** The brief showed `kautilya inspect corpus`; the actual S1 CLI uses `kautilya corpus inspect`. We preserved the S1 structure and added `kautilya retrieve` and `kautilya evaluate` as sibling top-level commands, which better fits the existing subparser design.

None of these deviations affect the deliverables or the definition of done.

---

## 9. Git History

S2 was committed atomically across seven capability-scoped commits on `sprint/s2-semantic-retrieval`, then merged into `main` with `--no-ff`, tagged as `v0.2`, and the sprint branch was deleted.

```
[1/7] feat(s2): add retrieval contracts (Evidence, RetrievalResult)
[2/7] feat(s2): add embedding provider abstraction + local implementation
[3/7] feat(s2): add vector index and semantic retriever
[4/7] feat(s2): add 30-question retrieval benchmark with ground truth
[5/7] feat(s2): add CLI commands for retrieval and evaluation
[6/7] test(s2): add retrieval unit, integration, and contract tests
[7/7] docs(s2): add semantic retrieval baseline report
       ↓
merge(s2): merge sprint/s2-semantic-retrieval into main
       ↓
tag: v0.2 — S2 Semantic Retrieval Baseline
```

Both `main` and `v0.2` were pushed to `origin`. `v0.1` remains intact and untouched.

---

## 10. Definition of Done — Checklist

### Benchmark
- [x] 30 manually curated questions exist
- [x] Questions have knowledge-requirement labels
- [x] Questions have reasoning-complexity labels
- [x] Ground-truth evidence is defined and verified against the actual corpus

### Embeddings
- [x] `EmbeddingProvider` abstraction exists
- [x] One local implementation exists (`SentenceTransformerProvider`)
- [x] Model identity recorded (`all-MiniLM-L6-v2`)
- [x] Dimension known (384)
- [x] Similarity metric explicit (cosine, L2-normalized)
- [x] Configuration reproducible (`experiments/configs/s2_semantic_retrieval.yaml`)

### Retrieval
- [x] Local vector index exists (`NumpyVectorIndex`)
- [x] Semantic retriever exists (`SemanticRetriever`)
- [x] Top-K retrieval works
- [x] Retrieval results preserve provenance
- [x] Retrieval method recorded on every Evidence item

### CLI
- [x] Human-readable retrieval command works (`kautilya retrieve`)
- [x] Retrieval trace inspectable (`--trace <path>`)
- [x] Evaluation command works (`kautilya evaluate s2`)

### Evaluation
- [x] Recall@1 implemented
- [x] Recall@3 implemented
- [x] Recall@5 implemented
- [x] Failures inspectable (per-question detail printed)

### Quality
- [x] `uv run pytest -q` passes (22/22)
- [x] `uv run ruff check .` passes

### Documentation
- [x] S2 specification/report exists (`docs/s2-semantic-retrieval.md` + this completion report)
- [x] Embedding decision documented
- [x] Retrieval architecture documented
- [x] Known limitations documented
- [x] No ADR required (no S1 contracts modified)

### Git
- [x] `v0.1` remains intact
- [x] No force-push
- [x] No rewritten S1 history
- [x] Working tree clean
- [x] S2 work merged cleanly (`--no-ff`)
- [x] `v0.2` points to the final S2 baseline
- [x] Sprint branch deleted after merge
- [x] `main` and `v0.2` pushed to `origin`

---

## 11. Known Limitations

These are documented deliberately, as inputs to future sprints.

1. **Corpus is small (12 chunks).** Retrieval quality on this benchmark is therefore not a strong claim about semantic retrieval in general. It is a claim about the retrieval pipeline being correct.
2. **Single-chunk-per-document.** All 12 documents produced exactly one chunk. This limits context and prevents evaluation of chunking strategies.
3. **No re-ranking.** The pipeline returns cosine similarity ordering unchanged.
4. **No query expansion, no HyDE, no hybrid keyword+dense.** Deliberately out of scope.
5. **No structural retrieval.** Relations exist in the S1 corpus (23 of them) but are entirely unused by S2. This is precisely what S3 (KAG) is for.
6. **No LLM.** The system retrieves evidence; it does not answer questions.
7. **Failures may re-emerge as the corpus grows.** In particular, multi-hop questions that currently succeed by lexical proximity will begin to fail as related facts are separated across documents with disjoint vocabularies.

---

## 12. Inputs to S3 (KAG Baseline)

S2 provides S3 with:

1. **A working retrieval framework** that S3's KAGRetriever can mirror in shape (`Question → Evidence`).
2. **A common `Evidence` contract** that structural retrieval can populate with `retrieval_method="structural"` and `evidence_origin="entity/relation"`—no new evidence type needed.
3. **A benchmark with `structural` and `hybrid` questions** that S2 currently handles by lexical accident. When the corpus grows, these will fail, and KAG should recover them.
4. **An evaluation harness** into which a KAG retriever can be plugged with minimal ceremony.
5. **A clean architectural boundary** (embedding provider, index, retriever) that KAG can parallel without disrupting.

S3 should not modify S2's retriever, contracts, or CLI. It should add a peer retriever and, in S4, a fusion layer that consumes both.

---

## 13. Progression

```
v0.0
Foundation
   │
   ▼
v0.1
S1 — The Knowledge World
   │
   │  "We have something to reason over."
   ▼
v0.2                      ← YOU ARE HERE
S2 — Semantic Retrieval Baseline
   │
   │  "We can retrieve textual evidence."
   ▼
S3
KAG Baseline
   │
   │  "We can retrieve structural evidence."
   ▼
S4
Evidence Fusion
   │
   │  "We can combine them."
   ▼
S5
Hybrid Reasoning
   │
   │  "Can the combination actually help?"
   ▼
Evaluation
   │
   ▼
V0 Research Result
```

---

## 14. Closing Note

S2 was a small sprint on paper: one retriever, one benchmark, one CLI addition. Its real contribution is that Kautilya now has a **discipline for retrieval** — a shape, a contract, an evaluation loop, and a baseline number. Everything S3, S4, and S5 will build must fit inside the boundaries S2 established, or must justify departing from them via ADR.

That discipline is the point.

The 100% recall is a happy artifact of a small, well-separated corpus and a strong embedding model. It should not be repeated in future reports without the same caveats attached. What will remain durable, long after that number moves, is the pipeline, the contracts, and the evaluation harness that produced it.

**Kautilya has eyes. S3 will give it structural vision.**

---

*Report generated for Project Kautilya, post-S2 milestone. Baseline `v0.2` established, pushed, and tagged.*