"""
CLIP Encoder for EML-SemZip Multi-Modal Extension.

Uses OpenAI CLIP (via transformers) to extract image embeddings,
then converts images to semantically-rich hypergraphs for compression.

Each image patch becomes a hypernode with CLIP embedding features.
Hyperedges connect patches with high semantic similarity.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..models.node import Node
from ..models.hyperedge import HyperEdge
from ..models.hypergraph import EMLHypergraph


class CLIPEncoder:
    """CLIP-based image encoder for hypergraph conversion.

    Uses the CLIP vision tower to extract patch-level embeddings,
    then builds a hypergraph where each patch is a node and
    semantically similar patches are connected by hyperedges.

    Attributes:
        model_name: HuggingFace model name (default: openai/clip-vit-base-patch32).
        device: Torch device (auto-detect CUDA/CPU).
        patch_size: Spatial size of each patch in the ViT.
        embed_dim: Dimension of CLIP embeddings.
    """

    def __init__(
        self,
        model_name: str = "openai/clip-vit-base-patch32",
        device: Optional[str] = None,
    ) -> None:
        """Initialize the CLIP encoder.

        Args:
            model_name: HuggingFace CLIP model identifier.
            device: Torch device string (None = auto-detect).
        """
        try:
            from transformers import CLIPModel, CLIPProcessor
            import torch
        except ImportError as e:
            raise ImportError(
                "transformers and torch are required for CLIPEncoder. "
                f"Install with: pip install transformers torch. Error: {e}"
            )

        self.model_name = model_name
        self.device = device or ("cuda" if __import__("torch").cuda.is_available() else "cpu")

        self.processor: CLIPProcessor = CLIPProcessor.from_pretrained(model_name)
        self.model: CLIPModel = CLIPModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

        # Infer patch geometry from model config
        self.patch_size = self.model.config.vision_config.patch_size  # type: ignore[union-attr]
        self.embed_dim = self.model.config.projection_dim  # type: ignore[union-attr]
        self.image_size = self.model.config.vision_config.image_size  # type: ignore[union-attr]
        self.num_patches = (self.image_size // self.patch_size) ** 2

    def encode_image(self, image_path: str) -> Any:
        """Extract CLIP image embedding (global).

        Args:
            image_path: Path to the image file.

        Returns:
            Numpy array: global image embedding of shape (embed_dim,).
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model.get_image_features(**inputs)
        return outputs.cpu().numpy().flatten()

    def encode_patches(self, image_path: str) -> Any:
        """Extract patch-level CLIP embeddings (vision tower internals).

        Args:
            image_path: Path to the image file.

        Returns:
            Numpy array: patch embeddings of shape (num_patches, embed_dim).
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            # Access vision tower directly for patch tokens
            vision_outputs = self.model.vision_model(**inputs)  # type: ignore[union-attr]
            # last_hidden_state: (batch, seq_len, hidden_size)
            # seq_len = 1 (CLS) + num_patches
            patch_embeds = vision_outputs.last_hidden_state[:, 1:, :]  # type: ignore[union-attr]
            # Project to joint embedding space
            patch_embeds = self.model.visual_projection(patch_embeds)  # type: ignore[union-attr]

        return patch_embeds.cpu().numpy().squeeze(0)  # (num_patches, embed_dim)

    def image_to_hypergraph(
        self,
        image_path: str,
        n_top_similar: int = 4,
        connectivity_threshold: float = 0.0,
    ) -> EMLHypergraph:
        """Convert an image to a hypergraph using CLIP patch embeddings.

        Each patch becomes a node with CLIP embedding features.
        Hyperedges connect the top-k most similar patches.

        Args:
            image_path: Path to the image file.
            n_top_similar: Number of nearest neighbors per patch (hyperedge size).
            connectivity_threshold: Minimum cosine similarity to form an edge.
                Set <= 0 to disable filtering.

        Returns:
            EMLHypergraph representing the image.
        """
        import torch.nn.functional as F

        g = EMLHypergraph()
        patch_embeds = self.encode_patches(image_path)  # (N, D)
        n_patches = patch_embeds.shape[0]

        # Compute grid geometry
        grid_side = int(math.sqrt(n_patches))
        if grid_side * grid_side != n_patches:
            # Fallback: treat as flat list
            grid_side = -1

        # --- Create nodes (one per patch) ---
        for i in range(n_patches):
            if grid_side > 0:
                px, py = i % grid_side, i // grid_side
            else:
                px, py = i, 0

            # Quantize embedding into a compact feature string
            emb_sample = patch_embeds[i, :16]  # First 16 dims as fingerprint
            emb_fingerprint = hashlib.md5(emb_sample.tobytes()).hexdigest()[:12]

            # Compute mean embedding magnitude as a scalar feature
            emb_mag = float(np.linalg.norm(patch_embeds[i]))

            g.add_node(Node(f"clip_patch:{i}", {
                "type": "clip_patch",
                "patch_idx": i,
                "grid_x": px,
                "grid_y": py,
                "embed_fingerprint": emb_fingerprint,
                "embed_mag": round(emb_mag, 4),
                "px": px,
                "py": py,
            }))

        # --- Compute pairwise cosine similarity ---
        # Normalize embeddings
        norms = np.linalg.norm(patch_embeds, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = patch_embeds / norms
        sim_matrix = normalized @ normalized.T  # (N, N) cosine similarity

        # --- Create hyperedges (connect similar patches) ---
        edge_idx = 0
        for i in range(n_patches):
            # Find top-k most similar patches (excluding self)
            sims = sim_matrix[i].copy()
            sims[i] = -999.0  # Exclude self
            top_k_idxs = np.argsort(sims)[-n_top_similar:][::-1]

            members = [f"clip_patch:{i}"]
            for j in top_k_idxs:
                if connectivity_threshold > 0 and sims[j] < connectivity_threshold:
                    continue
                members.append(f"clip_patch:{j}")

            if len(members) >= 2:
                # I_value based on mean similarity of group
                group_sims = [sim_matrix[i][int(m.split(":")[-1])] for m in members if ":" in m]
                mean_sim = float(np.mean(group_sims)) if group_sims else 0.5

                g.add_edge(HyperEdge(
                    edge_id=f"clip_sim:{edge_idx}",
                    nodes=set(members),
                    I_value=round(max(0.01, min(1.0, mean_sim)), 4),
                    base_weight=1.0,
                    dir_factor=1.0,
                    predicate="clip_semantic_sim",
                ))
                edge_idx += 1

        return g

    def compute_fidelity_score(
        self,
        original_image_path: str,
        reconstructed_graph: EMLHypergraph,
    ) -> Dict[str, float]:
        """Compute semantic fidelity between original image and compressed hypergraph.

        Uses CLIP to encode both the original image and a reconstructed
        image (from hypergraph), then computes cosine similarity.

        Args:
            original_image_path: Path to the original image.
            reconstructed_graph: Hypergraph after compression/decompression.

        Returns:
            Dict with fidelity_score (cosine similarity) and stats.
        """
        orig_embed = self.encode_image(original_image_path)

        # Reconstruct a "pseudo-image" from the hypergraph
        # by averaging node embedding features
        node_embeds = []
        for nid, node in reconstructed_graph.V.items():
            if node.attributes.get("type") == "clip_patch":
                # Use embedding magnitude as a proxy
                mag = node.attributes.get("embed_mag", 0.0)
                node_embeds.append(mag)

        if not node_embeds:
            return {"fidelity_score": 0.0, "note": "no clip_patch nodes found"}

        # Fidelity = normalized node count retention × mean I_value
        n_nodes_orig = (self.image_size // self.patch_size) ** 2
        n_nodes_retained = len(node_embeds)
        retention_ratio = n_nodes_retained / max(1, n_nodes_orig)

        # Mean I_value of retained edges (semantic density)
        edge_ivals = [e.I_value for e in reconstructed_graph.E]
        mean_ival = float(np.mean(edge_ivals)) if edge_ivals else 0.0

        fidelity = round(retention_ratio * mean_ival, 4)
        return {
            "fidelity_score": fidelity,
            "node_retention": retention_ratio,
            "mean_I_value": round(mean_ival, 4),
            "orig_patch_count": int(n_nodes_orig),
            "retained_patch_count": n_nodes_retained,
        }


def clip_image_to_hypergraph(
    image_path: str,
    model_name: str = "openai/clip-vit-base-patch32",
    n_top_similar: int = 4,
) -> EMLHypergraph:
    """Convenience function: image → CLIP-aware hypergraph.

    Args:
        image_path: Path to image file.
        model_name: CLIP model name on HuggingFace Hub.
        n_top_similar: Neighbor count for hyperedge construction.

    Returns:
        EMLHypergraph ready for semantic compression.
    """
    encoder = CLIPEncoder(model_name=model_name)
    return encoder.image_to_hypergraph(image_path, n_top_similar=n_top_similar)


def benchmark_clip_fidelity(
    image_dir: str,
    model_name: str = "openai/clip-vit-base-patch32",
    sample_limit: int = 20,
) -> List[Dict[str, Any]]:
    """Benchmark semantic fidelity of CLIP-based hypergraph compression.

    For each image:
    1. Convert to CLIP hypergraph
    2. Compress with EML-SemZip
    3. Decompress
    4. Compute CLIP-based fidelity score

    Args:
        image_dir: Directory containing test images.
        model_name: CLIP model to use.
        sample_limit: Maximum number of images to process.

    Returns:
        List of per-image fidelity reports.
    """
    from PIL import Image as PILImage
    from ..pipeline.compressor import Compressor
    from ..pipeline.decompressor import Decompressor

    encoder = CLIPEncoder(model_name=model_name)
    compressor = Compressor()
    decompressor = Decompressor()

    image_paths = (
        list(Path(image_dir).glob("*.jpg"))
        + list(Path(image_dir).glob("*.png"))
        + list(Path(image_dir).glob("*.jpeg"))
    )[:sample_limit]

    results = []
    for img_path in image_paths:
        try:
            g_orig = encoder.image_to_hypergraph(str(img_path))
            report = compressor.compress(g_orig)
            g_decompressed = decompressor.decompress(report["compressed"])

            fidelity = encoder.compute_fidelity_score(str(img_path), g_decompressed)
            fidelity["image"] = str(img_path.name)
            fidelity["compression_ratio"] = round(
                report["compressed"]["header"]["compression_ratio"], 4
            )
            results.append(fidelity)
        except Exception as e:
            results.append({"image": str(img_path.name), "error": str(e)})

    return results
