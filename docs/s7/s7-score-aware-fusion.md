# S7 — Score-Aware Reasoning Fusion Specification

**Sprint:** S7  
**Working Title:** Score-Aware Reasoning Fusion  
**Baseline:** v0.6 (S6 Reasoning-Aware Hybrid Evidence Selection)  
**Status:** Shipped / Green  
**Research Question:** Can score/provenance-aware weighting distinguish shallow multi-source agreement from deep, reasoning-derived evidence strongly enough to improve hybrid evidence ranking over the v0.6 equal-weight baseline?

---

## 1. Executive Summary

In S6, three-way equal-weight fusion achieved **75.0% Recall@5**, but an exploratory experiment with w_reasoning = 2.0 reached **83.3% Recall@5**, revealing that equal-weight rank normalization systematically undervalued deep reasoning evidence.

S7 isolated the root cause: the S6 evidence adapter emitted hops in forward chronological order (Hop 1 → Hop 2). Because downstream rank normalization assigns rank 1 the maximum score (
orm = 1.0) and subsequent ranks lower scores, the **terminal hop** (the true compositional answer) was assigned 
orm = 0.5, while intermediate seed-adjacent hops received 
orm = 1.0.

By establishing **terminal-first reasoning evidence adaptation**, terminal-hop evidence is awarded Rank 1 (
orm = 1.0), naturally closing the performance gap. At standard equal weighting (w_reasoning = 1.0), S7 achieves **83.3% Recall@5** and elevates standalone reasoning Recall@1 from **4.2% to 20.8%** (+16.6 pp) with zero architectural complexity added.

---

## 2. Theoretical Formulation

Given a reasoning trace  = (h_1, h_2, \dots, h_m)$ consisting of $ hops:

### S6 (Chronological Hop Ordering)
cls\text{RankOrder}(T) = [h_1, h_2, \dots, h_m]cls
cls\text{norm\_rea}(h_m) = \frac{k - m + 1}{k} < \text{norm\_rea}(h_1)cls

### S7 (Terminal-First Provenance-Aware Ordering)
cls\text{RankOrder}(T) = [h_m, h_{m-1}, \dots, h_1]cls
cls\text{norm\_rea}(h_m) = \frac{k - 1 + 1}{k} = 1.0cls

The terminal answer evidence receives the highest normalized reasoning score without requiring heuristic weight inflation (w_reasoning = 2.0).

---

## 3. Invariant Guarantees

1. **S1–S5 Contracts Unaltered:** Document, Chunk, Entity, Relation, ReasoningTrace, Evidence, and RetrievalResult data models remain immutable.
2. **S4 Parity:** When reasoning is absent or empty, fusion output is bit-for-bit identical to S4.
3. **Safe Failure Degradation:** Traces with statuses F1–F5 produce empty evidence sets without propagating invalid confidence.
4. **Deterministic Ranking:** Sort order remains strictly (-fusion_score, -agreement, best_rank, chunk_id).
