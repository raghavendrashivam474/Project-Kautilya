# S12 Failure Analysis & Architectural Note

**Sprint:** S12 — Adaptive Escalation & Evidence Sufficiency  
**Baseline:** `v1.1` (Commit: `e8ec060`)  
**Source Report:** `docs/s11/post_s11_report.md`  
**Source Benchmark:** `data/benchmarks/s11_questions.yaml`  

---

## 1. Executive Summary & Core S11 Trade-off

S11 introduced deterministic routing (`StrategySelector` + `AdaptiveOrchestrator`) which reduced capability invocations by **66.2%** (from 80 to 27 across 20 queries) and latency by **64.0%** (15.40 ms to 5.55 ms), maintaining 100% Recall@5.

However, resolution accuracy dropped from **60% (12/20)** in Always-On Hybrid to **55% (11/20)** in S11 Adaptive.

### Failure Mechanism Identified
```text
Always-On Hybrid:
  Semantic + Structural + Reasoning executed unconditionally
  -> Broad fusion pool (both structural graph + semantic text chunks)
  -> Conflicting / alternative claims both enter resolution
  -> Conflict / Ambiguity correctly surfaced

S11 Adaptive:
  Selector routes query to single capability (e.g. SEMANTIC or REASONING alone)
  -> Only partial evidence gathered
  -> Alternative / competing claims in the unselected capability are missed
  -> Resolution sees one-sided evidence and outputs premature CONSISTENT
```
## 2. Detailed S11 Failure Case Analysis

| Query ID | Query Text | S11 Selected Strategy | S11 Status | Always-On Status | Expected Status | Root Cause & Miss Mechanism | Detectable Post-Execution? | Potential Escalation Trigger |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **s11_q06** | "Who acquired DeepMind?" | STRUCTURAL | CONSISTENT | CONFLICTING | CONFLICTING | Structural graph had one acquisition record; semantic chunk held the conflicting/alternative acquisition claim. Single-strategy structural search never saw the semantic conflict. | Yes — Structural result returned exactly 1 claim with low evidence breadth on a known contentious entity/relation. | `claim_count == 1` when entity has multi-source traces, or query relation has competing claims in corpus. |
| **s11_q07** | "What is the relation between Project Kautilya and KAG?" | SEMANTIC | INSUFFICIENT | CONSISTENT | CONSISTENT | Semantic retriever found loose chunks but lacked graph structure to establish the direct KAG relationship. | Yes — Resolution status was directly INSUFFICIENT and evidence_count had low relation coverage. | `status == ResolutionStatus.INSUFFICIENT` |
| **s11_q08** | "Who founded Apple?" | REASONING | CONSISTENT | CONFLICTING | CONFLICTING | Reasoning executor traced one founder path (Steve Jobs) to completion and stopped. Did not explore alternative founder claims (Wozniak, Wayne). | Yes — Reasoning trace resolved a single path, but graph/semantic store contains alternative claims for target relation `founded_by`. | `claim_count == 1` on multi-claim relation, or reasoning completed with single candidate when corpus has competing candidates. |
| **s11_q09** | "Who is the CEO of Acme Corp?" | STRUCTURAL | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | Entity not present in graph or semantic corpus. Correctly identified as unsupported. | Yes (Correct Stop) — Zero evidence found across knowledge world. | None — Should STOP as UNSUPPORTED without wasting hybrid escalation. |
| **s11_q11** | "What connects Alpha and Gamma?" | REASONING | INSUFFICIENT | CONSISTENT | CONSISTENT | Multi-hop reasoning failed because intermediate hop required semantic chunk retrieval to bridge graph disconnect. | Yes — Reasoning trace incomplete (`completed == False` or status INSUFFICIENT). | `reasoning_incomplete` or intermediate hop missing. |
| **s11_q20** | "Which framework provides both graph and vector search?" | SEMANTIC | AMBIGUOUS | CONSISTENT | CONSISTENT | Semantic search returned multiple candidate matches with tied similarity; structural graph verification was needed to disambiguate. | Yes — Status was AMBIGUOUS with multiple candidate entities. | `status == ResolutionStatus.AMBIGUOUS` | 

