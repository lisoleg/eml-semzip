"""Decompressor class for EML-SemZip.

Reverses the compression pipeline: decodes ANS, deserializes the payload,
and reconstructs the hypergraph.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..coding.sempkt import SemPkt
from ..coding.serializer import deserialize
from ..kb.eml_lite_kb import EMLLiteKB
from ..models.hypergraph import EMLHypergraph
from ..models.node import Node
from ..models.hyperedge import HyperEdge


class Decompressor:
    """Reverses the EML-SemZip compression pipeline.

    Attributes:
        kb: Optional knowledge base for edge reconstruction.
    """

    def __init__(self, kb: Optional[EMLLiteKB] = None) -> None:
        """Initialize the decompressor.

        Args:
            kb: Knowledge base for pattern-based reconstruction.
        """
        self.kb = kb

    def decompress(self, data: bytes) -> EMLHypergraph:
        """Decompress bytes back into a hypergraph.

        Steps:
        1. Parse SemPkt from bytes.
        2. Deserialize the payload.
        3. Reconstruct nodes and edges.

        Args:
            data: Compressed bytes (SemPkt format).

        Returns:
            Reconstructed EMLHypergraph.
        """
        # Step 1: Parse SemPkt
        pkt = SemPkt.from_bytes(data)

        # Step 2: Deserialize payload
        payload = deserialize(pkt.payload)

        # Step 3: Reconstruct hypergraph
        graph = EMLHypergraph()

        # Reconstruct nodes from V_star
        for node_id in payload.V_star:
            graph.add_node(Node(node_id=node_id))

        # Reconstruct edges from E_star
        for edge_data in payload.E_star:
            if isinstance(edge_data, HyperEdge):
                edge = edge_data
            elif isinstance(edge_data, dict):
                edge = HyperEdge.from_dict(edge_data)
            else:
                continue
            graph.add_edge(edge)

        # Reconstruct absorbed edges if KB is available
        if self.kb is not None and payload.absorb_records:
            rebuilt = self.kb.rebuild_edges(payload.absorb_records)
            for edge in rebuilt:
                graph.add_edge(edge)
                graph.add_node(Node(node_id=next(iter(edge.nodes))))

        return graph
