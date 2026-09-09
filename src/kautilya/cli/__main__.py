"""Project Kautilya — CLI entry point."""

from __future__ import annotations

import argparse
import sys
import time
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


# ── Retriever builders ──────────────────────────────────────────

def _build_semantic_retriever(top_k: int = 5):
    from kautilya.infrastructure.embeddings import SentenceTransformerProvider
    from kautilya.retrieval.semantic import SemanticRetriever

    root = _get_project_root()
    config_path = root / "experiments" / "configs" / "s2_semantic_retrieval.yaml"

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        model_name = config.get("embedding", {}).get("model", "all-MiniLM-L6-v2")
        top_k = config.get("retrieval", {}).get("top_k", top_k)
    else:
        model_name = "all-MiniLM-L6-v2"

    print(f"Loading embedding model: {model_name} ...")
    provider = SentenceTransformerProvider(model_name)
    print(f"  dimension: {provider.dimension}")

    corpus = _load_corpus()
    print(f"Building index over {len(list(corpus.chunks))} chunks ...")
    return SemanticRetriever(
        corpus=corpus,
        embedding_provider=provider,
        top_k=top_k,
    )


def _build_kag_retriever(max_hops: int = 2, top_k: int = 5):
    from kautilya.retrieval.structural import KAGRetriever

    root = _get_project_root()
    config_path = root / "experiments" / "configs" / "s3_kag.yaml"

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        max_hops = config.get("retrieval", {}).get("max_hops", max_hops)
        top_k = config.get("retrieval", {}).get("top_k", top_k)

    corpus = _load_corpus()
    return KAGRetriever(
        corpus=corpus,
        max_hops=max_hops,
        top_k=top_k,
    )


def _build_fusion():
    from kautilya.fusion.evidence_fusion import EvidenceFusion

    root = _get_project_root()
    config_path = root / "experiments" / "configs" / "s4_hybrid.yaml"

    sem_w, kag_w, bonus = 1.0, 1.0, 0.5
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        fusion_cfg = config.get("fusion", {}) or {}
        sem_w = fusion_cfg.get("semantic_weight", sem_w)
        kag_w = fusion_cfg.get("structural_weight", kag_w)
        bonus = fusion_cfg.get("agreement_bonus", bonus)

    return EvidenceFusion(
        semantic_weight=sem_w,
        structural_weight=kag_w,
        agreement_bonus=bonus,
    )


def _build_reasoning_fusion():
    from kautilya.fusion.evidence_fusion import EvidenceFusion

    root = _get_project_root()
    config_path = root / "experiments" / "configs" / "s6_reasoning_hybrid.yaml"

    sem_w, kag_w, rea_w, bonus = 1.0, 1.0, 1.0, 0.5
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        fusion_cfg = config.get("fusion", {}) or {}
        sem_w = fusion_cfg.get("semantic_weight", sem_w)
        kag_w = fusion_cfg.get("structural_weight", kag_w)
        rea_w = fusion_cfg.get("reasoning_weight", rea_w)
        bonus = fusion_cfg.get("agreement_bonus", bonus)

    return EvidenceFusion(
        semantic_weight=sem_w,
        structural_weight=kag_w,
        reasoning_weight=rea_w,
        agreement_bonus=bonus,
    )


def _run_reasoning(query: str, corpus=None, max_hops: int = 2):
    from kautilya.knowledge.graph import KnowledgeGraph
    from kautilya.reasoning.decomposer import QueryDecomposer
    from kautilya.reasoning.evidence_adapter import trace_to_retrieval_result
    from kautilya.reasoning.executor import ReasoningExecutor

    if corpus is None:
        corpus = _load_corpus()

    graph = KnowledgeGraph.from_corpus(corpus)
    decomposer = QueryDecomposer()
    executor = ReasoningExecutor(graph, max_hops=max_hops)

    plan = decomposer.decompose(query)
    if plan is None:
        from kautilya.contracts.reasoning import ReasoningPlan, ReasoningStatus, ReasoningTrace
        from kautilya.contracts.retrieval import RetrievalResult
        trace = ReasoningTrace(
            plan=ReasoningPlan(query=query, seed_entity_name="", steps=()),
            hops=(),
            terminal_entity_name=None,
            status=ReasoningStatus.DECOMPOSITION_FAILURE,
        )
        return trace, RetrievalResult(
            query=query,
            evidence=[],
            retrieval_method="reasoning",
            metadata={"status": trace.status.value, "reasoning_trace": trace.to_dict()},
        )

    trace = executor.execute(plan)
    result = trace_to_retrieval_result(trace, corpus=corpus)
    return trace, result


