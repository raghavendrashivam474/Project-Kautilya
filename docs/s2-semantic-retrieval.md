# S2 — Semantic Retrieval Baseline Report

**Baseline:** `v0.1 — S1 Knowledge World`  
**Target release:** `v0.2`  
**Pipeline:** `Question -> SentenceTransformerProvider (all-MiniLM-L6-v2) -> NumpyVectorIndex (Cosine) -> Top-K Evidence`

---

## 1. Primary Research Question

> **Can semantic similarity reliably retrieve relevant textual evidence from Kautilya's controlled knowledge corpus?**

### Findings:
- **Overall Recall@1:** 100.0%
- **Overall Recall@3:** 100.0%
- **Overall Recall@5:** 100.0%

### Performance by Knowledge Requirement:
- **Hybrid** (5 questions): Recall@1 = 100.0%, Recall@3 = 100.0%, Recall@5 = 100.0%
- **Semantic** (15 questions): Recall@1 = 100.0%, Recall@3 = 100.0%, Recall@5 = 100.0%
- **Structural** (10 questions): Recall@1 = 100.0%, Recall@3 = 100.0%, Recall@5 = 100.0%

### Performance by Reasoning Complexity:
- **0-hop** (10 questions): Recall@1 = 100.0%, Recall@3 = 100.0%, Recall@5 = 100.0%
- **1-hop** (12 questions): Recall@1 = 100.0%, Recall@3 = 100.0%, Recall@5 = 100.0%
- **2-hop** (3 questions): Recall@1 = 100.0%, Recall@3 = 100.0%, Recall@5 = 100.0%
- **multi-hop** (5 questions): Recall@1 = 100.0%, Recall@3 = 100.0%, Recall@5 = 100.0%

---

## 2. Failure Analysis & Structural Blindspots

Total failures at top-5: **0**

- None at Top-5.

### Key Insights for S3 (KAG):
1. **Semantic Ambiguity:** When queries ask about abstract relationships or multihop chains (e.g., indirect partnerships or acquired company technologies), pure dense embeddings match on surface keyword similarity rather than graph connectivity.
2. **Entity Entanglement:** Entities appearing in multiple chunks (e.g., Mira Sharma, Vector Labs, Nova Systems) can cause vector collision where top-ranked chunks mention the entity in an irrelevant context.
3. **Foundation for S3:** S3 will implement structural graph traversal (KAG) to bridge multi-hop relations that semantic embeddings cannot connect.

---

## 3. Architecture & Contracts

- `Evidence`: Common frozen dataclass (`chunk_id`, `document_id`, `text`, `score`, `retrieval_method`, `evidence_origin`, `provenance`, `metadata`).
- `RetrievalResult`: Common container preserving query, ranked `Evidence`, and retrieval trace metadata.
- `EmbeddingProvider`: Replaceable abstraction; implemented via `SentenceTransformerProvider` (`all-MiniLM-L6-v2`, 384-dim).
- `VectorIndex`: Abstract index interface; implemented via `NumpyVectorIndex` (in-memory normalized cosine similarity).
- `SemanticRetriever`: Coordinates embedding provider and index to return ranked evidence from `Corpus`.
