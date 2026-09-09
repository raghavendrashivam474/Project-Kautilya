# S6 — Reasoning-Aware Evidence Selection Specification

## Sprint Purpose

Sprint S6 experimentally integrates deterministic multi-hop reasoning (introduced in S5) into the existing rank-based evidence fusion pipeline (introduced in S4).

The core objective is to determine whether **reasoning-aware evidence fusion** can outperform the two-way semantic + structural baseline without sacrificing the standalone RAG, KAG, or reasoning capabilities.

---

## 1. System Architecture
```text

                            Question
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
      Semantic (RAG)      KAG (Graph)    Reasoning (Decomp)
             │                 │                 │
             ▼                 ▼                 ▼
      RetrievalResult   RetrievalResult   RetrievalResult
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                    EvidenceFusion (3-Way)
                               │
                               ▼
                       Unified Evidence
                               │
                               ▼
                        RetrievalResult
```


### 1.1 Invariant Architecture

- **Reasoning as Evidence Producer:** Reasoning does not bypass retrieval or generate natural language answers. It produces a standard RetrievalResult carrying Evidence items with rich graph provenance.
- **Contract Preservation:** Zero modifications to Evidence, RetrievalResult, KnowledgePath, or KnowledgeGraph.
- **Additive Evolution:** EvidenceFusion.fuse() accepts 
easoning_result as an optional parameter. When None or empty, behavior is identical to S4.

---

## 2. Three-Way Fusion Algorithm

### 2.1 Rank Normalization

Each participating source  \in \{\text{semantic}, \text{structural}, \text{reasoning}\}$ normalizes candidate chunk ranks independently:

cls\text{norm\_score}(\text{rank}, k) = \frac{k - \text{rank} + 1}{k}cls

Where:
- $\text{rank}$ is the 1-indexed position in the source's retrieval list.
- $ is the total number of items returned by that source.
- Unretrieved items receive a normalized score of .0$.

### 2.2 Combined Scoring Formula

cls\text{fusion\_score} = w_{\text{sem}} \cdot \text{norm}_{\text{sem}} + w_{\text{kag}} \cdot \text{norm}_{\text{kag}} + w_{\text{rea}} \cdot \text{norm}_{\text{rea}} + \text{bonus} \cdot \mathbb{I}(\text{sources} \ge 2)cls

**Default Parameters (s6_reasoning_hybrid.yaml):**
- {\text{sem}} = 1.0$
- {\text{kag}} = 1.0$
- {\text{rea}} = 1.0$
- $\text{bonus} = 0.5$

### 2.3 Agreement Definition

An item is considered in **agreement** if it was retrieved by $\ge 2$ distinct sources out of the three.

### 2.4 Deterministic Sorting

cls\text{sort\_key} = (-\text{fusion\_score}, -\text{agreement}, \text{best\_rank}, \text{chunk\_id})cls

1. **Primary:** Descending fusion score.
2. **Secondary:** Agreement status (multi-source confirmation beats single-source).
3. **Tertiary:** Lowest best 1-indexed rank across any source.
4. **Tie-Breaker:** Lexicographical chunk_id ascending.

---

## 3. Safe Reasoning Degradation (Invariant 7)

When reasoning cannot decompose a query or fails graph traversal:
1. QueryDecomposer returns None (F1 failure) or ReasoningExecutor returns status != SUCCESS.
2. 	race_to_retrieval_result returns an empty RetrievalResult (evidence=[]).
3. EvidenceFusion detects has_reasoning = False and computes two-way fusion between Semantic and KAG.
4. Ordinary retrieval continues without exception or performance penalty.

---

## 4. CLI Interface

- kautilya retrieve <query> --mode reasoning-hybrid — Runs full three-way fusion and displays per-source attribution, agreement counts, and reasoning trace.
- kautilya evaluate s6 — Evaluates all 5 retrieval modes across the 30-question diagnostic benchmark.
- All pre-existing modes (--mode semantic, --mode kag, --mode hybrid, --mode reasoning, evaluate s2..s5) remain functional.