## 3. Seven Core Architectural Answers (Brief Section 41)

### 1. What S11 actually loses

S11 loses evidence breadth. By committing to a single retrieval/reasoning capability upfront, it misses complementary evidence from uninvoked capabilities that are required to:

* Surface alternative/competing claims (conflicts)
* Bridge multi-hop gaps where graph and text complement each other
* Disambiguate tied semantic candidates

### 2. Which losses are detectable after initial execution

* Directly Detectable:
    * Status INSUFFICIENT (explicitly signals that evidence was inadequate)
    * Status AMBIGUOUS (signals candidate competition requiring structural disambiguation)
    * ReasoningTrace.completed == False (signals multi-hop reasoning stalled)
    * evidence_count == 0 on non-unsupported queries
* Heuristically Detectable without arbitrary thresholds:
    * Structural/Semantic single claim found for queries where relation exploration is incomplete.

### 3. Which observable signals can indicate insufficiency

Observable, deterministic signals (NO ML, NO LLM, NO arbitrary float confidence):

1. status == ResolutionStatus.INSUFFICIENT
2. status == ResolutionStatus.AMBIGUOUS
3. reasoning_incomplete (when ReasoningTrace.completed is False or intermediate hops unresolved)
4. zero_evidence with viable query entities (distinct from confirmed UNSUPPORTED)
5. conflict_suspected (e.g. single claim returned when relation has known alternative candidates)

### 4. Which cases should STOP

* CONSISTENT with complete reasoning / verified direct relation (e.g., direct factoid queries where 
  evidence is complete and uncontradicted).
* UNSUPPORTED (when entities are genuinely absent from the knowledge base — escalating to hybrid would 
  find nothing and waste computation).
* Queries where Initial Strategy is already HYBRID (no higher tier exists; bounded to 1 execution).

### 5. Which cases should ESCALATE

* Any initial execution resulting in INSUFFICIENT
* Any initial execution resulting in AMBIGUOUS
* Any multi-hop reasoning execution where completed is False
* Any single-capability execution where evidence coverage is partial

### 6. What existing contracts are sufficient

The following contracts from S1–S11 are already complete and provide all necessary signals:

* ResolutionResult (status, claims, conflicts, evidence, confidence)
* ReasoningTrace (hops, completed, confidence, path)
* RetrievalResult (evidence, strategy_used, metadata)
* StrategyDecision (strategy, reason, confidence)
* ExplorationResult (paths, subgraph, coverage)

### 7. Whether any architectural change appears necessary

No breaking architectural change is needed.
Existing domain models (Evidence, ResolutionResult, ReasoningTrace, RetrievalResult) remain strictly intact.

We only need to introduce:

1. An Evidence Sufficiency Contract (EvidenceAssessment / SufficiencyDecision) representing the deterministic 
   post-execution evaluation.
2. A deterministic EvidenceSufficiencyEvaluator that inspects the initial execution output.
3. An updated AdaptiveOrchestrator (or two-phase execution flow) that 
   executes Phase 1 -> Evaluates Sufficiency -> conditionally executes Phase 2 (HYBRID escalation) -> resolves final state.
4. Proposed Two-Phase Execution Flow
```text

                      +------------------------+
                      |         Query          |
                      +-----------+------------+
                                  |
                                  v
                      +------------------------+
                      |    StrategySelector    | (S11)
                      +-----------+------------+
                                  |
                                  v
                      +------------------------+
                      |    Phase 1 Execution   | (Single capability)
                      +-----------+------------+
                                  |
                                  v
                      +------------------------+
                      |  Evidence Sufficiency  | (NEW S12)
                      |       Evaluator        |
                      +-----------+------------+
                                  |
                        Is Evidence Sufficient?
                                 / \
                   SUFFICIENT   /   \   INSUFFICIENT / AMBIGUOUS / INCOMPLETE
                               /     \
                              v       v
                        +----------+ +--------------------------+
                        |   STOP   | |    Phase 2 Escalation    | (HYBRID Exploration)
                        +----+-----+ +-------------+------------+
                             |                     |
                             +----------+----------+
                                        |
                                        v
                            +------------------------+
                            | Final Resolution Result|
                            +------------------------+
```