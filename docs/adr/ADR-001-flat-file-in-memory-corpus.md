# ADR-001: Flat-File, In-Memory Knowledge Representation

## Status
Accepted

## Context
Kautilya is designed to study the performance of RAG, KAG, and hybrid retrieval. To perform scientific comparisons, we need a controlled knowledge corpus containing:
1. Unstructured documents (for RAG).
2. Segmented, sequential text chunks (for RAG).
3. Structured entities and typed relations (for KAG).
4. Unambiguous provenance linking entities and relations back to their source chunks.

At this stage, introducing production-grade database systems (e.g., PostgreSQL, Neo4j, Chroma, Milvus) or complex ORMs/OGMs would introduce significant operational overhead, non-deterministic behaviors, and configuration complexity. This would violate Kautilya's core design principle: **logical modularity, physical simplicity**.

## Decision
For S1 and early retrieval experiments, we will represent the knowledge world using flat, human-readable files:
* Source documents as `.txt` files.
* A central manifest (`manifest.yaml`) describing documents and their metadata.
* Entities (`entities.yaml`) and typed relationships (`relations.yaml`) described using structured YAML format.

This raw data is parsed at runtime into immutable, type-safe Python dataclasses (`Document`, `Chunk`, `Entity`, `Relation`, `Provenance`) and compiled into a single validated aggregate root (`Corpus`). All relationships and lookups are evaluated in-memory using pure Python.

## Alternatives Considered
1. **Neo4j + Vector Database (Chroma/pgvector)**:
   * *Pros*: Closer to a production-grade deployment.
   * *Cons*: Adds non-trivial startup latency, local container dependencies, network socket operations in tests, and non-deterministic indexing. Unnecessary for a 12-document laboratory specimen.
2. **SQLite + NetworkX**:
   * *Pros*: Out-of-the-box relational structure and graph query algorithms.
   * *Cons*: Adds secondary storage schema complexity. Flat YAML files are easier to inspect directly in Git diffs, allowing deterministic verification of the corpus.

## Rationale
Using raw YAML and text files loaded into frozen dataclasses provides:
* **Zero-dependency setup**: Developers only need Python and `uv`.
* **Instantaneous testing**: The entire test suite executes in milliseconds.
* **100% Determinism**: No indexing delays, connection timeouts, or database state leakage between test runs.
* **Perfect Version Control**: Changes to the corpus, entities, or relationships are explicitly trackable via standard Git diffs.

## Consequences
* **What becomes easier**: Writing unit tests, verifying integrity rules, modifying entities/relations, and tracking experimental ground truth.
* **What becomes harder**: Multi-hop graph queries (which must be written as in-memory Python lookups rather than Cypher/SQL queries) and scaling the corpus to millions of nodes (which is explicitly out-of-scope for this laboratory scale).

## Reversibility
Highly reversible. Because the external interaction with the corpus is abstracted behind the `Corpus` aggregate root and standard interfaces in `kautilya.contracts`, we can swap the internal storage backend to a database later without changing the retrieval or evaluation contracts.