# ── Result Print Formatters ────────────────────────────────────

def _print_semantic_result(result) -> None:
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


def _print_kag_result(result) -> None:
    print()
    print("Project Kautilya")
    print("Structural Retrieval (KAG)")
    print("=" * 50)
    print(f"\nQuery:\n  {result.query}\n")
    entities_resolved = result.metadata.get("entities_resolved", [])
    if entities_resolved:
        print(f"Resolved Entities: {', '.join(entities_resolved)}")
    paths = result.metadata.get("paths", [])
    if paths:
        print(f"\nDiscovered Knowledge Paths ({len(paths)}):")
        for i, p in enumerate(paths, 1):
            print(f"  [{i}] {p['formatted']} (hops: {p['hops']})")
    print("\nRetrieved Evidence:")
    for i, ev in enumerate(result.evidence, 1):
        print(f"  [{i}] score={ev.score:.4f}")
        print(f"      {ev.document_id} / {ev.chunk_id}")
        if "path_formatted" in ev.metadata:
            print(f"      via: {ev.metadata['path_formatted']}")
        text_preview = ev.text[:120].replace("\n", " ")
        print(f"      {text_preview}...")
        print()
    print(f"Retrieval method: {result.retrieval_method}")
    print(f"Evidence origin:  {result.evidence[0].evidence_origin if result.evidence else 'N/A'}")
    print(f"Max hops:         {result.metadata.get('max_hops', 'N/A')}")
    print(f"Paths found:      {result.metadata.get('paths_found', 0)}")


def _print_reasoning_result(trace, result) -> None:
    print()
    print("Project Kautilya")
    print("Hybrid Reasoning (S5)")
    print("=" * 50)
    print(f"\nQuery:\n  {result.query}\n")
    print(f"Reasoning Status: {trace.status.value}")
    if trace.plan.seed_entity_name:
        print(f"Seed Entity:      {trace.plan.seed_entity_name}")
        print(f"Planned Hops:     {trace.plan.num_hops}")
    if trace.terminal_entity_name:
        print(f"Terminal Entity:  {trace.terminal_entity_name}")

    if trace.hops:
        print("\nReasoning Chain:")
        for hop in trace.hops:
            dir_str = "-->" if hop.direction.value == "outgoing" else "<--"
            print(f"  Step {hop.hop_index}: {hop.source_entity_name} {dir_str} {hop.relation_type} {dir_str} {hop.target_entity_name} [{hop.status.value}]")

    print("\nRetrieved Evidence:")
    for i, ev in enumerate(result.evidence, 1):
        print(f"  [{i}] score={ev.score:.4f}")
        print(f"      {ev.document_id} / {ev.chunk_id}")
        if "path_formatted" in ev.metadata:
            print(f"      via: {ev.metadata['path_formatted']}")
        text_preview = ev.text[:120].replace("\n", " ")
        print(f"      {text_preview}...")
        print()


def _print_hybrid_result(query: str, sem_result, kag_result, fused_result,
                         sem_ms: float, kag_ms: float, fuse_ms: float) -> None:
    print()
    print("Project Kautilya")
    print("Hybrid Retrieval (Semantic + Structural Fusion)")
    print("=" * 60)
    print(f"\nQuery:\n  {query}\n")

    print("Semantic Retrieval Input:")
    for i, ev in enumerate(sem_result.evidence, 1):
        print(f"  sem[{i}] score={ev.score:.4f}  {ev.chunk_id}")
    print()

    print("Structural Retrieval Input:")
    for i, ev in enumerate(kag_result.evidence, 1):
        via = ev.metadata.get("path_formatted", "")
        print(f"  kag[{i}] score={ev.score:.4f}  {ev.chunk_id}"
              + (f"  via: {via}" if via else ""))
    print()

    print("Fused Evidence:")
    for i, ev in enumerate(fused_result.evidence, 1):
        m = ev.metadata
        srcs = "+".join(m.get("fusion_sources", []))
        sem_r = m.get("semantic_rank")
        kag_r = m.get("structural_rank")
        sem_r_s = str(sem_r) if sem_r is not None else "-"
        kag_r_s = str(kag_r) if kag_r is not None else "-"
        agree = "AGREE" if m.get("agreement") else "     "
        print(f"  [{i}] fusion={m.get('fusion_score', ev.score):.4f} {agree}")
        print(f"      sources: {srcs}   sem_rank={sem_r_s}  kag_rank={kag_r_s}")
        print(f"      {ev.document_id} / {ev.chunk_id}")
        if "path_formatted" in m:
            print(f"      via: {m['path_formatted']}")
        text_preview = ev.text[:120].replace("\n", " ")
        print(f"      {text_preview}...")
        print()

    md = fused_result.metadata
    print(f"Retrieval method  : {fused_result.retrieval_method}")
    print(f"Unique chunks     : {md.get('unique_chunks', 0)}")
    print(f"Agreement count   : {md.get('agreement_count', 0)}")
    print(f"Dedup rate        : {md.get('dedup_rate', 0.0)}")
    print(f"Normalization     : {md.get('normalization', 'N/A')}")
    print(f"Weights           : {md.get('fusion_weights', {})}")
    print(f"Latency (ms)      : semantic={sem_ms:.1f}  structural={kag_ms:.1f}  fusion={fuse_ms:.1f}")


