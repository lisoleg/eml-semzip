"""
KB Automatic Learning Module.

Mines frequent predicate patterns from hypergraphs and automatically
updates EMLLiteKB. Implements frequent subgraph mining and
attribute correlation analysis.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from ..models.hyperedge import HyperEdge
from ..models.hypergraph import EMLHypergraph
from ..kb.eml_lite_kb import EMLLiteKB


def mine_frequent_predicates(
    graph: EMLHypergraph,
    min_support: int = 2,
    min_confidence: float = 0.3,
) -> List[Dict[str, Any]]:
    """Mine frequent predicate patterns from a hypergraph.

    Args:
        graph: The hypergraph to mine.
        min_support: Minimum occurrence count for a pattern to be considered.
        min_confidence: Minimum confidence for pattern extraction.

    Returns:
        List of pattern dicts with keys:
        - predicate, node_count, support, confidence, sample_edges
    """
    pred_edges: Dict[str, List[HyperEdge]] = defaultdict(list)
    for edge in graph.E:
        pred_edges[edge.predicate].append(edge)

    patterns = []
    for pred, edges in pred_edges.items():
        if len(edges) < min_support:
            continue
        # Compute most common node-count for this predicate
        cnts = Counter(len(e.nodes) for e in edges)
        node_count, support = cnts.most_common(1)[0]
        confidence = support / len(edges)
        if confidence < min_confidence:
            continue
        # Collect attribute types across edges with this node count
        attr_type_sets = []
        for e in edges:
            if len(e.nodes) == node_count:
                attr_type_sets.append(e.attr_types)
        # Intersection of common attribute types
        if attr_type_sets:
            common_attrs = set.intersection(*attr_type_sets)
        else:
            common_attrs = set()
        patterns.append({
            "predicate": pred,
            "node_count": node_count,
            "support": support,
            "total": len(edges),
            "confidence": round(confidence, 4),
            "attr_types": sorted(common_attrs),
            "sample_edges": [e.edge_id for e in edges[:3]],
        })
    # Sort by support descending
    patterns.sort(key=lambda x: (x["support"], x["confidence"]), reverse=True)
    return patterns


def mine_attribute_correlations(
    graph: EMLHypergraph,
    min_cooccur: int = 2,
) -> List[Dict[str, Any]]:
    """Mine attribute-type correlations across hyperedges.

    Args:
        graph: The hypergraph to mine.
        min_cooccur: Minimum co-occurrence count.

    Returns:
        List of correlation dicts.
    """
    # attr_type -> list of (predicate, edge_id)
    attr_pred: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
    for edge in graph.E:
        for at in edge.attr_types:
            attr_pred[at].append((edge.predicate, edge.edge_id))

    correlations = []
    attrs = sorted(attr_pred.keys())
    for i, a1 in enumerate(attrs):
        for a2 in attrs[i + 1:]:
            # Find predicates co-occurring with both attributes
            p1 = set(p for p, _ in attr_pred[a1])
            p2 = set(p for p, _ in attr_pred[a2])
            shared = p1 & p2
            if len(shared) >= min_cooccur:
                correlations.append({
                    "attr_pair": sorted([a1, a2]),
                    "shared_predicates": sorted(shared),
                    "cooccur_count": len(shared),
                    "support_ratio": round(len(shared) / max(len(p1), len(p2)), 4),
                })
    correlations.sort(key=lambda x: x["cooccur_count"], reverse=True)
    return correlations


def hypergraph_to_patterns(
    graph: EMLHypergraph,
    min_support: int = 2,
    min_confidence: float = 0.3,
    max_patterns: int = 50,
) -> List[HyperEdge]:
    """Convert mined patterns into HyperEdge pattern objects.

    Args:
        graph: Source hypergraph.
        min_support: Minimum support for pattern mining.
        min_confidence: Minimum confidence threshold.
        max_patterns: Maximum number of patterns to generate.

    Returns:
        List of HyperEdge pattern objects ready for EMLLiteKB.
    """
    freq = mine_frequent_predicates(graph, min_support, min_confidence)
    patterns: List[HyperEdge] = []
    for i, fp in enumerate(freq[:max_patterns]):
        if fp["node_count"] < 2:
            continue
        # Build pattern nodes: n_0, n_1, ...
        node_ids = {f"n_{j}" for j in range(fp["node_count"])}
        edge_id = f"auto_pat_{fp['predicate']}_{fp['node_count']}_{i}"
        he = HyperEdge(
            edge_id=edge_id,
            nodes=node_ids,
            I_value=1.0,
            base_weight=1.0,
            dir_factor=1.0,
            predicate=fp["predicate"],
            attr_types=set(fp.get("attr_types", [])),
        )
        patterns.append(he)
    return patterns


class KBAutoLearner:
    """Automatic KB learning from hypergraph datasets.

    Incrementally mines patterns from new hypergraphs and
    updates the KB with newly discovered patterns.

    Attributes:
        kb: The EMLLiteKB to update.
        min_support: Minimum support for pattern mining.
        min_confidence: Minimum confidence threshold.
        learned_patterns: Record of all auto-learned patterns.
    """

    def __init__(
        self,
        kb: Optional[EMLLiteKB] = None,
        min_support: int = 2,
        min_confidence: float = 0.3,
    ) -> None:
        """Initialize the learner.

        Args:
            kb: Existing KB to extend (creates empty if None).
            min_support: Minimum support count.
            min_confidence: Minimum confidence.
        """
        self.kb = kb if kb is not None else EMLLiteKB()
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.learned_patterns: List[Dict[str, Any]] = []
        self._existing_sig = self.kb.compute_sig()

    def learn_from_graph(self, graph: EMLHypergraph) -> Dict[str, Any]:
        """Learn patterns from a single hypergraph and update KB.

        Args:
            graph: The hypergraph to learn from.

        Returns:
            Report dict with stats.
        """
        n_before = len(self.kb.patterns)
        patterns = hypergraph_to_patterns(
            graph, self.min_support, self.min_confidence
        )
        added = 0
        skipped = 0
        for pat in patterns:
            # De-duplicate: skip if isomorphic pattern already exists
            existing = self.kb.find_isomorphic(pat)
            if existing is not None:
                skipped += 1
                continue
            self.kb.add_pattern(pat)
            added += 1

        self.learned_patterns.append({
            "source_nodes": graph.node_count(),
            "source_edges": graph.edge_count(),
            "patterns_mined": len(patterns),
            "added": added,
            "skipped_duplicates": skipped,
        })
        new_sig = self.kb.compute_sig()
        report = {
            "patterns_before": n_before,
            "patterns_after": len(self.kb.patterns),
            "newly_added": added,
            "duplicates_skipped": skipped,
            "kb_sig_before": self._existing_sig[:16] + "...",
            "kb_sig_after": new_sig[:16] + "...",
        }
        self._existing_sig = new_sig
        return report

    def learn_from_graphs(self, graphs: List[EMLHypergraph]) -> List[Dict[str, Any]]:
        """Learn patterns from multiple hypergraphs.

        Args:
            graphs: List of hypergraphs to learn from.

        Returns:
            List of report dicts, one per graph.
        """
        return [self.learn_from_graph(g) for g in graphs]

    def save_kb(self, path: str) -> None:
        """Save the updated KB to disk.

        Args:
            path: Output JSON file path.
        """
        self.kb.save(path)

    def load_kb(self, path: str) -> None:
        """Load an existing KB from disk.

        Args:
            path: Input JSON file path.
        """
        self.kb = EMLLiteKB.load(path)
        self._existing_sig = self.kb.compute_sig()

    def get_kb(self) -> EMLLiteKB:
        """Return the current KB.

        Returns:
            The EMLLiteKB instance.
        """
        return self.kb

    def summary(self) -> str:
        """Return a text summary of learning results.

        Returns:
            Multi-line summary string.
        """
        lines = [
            f"KB Auto-Learner Summary",
            f"  Total patterns in KB: {len(self.kb.patterns)}",
            f"  Learning rounds: {len(self.learned_patterns)}",
        ]
        for i, rec in enumerate(self.learned_patterns):
            lines.append(
                f"  Round {i+1}: "
                f"mined {rec['patterns_mined']}, "
                f"added {rec['added']}, "
                f"skipped {rec['skipped_duplicates']}"
            )
        return "\n".join(lines)
