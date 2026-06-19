"""
Real Knowledge Graph Evaluation for EML-SemZip.

Evaluates SCR (Semantic Compression Ratio) on real knowledge graphs
(DBpedia, Wikidata) vs. random hypergraphs.

Usage:
    python -m eml_semzip.benchmarks.bench_real_kg --output report.json

The script:
  1. Generates a semantic KG (with typed entities & patterned relations)
  2. Generates a random KG (same scale, no semantic structure)
  3. Converts both to EMLHypergraph
  4. Runs full 5-stage compression
  5. Reports SCR, per-stage contribution, and baseline comparison
  6. (Optional) Loads a real RDF file if --rdf-path is provided
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Semi-real KG generators ---------------------------------------------------


def generate_semantic_kg(
    n_entities: int = 500,
    n_relations: int = 20,
    n_triples: int = 2000,
    seed: int = 42,
) -> List[Tuple[str, str, str]]:
    """Generate a semi-real knowledge graph with semantic structure.

    Creates entities of different *types* (Person, Organization, Location, ...).
    Relations follow type-compatible patterns (e.g., Person → bornIn → Location),
    inducing semantic redundancy that EML-SemZip can exploit.

    Args:
        n_entities: Number of unique entities.
        n_relations: Number of unique relation types.
        n_triples: Number of (subject, predicate, object) triples.
        seed: Random seed.

    Returns:
        List of (subject, predicate, object) triples.
    """
    rng = random.Random(seed)
    entities: List[str] = [f"ent:{i:04d}" for i in range(n_entities)]

    # Assign each entity one or two *types*
    entity_types: Dict[str, List[str]] = {}
    all_types = [
        "Person", "Organization", "Location", "Event",
        "Product", "CreativeWork", "Periodical",
    ]
    for ent in entities:
        n_t = rng.randint(1, 2)
        entity_types[ent] = rng.sample(all_types, k=min(n_t, len(all_types)))

    # Define type-compatible predicate patterns
    # (domain_types, range_types, predicate_name)
    type_patterns = [
        ({"Person"}, {"Location"}, "bornIn"),
        ({"Person"}, {"Person"}, "knows"),
        ({"Person"}, {"Organization"}, "worksFor"),
        ({"Person"}, {"CreativeWork"}, "authored"),
        ({"Organization"}, {"Location"}, "headquarteredIn"),
        ({"Organization"}, {"Person"}, "employs"),
        ({"Organization"}, {"Organization"}, "subsidiaryOf"),
        ({"Location"}, {"Location"}, "borders"),
        ({"Location"}, {"Person"}, "capitalOf"),
        ({"Event"}, {"Location"}, "takesPlaceIn"),
        ({"Event"}, {"Person"}, "hasParticipant"),
        ({"Product"}, {"Organization"}, "manufacturedBy"),
        ({"Product"}, {"Periodical"}, "reviewedIn"),
        ({"CreativeWork"}, {"Person"}, "creator"),
        ({"CreativeWork"}, {"Periodical"}, "publishedIn"),
    ]
    # Pad to n_relations
    while len(type_patterns) < n_relations:
        d = rng.choice(all_types)
        r = rng.choice(all_types)
        p = f"rel:{len(type_patterns):03d}"
        type_patterns.append(({d}, {r}, p))

    # Build type → entities index for fast sampling
    type_to_ents: Dict[str, List[str]] = {t: [] for t in all_types}
    for ent, typs in entity_types.items():
        for t in typs:
            type_to_ents[t].append(ent)

    triples: List[Tuple[str, str, str]] = []
    for _ in range(n_triples):
        # Pick a type-compatible pattern
        dom_types, rng_types, pred = rng.choice(type_patterns)
        # Sample subject from domain-type entities
        dom_ents = [
            e for e in type_to_ents.get(list(dom_types)[0], entities)
            if any(t in dom_types for t in entity_types[e])
        ] or entities
        subj = rng.choice(dom_ents)
        # Sample object from range-type entities
        rng_ents = [
            e for e in type_to_ents.get(list(rng_types)[0], entities)
            if any(t in rng_types for t in entity_types[e])
        ] or entities
        obj = rng.choice(rng_ents)
        triples.append((subj, pred, obj))

    return triples


def generate_random_kg(
    n_entities: int = 500,
    n_relations: int = 20,
    n_triples: int = 2000,
    seed: int = 42,
) -> List[Tuple[str, str, str]]:
    """Generate a random KG (no semantic structure).

    All entities and relations are sampled uniformly — no type constraints,
    no patterned redundancy. This is the baseline for evaluating whether
    EML-SemZip's semantic compression *requires* semantic structure.

    Args:
        n_entities: Number of unique entities.
        n_relations: Number of unique relation types.
        n_triples: Number of triples.
        seed: Random seed.

    Returns:
        List of (subject, predicate, object) triples.
    """
    rng = random.Random(seed)
    entities = [f"ent:{i:04d}" for i in range(n_entities)]
    relations = [f"rel:{i:03d}" for i in range(n_relations)]

    triples = []
    for _ in range(n_triples):
        subj = rng.choice(entities)
        obj = rng.choice(entities)
        pred = rng.choice(relations)
        triples.append((subj, pred, obj))
    return triples


# --- Hypergraph conversion ------------------------------------------------------


def triples_to_hypergraph(
    triples: List[Tuple[str, str, str]],
    name: str = "kg",
) -> Any:
    """Convert (subject, predicate, object) triples to EMLHypergraph.

    Each triple becomes a hyperedge with:
    - nodes = {subject, object}
    - predicate = the relation type
    - I_value = 1.0 (uniform, for now)

    Args:
        triples: List of (s, p, o) triples.
        name: Name for the hypergraph.

    Returns:
        EMLHypergraph instance.
    """
    from ...models.node import Node  # type: ignore[relative-beyond-top]
    from ...models.hyperedge import HyperEdge  # type: ignore[relative-beyond-top]
    from ...models.hypergraph import EMLHypergraph  # type: ignore[relative-beyond-top]

    g = EMLHypergraph(name=name)
    for subj, pred, obj in triples:
        for nid in (subj, obj):
            if nid not in g.V:
                g.add_node(Node(nid, {"type": "entity"}))
        eid = f"{name}:edge:{subj}:{pred}:{obj}"
        g.add_edge(HyperEdge(
            edge_id=eid,
            nodes={subj, obj},
            I_value=1.0,
            base_weight=1.0,
            dir_factor=1.0,
            predicate=pred,
        ))
    return g


def load_rdf_file(rdf_path: str) -> List[Tuple[str, str, str]]:
    """Load triples from an RDF file (NTriples format, `.nt`).

    Args:
        rdf_path: Path to the `.nt` RDF file.

    Returns:
        List of (subject, predicate, object) triples.
    """
    triples = []
    with open(rdf_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # NTriples format: <subj> <pred> <obj> .
            parts = line.split()
            if len(parts) >= 4 and parts[-1] == ".":
                subj = parts[0].strip("<>")
                pred = parts[1].strip("<>")
                obj = parts[2].strip("<>")
                triples.append((subj, pred, obj))
    return triples


# --- Compression evaluation ----------------------------------------------------


def evaluate_compression(
    graph: Any,
    label: str = "unknown",
) -> Dict[str, Any]:
    """Run full 5-stage compression and collect metrics.

    Args:
        graph: EMLHypergraph to compress.
        label: Label for reporting.

    Returns:
        Dict with SCR, per-stage stats, timing, and baseline comparison.
    """
    from ...pipeline.stages import (  # type: ignore[relative-beyond-top]
        stage1_deadzero_pruning,
        stage2_isomorphic_merge,
        stage3_predicate_grouping,
        stage4_ksnap_selection,
        stage5_ans_encoding,
    )
    from ...coding.sempkt import encode_sempkt  # type: ignore[relative-beyond-top]
    from ...io.report import CompressionReport  # type: ignore[relative-beyond-top]

    report: Dict[str, Any] = {
        "label": label,
        "node_count": graph.node_count(),
        "edge_count": graph.edge_count(),
        "json_size": _estimate_json_size(graph),
    }

    # --- Run each stage and measure contribution ---
    timing: Dict[str, float] = {}
    stage_edges: Dict[str, int] = {}
    g = graph

    # Stage 1
    t0 = time.perf_counter()
    edges1, _ = stage1_deadzero_pruning(list(g.E.values()))
    timing["stage1"] = time.perf_counter() - t0
    stage_edges["stage1"] = len(edges1)
    report["stage1_kept"] = len(edges1)
    report["stage1_pruned"] = g.edge_count() - len(edges1)

    # Stage 2
    t0 = time.perf_counter()
    edges2, _, _ = stage2_isomorphic_merge(edges1)
    timing["stage2"] = time.perf_counter() - t0
    stage_edges["stage2"] = len(edges2)
    report["stage2_kept"] = len(edges2)
    report["stage2_merged"] = len(edges1) - len(edges2)

    # Stage 3
    t0 = time.perf_counter()
    groups3 = stage3_predicate_grouping(edges2)
    timing["stage3"] = time.perf_counter() - t0
    report["stage3_groups"] = len(groups3)

    # Flatten stage 3 groups back to edge list for stage 4
    edges3 = []
    for group in groups3:
        edges3.extend(group.get("edges", []))

    # Stage 4
    t0 = time.perf_counter()
    _, edges4 = stage4_ksnap_selection(edges3, keep_ratio=0.15)
    timing["stage4"] = time.perf_counter() - t0
    stage_edges["stage4"] = len(edges4)
    report["stage4_kept"] = len(edges4)
    report["stage4_selected"] = len(edges3) - len(edges4)

    # Stage 5 — encode to SemPkt and measure size
    t0 = time.perf_counter()
    from ...models.hypergraph import EMLHypergraph as HG
    g4 = HG(name=graph.name + "_stage4")
    for e in edges4:
        for nid in e.nodes:
            if nid not in g4.V:
                g4.add_node(graph.V[nid])
        g4.add_edge(e)

    sempkt_bytes = encode_sempkt(g4)
    timing["stage5"] = time.perf_counter() - t0

    compressed_size = len(sempkt_bytes)
    json_size = report["json_size"]
    scr = json_size / max(1, compressed_size)

    report["compressed_size"] = compressed_size
    report["scr"] = round(scr, 4)
    report["timing"] = {k: round(v * 1000, 2) for k, v in timing.items()}

    # Baseline: gzip/bzip2/lzma on JSON
    import gzip, bz2, lzma
    json_bytes = json.dumps(g.to_dict()).encode("utf-8")
    gz_size = len(gzip.compress(json_bytes))
    bz_size = len(bz2.compress(json_bytes))
    lzma_size = len(lzma.compress(json_bytes))

    report["baselines"] = {
        "gzip": {"size": gz_size, "ratio": round(json_size / gz_size, 4)},
        "bzip2": {"size": bz_size, "ratio": round(json_size / bz_size, 4)},
        "lzma": {"size": lzma_size, "ratio": round(json_size / lzma_size, 4)},
    }

    return report


def _estimate_json_size(g: Any) -> int:
    """Estimate JSON serialized size of a hypergraph."""
    try:
        return len(json.dumps(g.to_dict()).encode("utf-8"))
    except Exception:
        return g.node_count() * 50 + g.edge_count() * 80


# --- Main evaluation ------------------------------------------------------------


def run_evaluation(
    semantic_triples: List[Tuple[str, str, str]],
    random_triples: List[Tuple[str, str, str]],
    labels: Tuple[str, str] = ("SemanticKG", "RandomKG"),
) -> Dict[str, Any]:
    """Run full evaluation comparing semantic vs. random KG.

    Args:
        semantic_triples: Triples with semantic structure.
        random_triples: Triples without semantic structure.
        labels: (semantic_label, random_label).

    Returns:
        Dict with per-KG reports and comparison.
    """
    g_sem = triples_to_hypergraph(semantic_triples, name=labels[0])
    g_rand = triples_to_hypergraph(random_triples, name=labels[1])

    report_sem = evaluate_compression(g_sem, label=labels[0])
    report_rand = evaluate_compression(g_rand, label=labels[1])

    comparison = {
        "scr_ratio": round(report_sem["scr"] / max(0.01, report_rand["scr"]), 4),
        "semantic_scr": report_sem["scr"],
        "random_scr": report_rand["scr"],
        "semantic_better_than_gzip": report_sem["scr"] > report_sem["baselines"]["gzip"]["ratio"],
    }

    return {
        "semantic_kg": report_sem,
        "random_kg": report_rand,
        "comparison": comparison,
    }


def print_report(result: Dict[str, Any]) -> None:
    """Pretty-print the evaluation result."""
    for key in ("semantic_kg", "random_kg"):
        r = result[key]
        label = r["label"]
        print(f"\n{'=' * 60}")
        print(f"  {label}")
        print(f"{'=' * 60}")
        print(f"  Nodes: {r['node_count']}  Edges: {r['edge_count']}")
        print(f"  JSON size: {r['json_size']:,} B")
        print(f"  Compressed: {r['compressed_size']:,} B")
        print(f"  SCR (bit): {r['scr']}×")
        print(f"  Baselines: gzip={r['baselines']['gzip']['ratio']}×  "
              f"bzip2={r['baselines']['bzip2']['ratio']}×  "
              f"lzma={r['baselines']['lzma']['ratio']}×")
        print(f"  Stage contribution:")
        print(f"    S1 prune: {r.get('stage1_pruned', '?')} edges removed")
        print(f"    S2 merge: {r.get('stage2_merged', '?')} edges merged")
        print(f"    S3 groups: {r.get('stage3_groups', '?')}")
        print(f"    S4 select: {r.get('stage4_selected', '?')} edges selected")
        print(f"  Timing (ms): {r.get('timing', {})}")

    c = result["comparison"]
    print(f"\n{'=' * 60}")
    print(f"  Comparison: Semantic vs. Random")
    print(f"{'=' * 60}")
    print(f"  SCR ratio (sem/rnd): {c['scr_ratio']}×")
    print(f"  Semantic SCR: {c['semantic_scr']}×")
    print(f"  Random SCR:   {c['random_scr']}×")
    print(f"  Semantic > gzip? {c['semantic_better_than_gzip']}")


# --- CLI ----------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate EML-SemZip on real vs. random KGs"
    )
    parser.add_argument(
        "--n-entities", type=int, default=500,
        help="Number of entities (default: 500)",
    )
    parser.add_argument(
        "--n-triples", type=int, default=2000,
        help="Number of triples (default: 2000)",
    )
    parser.add_argument(
        "--rdf-path", type=str, default=None,
        help="Path to a real RDF file (.nt format) to evaluate",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to save the JSON report",
    )
    args = parser.parse_args()

    if args.rdf_path:
        print(f"Loading real KG from {args.rdf_path} ...")
        triples = load_rdf_file(args.rdf_path)
        print(f"  Loaded {len(triples)} triples")
        # Also generate a random KG of the same scale for comparison
        entities = list({s for s, _, _ in triples} | {o for _, _, o in triples})
        n_rand = len(triples)
        random_triples = generate_random_kg(
            n_entities=len(entities),
            n_relations=20,
            n_triples=n_rand,
            seed=42,
        )
        result = run_evaluation(triples, random_triples, labels=("RealKG", "RandomKG"))
    else:
        print("Generating semi-real KG (semantic structure) ...")
        sem_triples = generate_semantic_kg(
            n_entities=args.n_entities, n_triples=args.n_triples
        )
        print("Generating random KG (no semantic structure) ...")
        rand_triples = generate_random_kg(
            n_entities=args.n_entities, n_triples=args.n_triples
        )
        result = run_evaluation(sem_triples, rand_triples)

    print_report(result)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nReport saved to {args.output}")


if __name__ == "__main__":
    main()