def _print_reasoning_hybrid_result(
    query: str,
    sem_result,
    kag_result,
    rea_trace,
    rea_result,
    fused_result,
    sem_ms: float,
    kag_ms: float,
    rea_ms: float,
    fuse_ms: float,
) -> None:
    print()
    print("Project Kautilya")
    print("Reasoning-Aware Hybrid Retrieval (S6)")
    print("=" * 65)
    print(f"\nQuery:\n  {query}\n")

    print(f"Reasoning Status: {rea_trace.status.value}")
    if rea_trace.is_success and rea_trace.terminal_entity_name:
        print(f"Reasoning Target: {rea_trace.terminal_entity_name} ({len(rea_trace.hops)} hops)")

    print("\nRetrieval Sources Summary:")
    print(f"  Semantic hits   : {len(sem_result.evidence)}")
    print(f"  Structural hits : {len(kag_result.evidence)}")
    print(f"  Reasoning hits  : {len(rea_result.evidence)} (participated: {fused_result.metadata.get('reasoning_participated', False)})")
    print()

    print("Fused Evidence (S6):")
    for i, ev in enumerate(fused_result.evidence, 1):
        m = ev.metadata
        srcs = "+".join(m.get("fusion_sources", []))
        sem_r = m.get("semantic_rank")
        kag_r = m.get("structural_rank")
        rea_r = m.get("reasoning_rank")
        sem_r_s = str(sem_r) if sem_r is not None else "-"
        kag_r_s = str(kag_r) if kag_r is not None else "-"
        rea_r_s = str(rea_r) if rea_r is not None else "-"
        agree = f"AGREE({m.get('source_count', 1)})" if m.get("agreement") else "        "
        print(f"  [{i}] fusion={m.get('fusion_score', ev.score):.4f} {agree}")
        print(f"      sources: {srcs:<24} sem_rank={sem_r_s}  kag_rank={kag_r_s}  rea_rank={rea_r_s}")
        print(f"      {ev.document_id} / {ev.chunk_id}")
        if "path_formatted" in m:
            print(f"      via: {m['path_formatted']}")
        text_preview = ev.text[:120].replace("\n", " ")
        print(f"      {text_preview}...")
        print()

    md = fused_result.metadata
    print(f"Retrieval method  : {fused_result.retrieval_method}")
    print(f"Reasoning Active  : {md.get('reasoning_participated', False)}")
    print(f"Unique chunks     : {md.get('unique_chunks', 0)}")
    print(f"Agreement count   : {md.get('agreement_count', 0)}")
    print(f"Dedup rate        : {md.get('dedup_rate', 0.0)}")
    print(f"Normalization     : {md.get('normalization', 'N/A')}")
    print(f"Weights           : {md.get('fusion_weights', {})}")
    print(f"Latency (ms)      : sem={sem_ms:.1f}  kag={kag_ms:.1f}  rea={rea_ms:.1f}  fuse={fuse_ms:.1f}")


# ── Commands ───────────────────────────────────────────────────

