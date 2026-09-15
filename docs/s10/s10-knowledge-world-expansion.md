# Sprint 10 Technical Specification: Knowledge World Expansion

## 1. Expanded Knowledge World Architecture
The canonical knowledge world is expanded from 12 to 15 documents and 23 to 26 relations to introduce real, naturally occurring contradictions:

| Document | Entity | Relation | Conflicting Value | Baseline Value | Baseline Document |
|---|---|---|---|---|---|
| `doc_013.txt` | Nova Systems | `FOUNDED` | Mira Sharma (`ent_010`) | Rohan Kapoor (`ent_013`) | `doc_001.txt`, `doc_012.txt` |
| `doc_014.txt` | Orion Analytics | `HEADQUARTERED_IN` | Pune (`ent_051`) | Hyderabad (`ent_052`) | `doc_004.txt` |
| `doc_015.txt` | Vector Labs | `ACQUIRED` | Orion Analytics (`ent_003`) | Nova Systems (`ent_001`) | `doc_005.txt` |

## 2. Ingestion & Graph Schema
- All documents adhere to standard paragraph chunking (`chunk_013_001`, `chunk_014_001`, `chunk_015_001`).
- All relations (`rel_101`, `rel_102`, `rel_103`) maintain full bidirectional graph links and immutable provenance records.
- Deterministic relation tie-breaking in `ReasoningExecutor` ensures reproducible single-path navigation while S8 exploration discovers all competing branches.

## 3. Query-Scoped Conflict Resolution (ADR-0010)
`KnowledgeResolutionEngine` evaluates single-valued functional predicate constraints scoped to the semantic target of the query:
1. **Targeted Queries**: Predicates referenced in the question are matched; conflicts on unrelated predicates are preserved in metadata as `neighborhood_conflicts` while resolving the primary question as `CONSISTENT`.
2. **Open-Ended Queries**: Direct conflicts on the seed entity trigger `CONFLICTING`.
3. **Multi-Valued Relations**: Relations such as `LEADS`, `USES`, and `PARTNERED_WITH` are non-exclusive and do not trigger false conflicts.
