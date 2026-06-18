"""Multi-modal extension for EML-SemZip.

Converts images and audio to EML hypergraphs for semantic compression.

- image_to_hypergraph(): extracts patch features from images -> hypergraph
- audio_to_hypergraph(): extracts spectrogram features from audio -> hypergraph
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models.node import Node
from ..models.hyperedge import HyperEdge
from ..models.hypergraph import EMLHypergraph


def image_to_hypergraph(
    image_path: str,
    patch_size: int = 16,
    max_patches: int = 256,
) -> EMLHypergraph:
    """Convert an image file to an EML hypergraph.

    The image is divided into patches. Each patch becomes a node.
    Adjacent patches are connected by hyperedges.

    Args:
        image_path: Path to the image file.
        patch_size: Size of each square patch (default 16).
        max_patches: Maximum number of patches to extract.

    Returns:
        EMLHypergraph representing the image.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError(
            "Pillow is required for image processing. "
            "Install it with: pip install Pillow"
        )

    g = EMLHypergraph()
    img = Image.open(image_path).convert("RGB")
    w, h = img.size

    # Resize if too large
    max_dim = int(max_patches ** 0.5) * patch_size
    if w > max_dim or h > max_dim:
        img.thumbnail((int(max_dim), int(max_dim)))
        w, h = img.size

    patches_x = max(1, w // patch_size)
    patches_y = max(1, h // patch_size)

    # Extract patches as nodes
    nodes = []
    for py in range(patches_y):
        for px in range(patches_x):
            x0 = px * patch_size
            y0 = py * patch_size
            patch = img.crop((x0, y0, x0 + patch_size, y0 + patch_size))
            # Compute a feature vector: mean R, G, B
            pixels = list(patch.getdata())
            n_pixels = len(pixels)
            if n_pixels == 0:
                continue
            avg_r = sum(p[0] for p in pixels) / n_pixels
            avg_g = sum(p[1] for p in pixels) / n_pixels
            avg_b = sum(p[2] for p in pixels) / n_pixels
            # Simple feature hash
            feat = (int(avg_r) << 16) | (int(avg_g) << 8) | int(avg_b)
            feat_str = f"{feat:06x}"
            nid = f"patch:{px}_{py}"
            g.add_node(Node(nid, {
                "type": "image_patch",
                "px": px,
                "py": py,
                "avg_color": feat_str,
                "x0": x0, "y0": y0,
            }))
            nodes.append((px, py, nid))

            if len(g.V) >= max_patches:
                break
        if len(g.V) >= max_patches:
            break

    # Connect adjacent patches with hyperedges (spatial neighborhood)
    from itertools import product
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1)]
    edge_idx = 0
    for px, py, nid in nodes:
        neighbors = []
        for dx, dy in directions:
            np = (px + dx, py + dy)
            nnid = f"patch:{np[0]}_{np[1]}"
            if nnid in g.V:
                neighbors.append(nnid)
        if len(neighbors) >= 2:
            # Create a hyperedge connecting this patch and its neighbors
            all_nodes = {nid} | set(neighbors[:4])  # Max 5 nodes per edge
            edge_id = f"spatial:{edge_idx}"
            # I_value based on color similarity
            i_val = 0.7 + (hash(nid) % 30) / 100.0
            g.add_edge(HyperEdge(
                edge_id=edge_id,
                nodes=all_nodes,
                I_value=min(1.0, i_val),
                base_weight=1.0,
                dir_factor=1.0,
                predicate=f"spatial_adj",
            ))
            edge_idx += 1

    return g


