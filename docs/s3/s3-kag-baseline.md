# S3 — KAG Structural Retrieval Baseline Specification

**Sprint:** S3 — Knowledge-Augmented Generation / Structural Retrieval
**Baseline Entry:** `v0.2`
**Target Release:** `v0.3`
**Status:** Complete

---

## 1. Executive Overview

S3 delivers Kautilya's first **structural retrieval baseline (KAG)**. It operates directly over the explicit entities and relations established in S1, providing an alternative retrieval capability to the semantic baseline delivered in S2.

Where semantic retrieval (S2) finds text chunks by high-dimensional embedding similarity, structural retrieval (S3) navigates factual connections across entities in an explicit knowledge graph, constructing multi-hop reasoning chains with verifiable provenance.

---

## 2. Core Capabilities Implemented

1. **In-Memory Knowledge Graph Index (`KnowledgeGraph`)**:
   - High-performance, side-effect-free adjacency representation built from `Corpus`.
   - Bidirectional indexing (incoming and outgoing relations).
   - Deterministic sorting of relations and entity resolution.

2. **Deterministic Entity Resolution & Span Extraction**:
   - Exact ID, name, and alias matching (case-insensitive).
   - Non-overlapping substring span consumption to prevent parent-entity collisions (e.g., distinguishing "Nova AI Division" from "Nova Systems").

3. **Bounded Graph Traversal & Connecting Path Discovery**:
   - Bounded BFS traversal up to configurable `max_hops` (default: 2).
   - Cycle prevention and deterministic traversal order.
   - Connecting-path discovery prioritized when multiple seed entities are resolved in a query.

4. **Common Retrieval Contract (`Evidence` & `RetrievalResult`)**:
   - Zero fragmentation: KAG emits the identical `Evidence` dataclass introduced in S2, labeled with `retrieval_method="structural"` and `evidence_origin="entity/relation"`.
   - `KnowledgePath` domain contract preserves structured multi-hop paths and human-readable traces.

5. **30-Question Structural Benchmark (`data/benchmarks/s3_questions.yaml`)**:
   - Covers entity lookups (4), 1-hop structural questions (8), 2-hop structural questions (8), multi-hop relational questions (6), and structural edge cases (4).

---

## 3. Architecture

```text
Question
   │
   ▼
Entity Resolution (extract_entities / resolve_entity)
   │
   ▼
KnowledgeGraph Traversal (traverse / find_paths_between)
   │
   ▼
KnowledgePath Construction
   │
   ▼
Provenance-backed Evidence Generation
   │
   ▼
RetrievalResult (method="structural")
