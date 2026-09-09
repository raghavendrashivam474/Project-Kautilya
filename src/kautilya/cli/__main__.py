"""Project Kautilya — CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def _get_project_root() -> Path:
    """Resolve project root directory robustly."""
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parents[3],
        Path(__file__).resolve().parents[2],
    ]
    for c in candidates:
        if (c / "data" / "corpus").exists():
            return c
    return Path.cwd()


def _load_corpus():
    """Load the S1 corpus from the default data directory locations."""
    from kautilya.knowledge.corpus import load_corpus

    root = _get_project_root()
    corpus_dir = root / "data" / "corpus"
    knowledge_dir = root / "data" / "knowledge"

    return load_corpus(corpus_dir=corpus_dir, knowledge_dir=knowledge_dir)


# ── S1 commands (preserved) ─────────────────────────────────────

def _cmd_corpus_inspect(args: argparse.Namespace) -> None:
    corpus = _load_corpus()
    docs = list(corpus.documents)
    chunks = list(corpus.chunks)
    entities = list(corpus.entities)
    relations = list(corpus.relations)
    print("Project Kautilya — Corpus Inspection")
    print("=" * 40)
    print(f"Documents : {len(docs)}")
    print(f"Chunks    : {len(chunks)}")
    print(f"Entities  : {len(entities)}")
    print(f"Relations : {len(relations)}")


def _cmd_corpus_entity(args: argparse.Namespace) -> None:
    corpus = _load_corpus()
    name = args.name
    for entity in corpus.entities:
        if entity.name.lower() == name.lower():
            print(f"Entity: {entity.name}")
            print(f"Type:   {entity.entity_type}")
            return
    print(f"Entity '{name}' not found.")


# ── S2 commands ─────────────────────────────────────────────────

def _build_retriever(top_k: int = 5):
    """Build a SemanticRetriever from the corpus and config."""
    from kautilya.infrastructure.embeddings import SentenceTransformerProvider
    from kautilya.retrieval.semantic import SemanticRetriever

    root = _get_project_root()
    config_path = root / "experiments" / "configs" / "s2_semantic_retrieval.yaml"

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        model_name = config.get("embedding", {}).get(
            "model", "all-MiniLM-L6-v2"
        )
        top_k = config.get("retrieval", {}).get("top_k", top_k)
    else:
        model_name = "all-MiniLM-L6-v2"

    print(f"Loading embedding model: {model_name} ...")
    provider = SentenceTransformerProvider(model_name)
    print(f"  dimension: {provider.dimension}")

    corpus = _load_corpus()
    print(f"Building index over {len(list(corpus.chunks))} chunks ...")
    retriever = SemanticRetriever(
        corpus=corpus,
        embedding_provider=provider,
        top_k=top_k,
    )
    return retriever


def _cmd_retrieve(args: argparse.Namespace) -> None:
    retriever = _build_retriever(top_k=args.top_k)
    result = retriever.retrieve(args.query, top_k=args.top_k)

    print()
    print("Project Kautilya")
    print("Semantic Retrieval")
    print("=" * 50)
    print(f"\nQuery:\n  {result.query}\n")
    print("Results:\n")

    for i, ev in enumerate(result.evidence, 1):
        print(f"  [{i}] score={ev.score:.4f}")
        print(f"      {ev.document_id} / {ev.chunk_id}")
        text_preview = ev.text[:120].replace("\n", " ")
        print(f"      {text_preview}...")
        print()

    print(f"Retrieval method: {result.retrieval_method}")
    print(f"Evidence origin:  {result.evidence[0].evidence_origin if result.evidence else 'N/A'}")
    print(f"Embedding model:  {result.metadata.get('embedding_model', 'N/A')}")
    print(f"Similarity:       {result.metadata.get('similarity_metric', 'N/A')}")

    # Write trace if requested
    if args.trace:
        trace_path = Path(args.trace)
        with open(trace_path, "w", encoding="utf-8") as f:
            yaml.dump(result.to_dict(), f, default_flow_style=False)
        print(f"\nTrace written to: {trace_path}")


def _cmd_evaluate(args: argparse.Namespace) -> None:
    sprint = args.sprint
    if sprint != "s2":
        print(f"Unknown sprint: {sprint}. Only 's2' is supported.")
        sys.exit(1)

    root = _get_project_root()
    benchmark_path = root / "data" / "benchmarks" / "s2_questions.yaml"

    if not benchmark_path.exists():
        print(f"Benchmark not found: {benchmark_path}")
        sys.exit(1)

    with open(benchmark_path, encoding="utf-8") as f:
        benchmark = yaml.safe_load(f) or {}

    questions = benchmark.get("questions", [])
    print(f"\nLoading benchmark: {len(questions)} questions")

    retriever = _build_retriever(top_k=5)

    recall_at = {1: 0, 3: 0, 5: 0}
    failures = []

    for q in questions:
        qid = q["id"]
        question = q["question"]
        expected = {e["chunk_id"] for e in q.get("expected_evidence", [])}

        result = retriever.retrieve(question, top_k=5)
        retrieved_ids = result.top_chunk_ids

        for k in recall_at:
            if expected & set(retrieved_ids[:k]):
                recall_at[k] += 1

        if not (expected & set(retrieved_ids)):
            failures.append(
                {
                    "id": qid,
                    "question": question,
                    "expected": sorted(expected),
                    "retrieved": retrieved_ids,
                    "requirement": q.get("knowledge_requirement", "?"),
                    "complexity": q.get("reasoning_complexity", "?"),
                }
            )

    total = len(questions)
    print()
    print("Project Kautilya")
    print("S2 Semantic Retrieval Evaluation")
    print("=" * 50)
    print(f"\nQuestions : {total}")
    print(f"Recall@1  : {recall_at[1] / total * 100:.1f}%")
    print(f"Recall@3  : {recall_at[3] / total * 100:.1f}%")
    print(f"Recall@5  : {recall_at[5] / total * 100:.1f}%")
    print(f"Failures  : {len(failures)}")

    if failures:
        print("\nFailure details:\n")
        for fail in failures:
            print(f"  {fail['id']} [{fail['requirement']}/{fail['complexity']}]")
            print(f"    Q: {fail['question']}")
            print(f"    Expected:  {fail['expected']}")
            print(f"    Retrieved: {fail['retrieved']}")
            print()


# ── Main ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="kautilya")
    subparsers = parser.add_subparsers(dest="group")

    # S1: corpus
    corpus_parser = subparsers.add_parser("corpus")
    corpus_sub = corpus_parser.add_subparsers(dest="cmd")
    corpus_sub.add_parser("inspect")
    entity_parser = corpus_sub.add_parser("entity")
    entity_parser.add_argument("name")

    # S2: retrieve
    retrieve_parser = subparsers.add_parser("retrieve")
    retrieve_parser.add_argument("query")
    retrieve_parser.add_argument("--top-k", type=int, default=5)
    retrieve_parser.add_argument("--trace", type=str, default=None)

    # S2: evaluate
    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("sprint")

    args = parser.parse_args()

    if args.group == "corpus":
        if args.cmd == "inspect":
            _cmd_corpus_inspect(args)
        elif args.cmd == "entity":
            _cmd_corpus_entity(args)
        else:
            corpus_parser.print_help()
    elif args.group == "retrieve":
        _cmd_retrieve(args)
    elif args.group == "evaluate":
        _cmd_evaluate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()