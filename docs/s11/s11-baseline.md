# S11 Baseline Execution Map

**Status:** DRAFT — placeholder created at S11 branch initialization.
**Deliverable of:** S11.1 — Baseline Mapping
**Do not edit until baseline inspection begins.**

---

## Purpose

Document how Kautilya (`v1.0`, commit `0f2d37a`) currently executes a query
end-to-end, from CLI entry to resolution, **before** any adaptive strategy
selection is introduced.

This document must answer:

1. What is the current execution flow from query → result?
2. Which capabilities are invoked, in what order?
3. What are the inputs/outputs at each boundary?
4. Where (if anywhere) does the always-on hybrid execution do work
   that may not be necessary for a given query?

No code changes should be made while producing this document,
except for read-only instrumentation if strictly required.

---

## 1. Entry point

_TBD — inspect `src/kautilya/cli/__main__.py`_

## 2. Retrieval capabilities

_TBD — inspect `src/kautilya/retrieval/semantic.py` and `structural.py`_

## 3. Reasoning

_TBD — inspect `src/kautilya/reasoning/executor.py`_

## 4. Fusion

_TBD — inspect `src/kautilya/fusion/evidence_fusion.py`_

## 5. Exploration

_TBD — inspect `src/kautilya/exploration/`_

## 6. Resolution

_TBD — inspect `src/kautilya/resolution/resolution_engine.py`_

## 7. Current execution flow (diagram)

_TBD_

## 8. Observed potentially-unnecessary work

_TBD — do NOT speculate; only fill in after inspection._

## 9. Notes for S11 design

_TBD_