def _cmd_retrieve(args: argparse.Namespace) -> None:
    mode = getattr(args, "mode", "semantic")

    if mode == "kag":
        retriever = _build_kag_retriever(max_hops=args.max_hops, top_k=args.top_k)
        result = retriever.retrieve(args.query, top_k=args.top_k, max_hops=args.max_hops)
        _print_kag_result(result)

    elif mode == "reasoning":
        corpus = _load_corpus()
        trace, result = _run_reasoning(args.query, corpus=corpus, max_hops=args.max_hops)
        _print_reasoning_result(trace, result)

    elif mode == "hybrid":
        sem_retriever = _build_semantic_retriever(top_k=args.top_k)
        kag_retriever = _build_kag_retriever(max_hops=args.max_hops, top_k=args.top_k)
        fusion = _build_fusion()

        t0 = time.perf_counter()
        sem_result = sem_retriever.retrieve(args.query, top_k=args.top_k)
        t1 = time.perf_counter()
        kag_result = kag_retriever.retrieve(args.query, top_k=args.top_k, max_hops=args.max_hops)
        t2 = time.perf_counter()
        fused = fusion.fuse(sem_result, kag_result, top_k=args.top_k)
        t3 = time.perf_counter()

        _print_hybrid_result(
            args.query, sem_result, kag_result, fused,
            sem_ms=(t1 - t0) * 1000,
            kag_ms=(t2 - t1) * 1000,
            fuse_ms=(t3 - t2) * 1000,
        )
        result = fused

    elif mode == "reasoning-hybrid":
        corpus = _load_corpus()
        sem_retriever = _build_semantic_retriever(top_k=args.top_k)
        kag_retriever = _build_kag_retriever(max_hops=args.max_hops, top_k=args.top_k)
        fusion = _build_reasoning_fusion()

        t0 = time.perf_counter()
        sem_result = sem_retriever.retrieve(args.query, top_k=args.top_k)
        t1 = time.perf_counter()
        kag_result = kag_retriever.retrieve(args.query, top_k=args.top_k, max_hops=args.max_hops)
        t2 = time.perf_counter()
        rea_trace, rea_result = _run_reasoning(args.query, corpus=corpus, max_hops=args.max_hops)
        t3 = time.perf_counter()
        fused = fusion.fuse(sem_result, kag_result, rea_result, top_k=args.top_k)
        t4 = time.perf_counter()

        _print_reasoning_hybrid_result(
            args.query,
            sem_result,
            kag_result,
            rea_trace,
            rea_result,
            fused,
            sem_ms=(t1 - t0) * 1000,
            kag_ms=(t2 - t1) * 1000,
            rea_ms=(t3 - t2) * 1000,
            fuse_ms=(t4 - t3) * 1000,
        )
        result = fused

    else:
        retriever = _build_semantic_retriever(top_k=args.top_k)
        result = retriever.retrieve(args.query, top_k=args.top_k)
        _print_semantic_result(result)

    if args.trace:
        trace_path = Path(args.trace)
        with open(trace_path, "w", encoding="utf-8") as f:
            yaml.dump(result.to_dict(), f, default_flow_style=False)
        print(f"\nTrace written to: {trace_path}")


# ── Evaluations (S2, S3, S4, S5, S6) ────────────────────────────

def _evaluate_s2() -> None:
    root = _get_project_root()
    benchmark_path = root / "data" / "benchmarks" / "s2_questions.yaml"
    if not benchmark_path.exists():
        print(f"Benchmark not found: {benchmark_path}")
        sys.exit(1)

    with open(benchmark_path, encoding="utf-8") as f:
        benchmark = yaml.safe_load(f) or {}

    questions = benchmark.get("questions", [])
    print(f"\nLoading S2 benchmark: {len(questions)} questions")

    retriever = _build_semantic_retriever(top_k=5)
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
            failures.append({
                "id": qid, "question": question,
                "expected": sorted(expected), "retrieved": retrieved_ids,
                "requirement": q.get("knowledge_requirement", "?"),
                "complexity": q.get("reasoning_complexity", "?"),
            })

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


