# ADR 0010: Query-Scoped Conflict Resolution

## Status
Accepted

## Context
In Sprint 9, `KnowledgeResolutionEngine` performed conflict detection by finding all pairs of conflicting single-valued predicate claims across the entire `ExplorationResult` neighborhood. In S9, this worked because synthetic conflicts were injected on a per-query basis in an otherwise uniform corpus.

In Sprint 10, when real natural conflicts are added directly into the corpus (e.g., `Orion Analytics` has conflicting `HEADQUARTERED_IN` records in Pune vs Hyderabad, but a consistent `FOUNDED` record with Arjun Mehta), a query asking `"Who founded Orion Analytics?"` retrieves the full 2-hop neighborhood. The S9 resolution engine flagged the question as `CONFLICTING` because it observed the headquarters conflict in the neighborhood, even though the question asked exclusively about the founder.

## Decision
Extend `KnowledgeResolutionEngine` with deterministic query-predicate scoping:
1. When a query targets specific semantic predicates (derived from query terms or reasoning traces), conflict resolution evaluates whether the *query-targeted predicate* contains contradictory claims.
2. If the targeted predicate is consistent, the status is `CONSISTENT` (while any incidental neighborhood conflicts can be preserved in metadata).
3. If the query is an open-ended exploration query without a specific predicate constraint, any direct conflict on the seed entity triggers `CONFLICTING`.

## Consequences
### Positive
- Eliminates false conflict propagation across unrelated properties of the same entity.
- Allows natural contradictions to exist in the corpus without polluting unrelated factual queries.
- Preserves 100% backward compatibility with S1–S9 deterministic guarantees.

### Negative / Trade-offs
- Requires deterministic mapping between query predicate keywords and structural relation types.
