# Kautilya System Architecture — v0.1

This document outlines the architectural boundaries and design patterns established as of **v0.1**.

## Core Architectural Principle: Logical Modularity, Physical Simplicity

Kautilya maintains a clean directory structure where physical layout directly matches logical domain boundaries. 
src/kautilya/
├── contracts/ # Pure, side-effect-free domain models (Dataclasses)
├── ingestion/ # Extraction, parsing, and chunking boundaries
├── knowledge/ # Aggregation, validation, and in-memory representation
└── cli/ # Presentation and user inspection commands

text


---

## 1. Domain Contracts (`kautilya.contracts`)
Contracts are the formal type definitions used throughout the system. 
To ensure thread-safety and prevent accidental side-effects during retrieval experiments, **all domain contracts are frozen (immutable) dataclasses**.

* **`Document`**: Represents a raw, unstructured source text file along with its metadata.
* **`Chunk`**: A deterministic segment of a `Document`.
* **`Entity`**: A named node in our structural knowledge graph.
* **`Relation`**: A directed, typed link connecting two entities.
* **`Provenance`**: The core grounding contract. Every `Relation` must contain a `Provenance` block specifying the `document_id` and `chunk_id` where this factual relationship was extracted.

---

## 2. Ingestion Namespace (`kautilya.ingestion`)
Responsible for reading raw assets and transforming them into domain contracts.
* **`chunker.py`**: Splits documents into sequential `Chunk` objects. S1 implements a deterministic, paragraph-level chunker (splitting on blank lines `\n\n`).
* **`corpus_loader.py`**: Reads `manifest.yaml` and raw text documents to build the unstructured document list.

---

## 3. Knowledge Namespace (`kautilya.knowledge`)
The core knowledge representation engine.
* **`corpus.py`**: Houses the **`Corpus`** aggregate root. The `Corpus` is a validated, read-only compound object that loads and indexes all documents, chunks, entities, and relations.
* **Lookups**: Provides O(1) or O(N) in-memory lookups (`corpus.entity()`, `corpus.relations_for()`) to simulate database queries.
* **`validate_corpus`**: A strict compiler-like validator that runs immediately upon loading. It checks:
  1. Unique identifiers across all collections.
  2. Dangling references (e.g., relation pointing to a non-existent entity).
  3. Provenance accuracy (e.g., relation referencing an invalid chunk or document).

---

## 4. CLI Presentation Layer (`kautilya.cli`)
A text-only CLI designed to provide human inspectability. 
* Command structure: `kautilya corpus [inspect | entity <name/id>]`
* Relies exclusively on `load_corpus()` from the knowledge namespace.