def _evaluate_s3() -> None:
    root = _get_project_root()
    benchmark_path = root / "data" / "benchmarks" / "s3_questions.yaml"
    if not benchmark_path.exists():
        print(f"Benchmark not found: {benchmark_path}")
        sys.exit(1)

    with open(benchmark_path, encoding="utf-8") as f:
        benchmark = yaml.safe_load(f) or {}

    questions = benchmark.get("questions", [])
    print(f"\nLoading S3 benchmark: {len(questions)} questions")

    retriever = _build_kag_retriever(max_hops=2, top_k=5)
    recall_at = {1: 0, 3: 0, 5: 0}
    provenance_valid = 0
    path_found_count = 0
    failures = []

    for q in questions:
        qid = q["id"]
        question = q["question"]
        expected_chunks = {e["chunk_id"] for e in q.get("expected_evidence", [])}
        result = retriever.retrieve(question, top_k=5)
        retrieved_ids = result.top_chunk_ids
        for k in recall_at:
            if expected_chunks & set(retrieved_ids[:k]):
                recall_at[k] += 1
        if result.metadata.get("paths_found", 0) > 0:
            path_found_count += 1
        if result.evidence:
            all_prov_ok = all(
                ev.provenance.get("document_id") and ev.provenance.get("chunk_id")
                for ev in result.evidence
            )
            if all_prov_ok:
                provenance_valid += 1
        if not (expected_chunks & set(retrieved_ids)):
            failures.append({
                "id": qid, "question": question,
                "expected": sorted(expected_chunks), "retrieved": retrieved_ids,
                "category": q.get("category", "?"),
                "complexity": q.get("complexity", "?"),
            })

    total = len(questions)
    print()
    print("Project Kautilya")
    print("S3 Structural Retrieval (KAG) Evaluation")
    print("=" * 50)
    print(f"\nQuestions     : {total}")
    print(f"Recall@1      : {recall_at[1] / total * 100:.1f}%")
    print(f"Recall@3      : {recall_at[3] / total * 100:.1f}%")
    print(f"Recall@5      : {recall_at[5] / total * 100:.1f}%")
    print(f"Path Discovery: {path_found_count / total * 100:.1f}%")
    print(f"Provenance OK : {provenance_valid / total * 100:.1f}%")
    print(f"Failures      : {len(failures)}")


def _evaluate_s4() -> None:
    """S4 evaluation: run RAG, KAG, and Fusion side-by-side on the S4 benchmark."""
    root = _get_project_root()
    benchmark_path = root / "data" / "benchmarks" / "s4_questions.yaml"
    if not benchmark_path.exists():
        print(f"Benchmark not found: {benchmark_path}")
        sys.exit(1)

    with open(benchmark_path, encoding="utf-8") as f:
        benchmark = yaml.safe_load(f) or {}

    questions = benchmark.get("questions", [])
    print(f"\nLoading S4 benchmark: {len(questions)} questions")

    sem_retriever = _build_semantic_retriever(top_k=5)
    kag_retriever = _build_kag_retriever(max_hops=2, top_k=5)
    fusion = _build_fusion()

    modes = ["semantic", "kag", "fusion"]
    recall = {m: {1: 0, 3: 0, 5: 0} for m in modes}
    latency_totals = {m: 0.0 for m in modes}
    per_category: dict[str, dict[str, dict[int, int]]] = {}
    per_category_totals: dict[str, int] = {}
    failures: list[dict] = []

    for q in questions:
        question = q["question"]
        expected = {e["chunk_id"] for e in q.get("expected_evidence", [])}
        category = q.get("category", "uncategorized")
        per_category.setdefault(category, {m: {1: 0, 3: 0, 5: 0} for m in modes})
        per_category_totals[category] = per_category_totals.get(category, 0) + 1

        t0 = time.perf_counter()
        sem_result = sem_retriever.retrieve(question, top_k=5)
        t1 = time.perf_counter()
        kag_result = kag_retriever.retrieve(question, top_k=5)
        t2 = time.perf_counter()
        fused_result = fusion.fuse(sem_result, kag_result, top_k=5)
        t3 = time.perf_counter()

        latency_totals["semantic"] += (t1 - t0) * 1000
        latency_totals["kag"] += (t2 - t1) * 1000
        latency_totals["fusion"] += (t3 - t2) * 1000

        mode_ids = {
            "semantic": sem_result.top_chunk_ids,
            "kag": kag_result.top_chunk_ids,
            "fusion": fused_result.top_chunk_ids,
        }

        for mode, ids in mode_ids.items():
            for k in (1, 3, 5):
                if expected & set(ids[:k]):
                    recall[mode][k] += 1
                    per_category[category][mode][k] += 1

        if not (expected & set(mode_ids["fusion"])):
            failures.append({
                "id": q.get("id"),
                "question": question,
                "category": category,
                "expected": sorted(expected),
                "fusion_retrieved": mode_ids["fusion"],
                "semantic_retrieved": mode_ids["semantic"],
                "kag_retrieved": mode_ids["kag"],
            })

    total = len(questions)
    print()
    print("Project Kautilya")
    print("S4 Evidence Fusion Evaluation")
    print("=" * 60)
    print(f"\nQuestions: {total}\n")

    header = f"{'':<12}{'Recall@1':>12}{'Recall@3':>12}{'Recall@5':>12}"
    print(header)
    print("-" * len(header))
    for m in modes:
        r1 = recall[m][1] / total * 100
        r3 = recall[m][3] / total * 100
        r5 = recall[m][5] / total * 100
        print(f"{m:<12}{r1:>11.1f}%{r3:>11.1f}%{r5:>11.1f}%")

    print()
    print("Fusion Δ vs Semantic:")
    for k in (1, 3, 5):
        delta = (recall["fusion"][k] - recall["semantic"][k]) / total * 100
        print(f"  Δ Recall@{k}: {delta:+.1f}%")
    print("Fusion Δ vs KAG:")
    for k in (1, 3, 5):
        delta = (recall["fusion"][k] - recall["kag"][k]) / total * 100
        print(f"  Δ Recall@{k}: {delta:+.1f}%")

    print()
    print("Latency (avg ms per query):")
    for m in modes:
        print(f"  {m:<12}: {latency_totals[m] / total:.2f} ms")
    total_hybrid_ms = (latency_totals["semantic"] + latency_totals["kag"] + latency_totals["fusion"]) / total
    print(f"  hybrid_total: {total_hybrid_ms:.2f} ms")

    print()
    print("Per-category Recall@3:")
    cat_header = f"{'category':<24}{'sem':>8}{'kag':>8}{'fusion':>8}{'n':>6}"
    print(cat_header)
    print("-" * len(cat_header))
    for cat in sorted(per_category.keys()):
        n = per_category_totals[cat]
        s = per_category[cat]["semantic"][3] / n * 100
        k = per_category[cat]["kag"][3] / n * 100
        f_ = per_category[cat]["fusion"][3] / n * 100
        print(f"{cat:<24}{s:>7.1f}%{k:>7.1f}%{f_:>7.1f}%{n:>6d}")


