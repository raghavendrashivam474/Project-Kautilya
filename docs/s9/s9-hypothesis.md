---

# Project Kautilya — Sprint 9 Hypothesis
## Knowledge Resolution

**Author**: S9 Implementation (Junior Dev)
**Reviewer**: Senior Dev
**Date**: 2026-09-15
**Baseline**: v0.8 — Knowledge Exploration (commit `46ed379`)
**Branch**: `s9-knowledge-resolution`
**Status**: IN PROGRESS

---

## 1. Research Question

> Can Kautilya reliably detect and characterize competing or ambiguous
> knowledge claims discovered through its existing exploration pipeline
> without requiring a rewrite of the underlying retrieval, reasoning,
> fusion, or exploration architecture?

## 2. Hypothesis

> If the S8 ExplorationResult contains multiple evidence items and
> traversed knowledge paths with preserved provenance, then a
> deterministic post-exploration resolution layer can classify the
> discovered knowledge as CONSISTENT, AMBIGUOUS, CONFLICTING, or
> INSUFFICIENT by structurally comparing the claims implied by
> overlapping entities, relations, and evidence sources.

## 3. Rationale

S8 established that exploration produces rich structural context:
explicit seed entities, traversed knowledge paths, reasoning chains,
and per-evidence provenance traces. However, S8 stops at discovery.
It answers **"What did we find?"** but not **"How do the findings
relate to one another?"**

The existing contracts provide the raw material for resolution:

- `Evidence` items carry `chunk_id`, `document_id`, `text`,
  `score`, and `evidence_origin`
- `Relation` objects encode typed edges
  (`source_entity_id → relation_type → target_entity_id`)
  with `Provenance` back to source chunks
- `KnowledgePath` preserves the traversal chain of entities
  and relations
- `ExplorationResult` bundles all of the above into a single
  inspectable object

S9 hypothesizes that by extracting **claims** (entity-relation-entity
triples supported by specific evidence) from the ExplorationResult
and comparing them structurally, we can determine:

| Status | Meaning |
|---|---|
| CONSISTENT | Multiple evidence sources support compatible claims |
| AMBIGUOUS | Evidence admits multiple plausible interpretations |
| CONFLICTING | Evidence supports incompatible claims about the same entity/relation |
| INSUFFICIENT | Not enough evidence to make a determination |

## 4. Scope Boundaries

- S9 consumes `ExplorationResult` as-is; it does not modify S8
- S9 does not generate natural-language answers
- S9 does not use LLMs or external models
- S9 is deterministic and bounded
- S9 preserves all provenance from S1–S8

## 5. Success Criteria

- At least one controlled CONFLICTING case detected with correct
  provenance attribution
- At least one CONSISTENT case verified
- INSUFFICIENT boundary respected (no fabricated certainty)
- Determinism verified across repeated runs
- Zero regressions in S1–S8 test suite (127 tests)

## 6. Known Risks

- The current 15-entity knowledge world may not naturally contain
  enough conflicting claims; corpus augmentation may be needed
- The `ExplorationResult` may lack explicit claim-level
  representation, requiring a lightweight extraction step
- Distinguishing AMBIGUOUS from INSUFFICIENT may require
  iterative refinement

---
