"""Kautilya CLI — S1 inspection surface."""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from kautilya.knowledge import CorpusValidationError, load_corpus


def _cmd_inspect(args) -> int:
    try:
        corpus = load_corpus()
    except CorpusValidationError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    type_counts = Counter(e.entity_type for e in corpus.entities)
    rel_counts = Counter(r.relation_type for r in corpus.relations)

    print("Project Kautilya")
    print("Hybrid Knowledge Exploration Laboratory")
    print()
    print("Corpus")
    print(f"  Documents : {len(corpus.documents)}")
    print(f"  Chunks    : {len(corpus.chunks)}")
    print(f"  Entities  : {len(corpus.entities)}")
    print(f"  Relations : {len(corpus.relations)}")
    print()
    print("Entity Types")
    for t, n in sorted(type_counts.items()):
        print(f"  {t:<14} {n}")
    print()
    print("Relation Types")
    for t, n in sorted(rel_counts.items()):
        print(f"  {t:<18} {n}")
    print()
    print("Integrity")
    print("  [ok] IDs unique")
    print("  [ok] References valid")
    print("  [ok] Provenance complete")
    return 0


def _cmd_entity(args) -> int:
    try:
        corpus = load_corpus()
    except CorpusValidationError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    ent = corpus.entity(args.identifier)
    if ent is None:
        print(f"Entity not found: {args.identifier}", file=sys.stderr)
        return 2

    print(ent.name)
    print(ent.entity_type)
    if ent.aliases:
        print(f"Aliases: {', '.join(ent.aliases)}")
    print()

    outgoing = [r for r in corpus.relations if r.source_entity_id == ent.id]
    incoming = [r for r in corpus.relations if r.target_entity_id == ent.id]

    if outgoing:
        print("Outgoing:")
        for r in outgoing:
            tgt = corpus.entity(r.target_entity_id)
            tgt_name = tgt.name if tgt else r.target_entity_id
            print(f"  --{r.relation_type}--> {tgt_name}   [{r.provenance.document_id}/{r.provenance.chunk_id}]")
        print()

    if incoming:
        print("Incoming:")
        for r in incoming:
            src = corpus.entity(r.source_entity_id)
            src_name = src.name if src else r.source_entity_id
            print(f"  <--{r.relation_type}-- {src_name}   [{r.provenance.document_id}/{r.provenance.chunk_id}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kautilya")
    sub = parser.add_subparsers(dest="group", required=True)

    corpus_p = sub.add_parser("corpus", help="Corpus commands")
    corpus_sub = corpus_p.add_subparsers(dest="cmd", required=True)

    insp = corpus_sub.add_parser("inspect", help="Show corpus summary")
    insp.set_defaults(func=_cmd_inspect)

    ent = corpus_sub.add_parser("entity", help="Inspect an entity by id or name")
    ent.add_argument("identifier")
    ent.set_defaults(func=_cmd_entity)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