def _evaluate_s5() -> None:
    root = _get_project_root()
    benchmark_path = root / "data" / "benchmarks" / "s5_questions.yaml"
    if not benchmark_path.exists():
        print(f"Benchmark not found: {benchmark_path}")
        sys.exit(1)

    with open(benchmark_path, encoding="utf-8") as f:
        benchmark = yaml.safe_load(f) or {}

    questions = benchmark.get("questions", [])
    print(f"\nLoading S5 benchmark: {len(questions)} questions")

    corpus = _load_corpus()
    sem_retriever = _build_semantic_retriever(top_k=5)
    kag_retriever = _build_kag_retriever(max_hops=2, top_k=5)
    fusion = _build_fusion()

    modes = ["semantic", "kag", "fusion", "reasoning"]
    recall = {m: {1: 0, 3: 0, 5: 0} for m in modes}
    plans_constructed = 0
    chains_succeeded = 0
    total_hops = 0

    for q in questions:
        question = q["question"]
        expected = {e["chunk_id"] for e in q.get("expected_evidence", [])}

        sem_res = sem_retriever.retrieve(question, top_k=5)
        kag_res = kag_retriever.retrieve(question, top_k=5)
        fused_res = fusion.fuse(sem_res, kag_res, top_k=5)
        trace, rea_res = _run_reasoning(question, corpus=corpus)

        if trace.plan.seed_entity_name:
            plans_constructed += 1
        if trace.is_success:
            chains_succeeded += 1
            total_hops += len(trace.hops)

        mode_ids = {
            "semantic": sem_res.top_chunk_ids,
            "kag": kag_res.top_chunk_ids,
            "fusion": fused_res.top_chunk_ids,
            "reasoning": rea_res.top_chunk_ids,
        }

        for mode, ids in mode_ids.items():
            for k in (1, 3, 5):
                if expected and (expected & set(ids[:k])):
                    recall[mode][k] += 1

    total = len(questions)
    print()
    print("Project Kautilya")
    print("S5 Hybrid Reasoning Evaluation")
    print("=" * 60)
    print(f"\nQuestions: {total}\n")

    header = f"{'':<14}{'Recall@1':>12}{'Recall@3':>12}{'Recall@5':>12}"
    print(header)
    print("-" * len(header))
    for m in modes:
        r1 = recall[m][1] / total * 100
        r3 = recall[m][3] / total * 100
        r5 = recall[m][5] / total * 100
        print(f"{m:<14}{r1:>11.1f}%{r3:>11.1f}%{r5:>11.1f}%")

    print()
    print(f"Plan Construction Rate: {plans_constructed / total * 100:.1f}% ({plans_constructed}/{total})")
    chain_succ_rate = (chains_succeeded / plans_constructed * 100) if plans_constructed > 0 else 0.0
    print(f"Chain Success Rate    : {chain_succ_rate:.1f}%")
    mean_hops = (total_hops / chains_succeeded) if chains_succeeded > 0 else 0.0
    print(f"Mean Hops per Chain   : {mean_hops:.1f}")


