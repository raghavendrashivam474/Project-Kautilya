# Sprint 10 Research Hypothesis: Natural Conflict Resolution

## Primary Research Hypothesis
If the controlled knowledge world contains deliberately authored documents that make competing factual claims about the same entity and functional relation, then the existing S8 ExplorationResult -> S9 KnowledgeResolutionEngine pipeline can naturally discover, preserve, and characterize those contradictions end-to-end without simulated claim injection.

## Secondary Hypothesis & Epistemic Boundary Condition
If natural contradictions exist across distinct entities or predicates within a shared 2-hop exploration neighborhood, naive global conflict evaluation will falsely pollute unrelated factual questions (false conflict propagation). Resolving this failure mode requires query-scoped predicate filtering (ADR-0010) that confines contradiction evaluation to relations targeted by the question.

## Core Questions
1. **Natural Surfacing**: Does S8 graph and semantic exploration retrieve competing documents and form conflicting paths without artificial hints?
2. **Deterministic Resolution**: Does S9 correctly classify single-valued predicate conflicts as `CONFLICTING` while preserving multi-valued relations (`LEADS`, `USES`) as `CONSISTENT`?
3. **Provenance Attribution**: Does the resulting `ResolutionResult` maintain inspectable, verifiable document and chunk provenance for all competing claims?
