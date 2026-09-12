# S8 Specification — Knowledge Exploration

## 1. Context & Motivation
In sprints S1–S7, Project Kautilya built a retrieval-and-reasoning foundation:
- **S1**: Controlled Knowledge World (12 docs, 12 chunks, 15 entities, 23 relations).
- **S2**: Dense Semantic Retrieval (`all-MiniLM-L6-v2`).
- **S3**: Structural Retrieval via Knowledge Augmented Generation (KAG BFS path extraction).
- **S4**: Multi-source normalized rank fusion with agreement boosting.
- **S5**: Explicit pattern-driven symbolic reasoning chains.
- **S6**: Reasoning-aware hybrid fusion.
- **S7**: Score-aware terminal-first reasoning evidence adapter.

While S1–S7 addressed **"Which chunks are relevant to this question?"**, S8 addresses **"Can Kautilya explore the knowledge space behind a question?"**

---

## 2. Core Exploration Model
Knowledge Exploration is modeled as an inspectable sequence:
1. **Seed Discovery**: Query entities are extracted and resolved against the KnowledgeGraph.
2. **Explicit Reasoning Traversal**: If an explicit multi-hop pattern is detected by `QueryDecomposer`, `ReasoningExecutor` deterministically traverses the graph and generates a `ReasoningTrace`.
3. **Neighborhood & Structural Graph Traversal**: `KnowledgeGraph.traverse` explores connected sub-graphs from each seed entity up to bounded `max_hops`.
4. **Semantic Retrieval**: Captures global context and provides fallback coverage.
5. **Multi-Source Evidence Fusion**: `EvidenceFusion` combines semantic, structural, and reasoning evidence using normalized reciprocal ranks and agreement bonuses.
6. **Unified Exploration Representation**: Formats seeds, traversed paths, discovered evidence, reasoning trace, and status into a frozen `ExplorationResult`.

---

## 3. Contracts
### `ExplorationResult` (`kautilya.contracts.exploration`)
- `query: str`
- `objective: str`
- `seed_entities: tuple[Entity, ...]`
- `explored_paths: tuple[KnowledgePath, ...]`
- `evidence: tuple[Evidence, ...]`
- `trace: ReasoningTrace | None`
- `status: str` (`"SUCCESS"`, `"PARTIAL"`, `"UNSUPPORTED"`, `"NO_EVIDENCE"`)
- `metadata: dict[str, Any]`

---

## 4. Interfaces & CLI
- **Retrieval CLI**: `kautilya retrieve <query> --mode explore [--max-hops N] [--top-k K] [--trace path.yaml]`
- **Evaluation CLI**: `kautilya evaluate s8`
