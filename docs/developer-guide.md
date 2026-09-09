# Developer Onboarding & Verification Guide (v0.1)

Welcome to **Project Kautilya**. 

This guide gets you up and running with the **v0.1 Knowledge World** repository.

---

## 1. Prerequisites
Ensure you have the following installed on your machine:
* **Python**: `3.13.x`
* **uv**: Fast Python package installer and resolver.

---

## 2. Fast Setup

Clone the repository and run the setup sequence:

```bash
# Sync dependencies and build virtual environment
uv sync

# Run the test suite
uv run pytest

# Check code formatting and linting rules
uv run ruff check .
3. Verifying the Knowledge World
Run the following commands to interact with Kautilya's fictional technology ecosystem:

Step A: Summarize the Corpus
Generate a structural breakdown of all loaded documents, chunks, entities, and relationships:

Bash

uv run kautilya corpus inspect
Step B: Inspect a Specific Entity
Trace an entity's outgoing connections, incoming connections, and the source document/chunk provenance backing up those facts:

Bash

uv run kautilya corpus entity "HelixDB"
To see a person's profile and affiliations:

Bash

uv run kautilya corpus entity "Mira Sharma"
4. Directory Overview
If you are developing features, these are your entry points:

Data Sources: data/corpus/ (Raw texts + manifest), data/knowledge/ (Entities + Relations).
Data Models: src/kautilya/contracts/
Parsing / Loading: src/kautilya/ingestion/
Aggregate Root: src/kautilya/knowledge/corpus.py
Tests: tests/
