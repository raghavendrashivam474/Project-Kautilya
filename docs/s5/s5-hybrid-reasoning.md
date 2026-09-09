# S5 Specification — Deterministic Hybrid Reasoning

## 1. Overview & Objective
Sprint S5 introduces deterministic multi-hop query decomposition and graph-guided reasoning to Project Kautilya. Building upon the multi-modal evidence fusion developed in S4, S5 addresses the compositional reasoning gap: enabling the system to explicitly parse relational chains in natural language queries and traverse the knowledge graph to retrieve chained evidence with full provenance.

## 2. Core Components
- ReasoningStep: Represents a directional relational link (relation_type, Direction, hop_index).
- ReasoningPlan: Immutable sequence of reasoning steps starting from a resolved seed entity.
- HopResult: Execution outcome for an individual hop, capturing source/target entities, supporting chunk IDs, and status.
- ReasoningTrace: End-to-end execution trace recording per-hop resolution, terminal entity, and overall ReasoningStatus.
- ReasoningStatus: Explicit failure codes (SUCCESS, F1-F5).

## 3. Query Decomposer & Executor
- Decomposer: Deterministic pattern matching over compositional forms.
- Executor: Graph-guided step-by-step traversal with bounded hops (max_hops=2) and cycle prevention.
- EvidenceAdapter: Converts ReasoningTrace to Evidence and RetrievalResult objects.