def _evaluate_s6() -> None:
    root = _get_project_root()
    benchmark_path = root / "data" / "benchmarks" / "s6_questions.yaml"
    if not benchmark_path.exists():
        print(f"Benchmark not found: {benchmark_path}")
        sys.exit(1)

    with open(benchmark_path, encoding="utf-8") as f:
        benchmark = yaml.safe_load(f) or {}

    questions = benchmark.get("questions", [])
    print(f"\nLoading S6 benchmark: {len(questions)} questions")

    corpus = _load_corpus()
    sem_retriever = _build_semantic_retriever(top_k=5)
    kag_retriever = _build_kag_retriever(max_hops=2, top_k=5)
    s4_fusion = _build_fusion()
    s6_fusion = _build_reasoning_fusion()

    modes = ["semantic", "kag", "s4_fusion", "reasoning", "s6_fusion"]
    recall = {m: {1: 0, 3: 0, 5: 0} for m in modes}
    latency_totals = {m: 0.0 for m in ["semantic", "kag", "reasoning", "s4_fusion", "s6_fusion"]}
    per_category: dict[str, dict[str, dict[int, int]]] = {}
    per_category_totals: dict[str, int] = {}

    reasoning_invoked = 0
    reasoning_succeeded = 0
    reasoning_contributed = 0
    total_reasoning_hops = 0

    for q in questions:
        question = q["question"]
        expected = {e["chunk_id"] for e in q.get("expected_evidence", [])}
        category = q.get("category", "uncategorized")
        per_category.setdefault(category, {m: {1: 0, 3: 0, 5: 0} for m in modes})
        per_category_totals[category] = per_category_totals.get(category, 0) + 1

        t0 = time.perf_counter()
        sem_result = sem_retriever.retrieve(question, top_k=5)
        t1 = time.perf_counter()
        kag_result = kag_retriever.retrieve(question, top_k=5)
        t2 = time.perf_counter()
        rea_trace, rea_result = _run_reasoning(question, corpus=corpus)
        t3 = time.perf_counter()
        s4_result = s4_fusion.fuse(sem_result, kag_result, top_k=5)
        t4 = time.perf_counter()
        s6_result = s6_fusion.fuse(sem_result, kag_result, rea_result, top_k=5)
        t5 = time.perf_counter()

        latency_totals["semantic"] += (t1 - t0) * 1000
        latency_totals["kag"] += (t2 - t1) * 1000
        latency_totals["reasoning"] += (t3 - t2) * 1000
        latency_totals["s4_fusion"] += (t4 - t3) * 1000
        latency_totals["s6_fusion"] += (t5 - t4) * 1000

        if rea_trace.plan.seed_entity_name:
            reasoning_invoked += 1
        if rea_trace.is_success:
            reasoning_succeeded += 1
            total_reasoning_hops += len(rea_trace.hops)

        if s6_result.metadata.get("reasoning_participated", False):
            reasoning_contributed += 1

        mode_ids = {
            "semantic": sem_result.top_chunk_ids,
            "kag": kag_result.top_chunk_ids,
            "s4_fusion": s4_result.top_chunk_ids,
            "reasoning": rea_result.top_chunk_ids,
            "s6_fusion": s6_result.top_chunk_ids,
        }

        for mode, ids in mode_ids.items():
            for k in (1, 3, 5):
                if expected and (expected & set(ids[:k])):
                    recall[mode][k] += 1
                    per_category[category][mode][k] += 1

    total = len(questions)
    eval_total = sum(1 for q in questions if q.get("expected_evidence"))

    print()
    print("Project Kautilya")
    print("S6 Reasoning-Aware Hybrid Retrieval Evaluation")
    print("=" * 65)
    print(f"\nTotal Questions   : {total}")
    print(f"Evaluated (GT > 0): {eval_total}\n")

    header = f"{'Mode':<16}{'Recall@1':>12}{'Recall@3':>12}{'Recall@5':>12}"
    print(header)
    print("-" * len(header))
    denom = eval_total if eval_total > 0 else total
    for m in modes:
        r1 = recall[m][1] / denom * 100
        r3 = recall[m][3] / denom * 100
        r5 = recall[m][5] / denom * 100
        print(f"{m:<16}{r1:>11.1f}%{r3:>11.1f}%{r5:>11.1f}%")

    print()
    print("S6 Fusion Δ vs S4 Baseline:")
    for k in (1, 3, 5):
        delta = (recall["s6_fusion"][k] - recall["s4_fusion"][k]) / denom * 100
        print(f"  Δ Recall@{k}: {delta:+.1f}%")

    print()
    print("Reasoning Diagnostic Metrics:")
    print(f"  Invocation Rate     : {reasoning_invoked / total * 100:.1f}% ({reasoning_invoked}/{total})")
    succ_rate = (reasoning_succeeded / reasoning_invoked * 100) if reasoning_invoked > 0 else 0.0
    print(f"  Success Rate        : {succ_rate:.1f}%")
    print(f"  Contribution Rate   : {reasoning_contributed / total * 100:.1f}%")
    mean_hops = (total_reasoning_hops / reasoning_succeeded) if reasoning_succeeded > 0 else 0.0
    print(f"  Mean Reasoning Hops : {mean_hops:.1f}")

    print()
    print("Latency (avg ms per query):")
    for m in ["semantic", "kag", "reasoning", "s4_fusion", "s6_fusion"]:
        print(f"  {m:<14}: {latency_totals[m] / total:.2f} ms")
    total_s6_ms = (latency_totals["semantic"] + latency_totals["kag"] + latency_totals["reasoning"] + latency_totals["s6_fusion"]) / total
    print(f"  s6_hybrid_total : {total_s6_ms:.2f} ms")

    print()
    print("Per-category Recall@3 (on questions with ground truth):")
    cat_header = f"{'category':<24}{'sem':>8}{'kag':>8}{'s4':>8}{'s6':>8}{'n':>6}"
    print(cat_header)
    print("-" * len(cat_header))
    for cat in sorted(per_category.keys()):
        n = per_category_totals[cat]
        has_gt = any(q.get("expected_evidence") for q in questions if q.get("category") == cat)
        if has_gt and n > 0:
            s = per_category[cat]["semantic"][3] / n * 100
            k = per_category[cat]["kag"][3] / n * 100
            s4_ = per_category[cat]["s4_fusion"][3] / n * 100
            s6_ = per_category[cat]["s6_fusion"][3] / n * 100
            print(f"{cat:<24}{s:>7.1f}%{k:>7.1f}%{s4_:>7.1f}%{s6_:>7.1f}%{n:>6d}")
        else:
            print(f"{cat:<24}{'-':>8}{'-':>8}{'-':>8}{'-':>8}{n:>6d} (boundary)")