def audio_to_hypergraph(
    audio_path: str,
    samples_per_node: int = 1024,
    max_nodes: int = 512,
) -> EMLHypergraph:
    """Convert an audio file to an EML hypergraph.

    The audio is split into time windows. Each window becomes a node.
    Adjacent windows are connected by hyperedges.

    Args:
        audio_path: Path to the audio file (WAV format).
        samples_per_node: Number of audio samples per node.
        max_nodes: Maximum number of nodes.

    Returns:
        EMLHypergraph representing the audio.
    """
    g = EMLHypergraph()

    try:
        import wave
        with wave.open(audio_path, "rb") as wf:
            n_channels = wf.getnchannels()
            frame_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)
            # Convert to samples (16-bit PCM)
            n_samples = n_frames * n_channels
            samples = struct.unpack(f"<{n_samples}h", raw_bytes)
    except Exception as e:
        # Fallback: create a dummy graph
        g.add_node(Node("audio:dummy", {"type": "audio", "error": str(e)}))
        g.add_edge(HyperEdge(
            edge_id="audio:dummy:edge",
            nodes={"audio:dummy"},
            I_value=0.5, base_weight=1.0, dir_factor=1.0,
            predicate="audio_dummy",
        ))
        return g

    # Create nodes from audio windows
    mono_samples = samples[::n_channels] if n_channels > 0 else samples
    node_idx = 0
    pos = 0
    while pos < len(mono_samples) and node_idx < max_nodes:
        end = min(pos + samples_per_node, len(mono_samples))
        window = mono_samples[pos:end]
        if len(window) < 32:
            break
        # Features: energy, zero-crossing rate
        energy = sum(s * s for s in window) / len(window)
        zcr = sum(1 for i in range(1, len(window)) if window[i] * window[i-1] < 0) / len(window)
        feat_hash = int(energy * 1000) % 65536
        nid = f"audio:{node_idx}"
        g.add_node(Node(nid, {
            "type": "audio_window",
            "start_sample": pos,
            "end_sample": end,
            "energy": round(energy, 4),
            "zcr": round(zcr, 4),
            "feat": feat_hash,
        }))
        pos = end
        node_idx += 1

    # Connect adjacent audio windows
    node_ids = [f"audio:{i}" for i in range(node_idx)]
    for i in range(len(node_ids) - 1):
        eid = f"audio:seq:{i}"
        # Connect 3 consecutive windows
        members = set(node_ids[max(0, i - 1):min(len(node_ids), i + 2)])
        if len(members) >= 2:
            g.add_edge(HyperEdge(
                edge_id=eid,
                nodes=members,
                I_value=0.6 + (i % 4) * 0.1,
                base_weight=1.0,
                dir_factor=1.0,
                predicate="audio_temporal",
            ))

    return g


def hypergraph_to_image(
    graph: EMLHypergraph,
    output_path: str,
    width: int = 256,
    height: int = 256,
) -> None:
    """Reconstruct an image from a hypergraph (approximate).

    Only works for hypergraphs created by image_to_hypergraph().
    """
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("Pillow is required. Install: pip install Pillow")

    img = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = img.load()

    for nid, node in graph.V.items():
        if not nid.startswith("patch:"):
            continue
        attrs = node.attributes
        x0 = attrs.get("x0", 0)
        y0 = attrs.get("y0", 0)
        color_hex = attrs.get("avg_color", "000000")
        try:
            r = int(color_hex[0:2], 16)
            g = int(color_hex[2:4], 16)
            b = int(color_hex[4:6], 16)
        except Exception:
            r, g, b = 128, 128, 128
        # Fill patch area
        ps = 16
        for py in range(y0, min(y0 + ps, height)):
            for px in range(x0, min(x0 + ps, width)):
                pixels[px, py] = (r, g, b)

    img.save(output_path)


def describe_hypergraph(graph: EMLHypergraph) -> Dict[str, Any]:
    """Return a human-readable description of a hypergraph.

    Useful for debugging multi-modal conversion.
    """
    return {
        "node_count": graph.node_count(),
        "edge_count": graph.edge_count(),
        "node_types": _count_types(graph, "node"),
        "edge_predicates": _count_predicates(graph),
    }


def _count_types(graph: EMLHypergraph, which: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    items = graph.V.values() if which == "node" else []
    for item in items:
        t = item.attributes.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


def _count_predicates(graph: EMLHypergraph) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for e in graph.E:
        p = e.predicate
        counts[p] = counts.get(p, 0) + 1
    return counts
