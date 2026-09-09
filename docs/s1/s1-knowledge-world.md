# S1 — The Knowledge World

## Objective
Build Kautilya's first controlled, inspectable knowledge corpus. S1 does not
implement RAG, KAG, or hybrid retrieval — it constructs the specimen those
experiments will run on.

## Domain
A fictional technology ecosystem. All entities, people, and events are
invented. This provides deterministic ground truth without licensing or
data-quality complications.

Central entities include Nova Systems, Vector Labs, Orion Analytics,
Meridian Cloud, HelixDB, and Kaveri.

## Corpus Design
- Documents live in `data/corpus/documents/` as plain UTF-8 text.
- `data/corpus/manifest.yaml` describes documents and metadata.
- `data/knowledge/entities.yaml` lists entities.
- `data/knowledge/relations.yaml` lists typed relations with provenance.

## Entity Types
Person, Company, Product, Technology, Organization, Location.

## Relation Vocabulary (controlled)
FOUNDED, CO_FOUNDED, DEVELOPED, USES, ACQUIRED, LEADS, LOCATED_IN,
HEADQUARTERED_IN, PARTNERED_WITH, WORKS_FOR.

## Provenance Model
Every relation carries a `Provenance(document_id, chunk_id)` linking it back
to the source chunk in the corpus. This is enforced by validation.

## IDs
Deterministic and stable:
- `doc_001`, `doc_002`, ...
- `chunk_<docnum>_<seq>` (e.g. `chunk_003_001`)
- `ent_001`, `ent_002`, ...
- `rel_001`, `rel_002`, ...

## Chunking
Deterministic paragraph split on blank lines. No ML, no tokenization tricks.

## Loading
```python
from kautilya.knowledge import load_corpus
corpus = load_corpus()
Inspection
text

uv run kautilya corpus inspect
uv run kautilya corpus entity HelixDB
Validation Rules
IDs unique within their kind.
Chunks reference real documents.
Relations reference real entities on both sides.
Provenance references a real document and a real chunk.
Violations raise CorpusValidationError.
Known Limitations
No cross-document coreference resolution.
Chunking is paragraph-level only.
Corpus size is deliberately small (~12 documents).
No embeddings, no graph database, no retrieval — those belong to later sprints.
Architectural Notes
Files, not databases. "Logical modularity, physical simplicity."
Contracts are frozen dataclasses to enforce immutability.
Loader is the single choke point that produces a validated Corpus.