def _cmd_evaluate(args: argparse.Namespace) -> None:
    sprint = args.sprint
    if sprint == "s2":
        _evaluate_s2()
    elif sprint == "s3":
        _evaluate_s3()
    elif sprint == "s4":
        _evaluate_s4()
    elif sprint == "s5":
        _evaluate_s5()
    elif sprint == "s6":
        _evaluate_s6()
    else:
        print(f"Unknown sprint: {sprint}. Use 's2', 's3', 's4', 's5', or 's6'.")
        sys.exit(1)


# ── Main ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(prog="kautilya")
    subparsers = parser.add_subparsers(dest="group")

    corpus_parser = subparsers.add_parser("corpus")
    corpus_sub = corpus_parser.add_subparsers(dest="cmd")
    corpus_sub.add_parser("inspect")
    entity_parser = corpus_sub.add_parser("entity")
    entity_parser.add_argument("name")

    retrieve_parser = subparsers.add_parser("retrieve")
    retrieve_parser.add_argument("query")
    retrieve_parser.add_argument(
        "--mode",
        choices=["semantic", "kag", "hybrid", "reasoning", "reasoning-hybrid"],
        default="semantic",
        help="Retrieval mode: 'semantic', 'kag', 'hybrid', 'reasoning', or 'reasoning-hybrid'",
    )
    retrieve_parser.add_argument("--top-k", type=int, default=5)
    retrieve_parser.add_argument(
        "--max-hops", type=int, default=2,
        help="Maximum hops for structural traversal (KAG, reasoning, or hybrid modes)",
    )
    retrieve_parser.add_argument("--trace", type=str, default=None)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("sprint", choices=["s2", "s3", "s4", "s5", "s6"])

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
