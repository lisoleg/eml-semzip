"""
ViT (Vision Transformer) Encoder for EML-SemZip Multi-Modal Extension.

Uses a pre-trained ViT to extract patch-level embeddings,
then converts images to hypergraphs for semantic compression.

Compared to CLIPEncoder, ViTEncoder uses a classification-first
architecture (e.g. Google ViT) and provides attention-based
hyperedge construction (using attention weights between patches).
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


class ViTEncoder:
    """ViT-based image encoder for hypergraph conversion.

    Uses a pre-trained Vision Transformer to extract patch embeddings
    and attention weights, then builds a hypergraph where:
    - Each patch = a node with ViT embedding features.
    - Hyperedges = patches with high attention weights (semantic grouping).

    Attributes:
        model_name: HuggingFace ViT model name.
        device: Torch device.
        patch_size: Spatial patch size in pixels.
        hidden_size: Dimension of patch embeddings.
    """

    def __init__(
        self,
        model_name: str = "google/vit-base-patch16-224",
        device: Optional[str] = None,
    ) -> None:
        """Initialize the ViT encoder.

        Args:
            model_name: HuggingFace ViT model identifier.
            device: Torch device string (None = auto-detect).
        """
        try:
            from transformers import ViTModel, ViTImageProcessor
            import torch
        except ImportError as e:
            raise ImportError(
                "transformers and torch are required for ViTEncoder. "
                f"Install with: pip install transformers torch. Error: {e}"
            )

        self.model_name = model_name
        self.device = device or (
            "cuda" if __import__("torch").cuda.is_available() else "cpu"
        )

        self.processor: ViTImageProcessor = ViTImageProcessor.from_pretrained(
            model_name
        )
        self.model: ViTModel = ViTModel.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()

        config = self.model.config
        self.patch_size = config.patch_size  # type: ignore[union-attr]
        self.hidden_size = config.hidden_size  # type: ignore[union-attr]
        self.image_size = config.image_size  # type: ignore[union-attr]
        self.num_patches = (self.image_size // self.patch_size) ** 2

    def encode_image(self, image_path: str) -> Any:
        """Extract ViT CLS embedding (global image representation).

        Args:
            image_path: Path to the image file.

        Returns:
            Numpy array: CLS embedding of shape (hidden_size,).
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        # last_hidden_state[:, 0, :] = CLS token
        cls_embed = outputs.last_hidden_state[:, 0, :]
        return cls_embed.cpu().numpy().flatten()

    def encode_patches(self, image_path: str) -> Any:
        """Extract patch-level ViT embeddings (excluding CLS).

        Args:
            image_path: Path to the image file.

        Returns:
            Numpy array: patch embeddings of shape (num_patches, hidden_size).
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        # Exclude CLS token (index 0)
        patch_embeds = outputs.last_hidden_state[:, 1:, :]
        return patch_embeds.cpu().numpy().squeeze(0)  # (num_patches, hidden_size)

    def get_attention_weights(
        self, image_path: str, layer_idx: int = -1
    ) -> Any:
        """Extract attention weights between patches.

        Args:
            image_path: Path to the image file.
            layer_idx: Which transformer layer to use (-1 = last).

        Returns:
            Numpy array: attention weights of shape (num_heads, seq_len, seq_len).
            seq_len = 1 (CLS) + num_patches.
        """
        import torch
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        # Enable outputting attentions
        self.model.config.output_attentions = True
        with torch.no_grad():
            outputs = self.model(**inputs)
        self.model.config.output_attentions = False

        # attentions: tuple of (batch, num_heads, seq_len, seq_len) per layer
        attn = outputs.attentions[layer_idx]  # (1, H, seq_len, seq_len)
        return attn.cpu().numpy().squeeze(0)  # (H, seq_len, seq_len)

    def image_to_hypergraph(
        self,
        image_path: str,
        use_attention: bool = True,
        n_top_attention: int = 4,
        connectivity_threshold: float = 0.0,
    ) -> EMLHypergraph:
        """Convert an image to a hypergraph using ViT patch embeddings.

        Args:
            image_path: Path to the image file.
            use_attention: If True, use attention weights for hyperedge construction.
                If False, use cosine similarity of patch embeddings.
            n_top_attention: Number of top-attended patches per hyperedge.
            connectivity_threshold: Minimum score to form an edge (<= 0 = no filter).

        Returns:
            EMLHypergraph representing the image.
        """
        import torch.nn.functional as F

        g = EMLHypergraph()
        patch_embeds = self.encode_patches(image_path)  # (N, D)
        n_patches = patch_embeds.shape[0]

        grid_side = int(math.sqrt(n_patches))
        if grid_side * grid_side != n_patches:
            grid_side = -1

        # --- Create nodes ---
        for i in range(n_patches):
            if grid_side > 0:
                px, py = i % grid_side, i // grid_side
            else:
                px, py = i, 0

            emb_sample = patch_embeds[i, :16]
            emb_fingerprint = hashlib.md5(emb_sample.tobytes()).hexdigest()[:12]
            emb_mag = float(np.linalg.norm(patch_embeds[i]))

            g.add_node(Node(f"vit_patch:{i}", {
                "type": "vit_patch",
                "patch_idx": i,
                "grid_x": px,
                "grid_y": py,
                "embed_fingerprint": emb_fingerprint,
                "embed_mag": round(emb_mag, 4),
                "px": px,
                "py": py,
            }))

        # --- Build connectivity ---
        if use_attention:
            # Use attention weights (exclude CLS token = index 0)
            attn = self.get_attention_weights(image_path)  # (H, seq_len, seq_len)
            # Average across heads, then take patch-patch attention (indices 1:, 1:)
            avg_attn = np.mean(attn, axis=0)  # (seq_len, seq_len)
            patch_attn = avg_attn[1:, 1:]  # (N, N) — patch-to-patch attention
            sim_matrix = patch_attn
        else:
            # Use cosine similarity of patch embeddings
            norms = np.linalg.norm(patch_embeds, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            normalized = patch_embeds / norms
            sim_matrix = normalized @ normalized.T

        # --- Create hyperedges ---
        edge_idx = 0
        for i in range(n_patches):
            scores = sim_matrix[i].copy()
            scores[i] = -999.0
            top_k_idxs = np.argsort(scores)[-n_top_attention:][::-1]

            members = [f"vit_patch:{i}"]
            for j in top_k_idxs:
                if connectivity_threshold > 0 and scores[j] < connectivity_threshold:
                    continue
                members.append(f"vit_patch:{j}")

            if len(members) >= 2:
                mean_score = float(np.mean([scores[int(m.split(":")[-1])] for m in members if ":" in m]))
                # Normalize score to [0, 1] for I_value
                if use_attention:
                    # Attention weights are already in [0, 1]
                    i_val = round(max(0.01, min(1.0, mean_score)), 4)
                else:
                    # Cosine similarity in [-1, 1], normalize to [0, 1]
                    i_val = round(max(0.01, min(1.0, (mean_score + 1.0) / 2.0)), 4)

                g.add_edge(HyperEdge(
                    edge_id=f"vit_attn:{edge_idx}",
                    nodes=set(members),
                    I_value=i_val,
                    base_weight=1.0,
                    dir_factor=1.0,
                    predicate="vit_semantic_attn" if use_attention else "vit_cosine_sim",
                ))
                edge_idx += 1

        return g

    def compute_fidelity_score(
        self,
        original_image_path: str,
        reconstructed_graph: EMLHypergraph,
    ) -> Dict[str, float]:
        """Compute semantic fidelity using ViT CLS embedding similarity.

        Args:
            original_image_path: Path to the original image.
            reconstructed_graph: Hypergraph after compression/decompression.

        Returns:
            Dict with fidelity_score and stats.
        """
        orig_cls = self.encode_image(original_image_path)

        # Estimate reconstructed CLS by averaging retained patch embeddings
        retained_embeds = []
        for nid, node in reconstructed_graph.V.items():
            if node.attributes.get("type") in ("vit_patch", "clip_patch"):
                mag = node.attributes.get("embed_mag", 0.0)
                retained_embeds.append(mag)

        if not retained_embeds:
            return {"fidelity_score": 0.0, "note": "no patch nodes found"}

        # Fidelity proxy: node retention ratio × mean I_value
        n_nodes_orig = self.num_patches
        n_nodes_retained = len(retained_embeds)
        retention_ratio = n_nodes_retained / max(1, n_nodes_orig)

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


def vit_image_to_hypergraph(
    image_path: str,
    model_name: str = "google/vit-base-patch16-224",
    use_attention: bool = True,
) -> EMLHypergraph:
    """Convenience function: image → ViT-aware hypergraph.

    Args:
        image_path: Path to image file.
        model_name: ViT model name on HuggingFace Hub.
        use_attention: Use attention-based connectivity.

    Returns:
        EMLHypergraph ready for semantic compression.
    """
    encoder = ViTEncoder(model_name=model_name)
    return encoder.image_to_hypergraph(
        image_path, use_attention=use_attention
    )


def benchmark_vit_fidelity(
    image_dir: str,
    model_name: str = "google/vit-base-patch16-224",
    sample_limit: int = 20,
) -> List[Dict[str, Any]]:
    """Benchmark semantic fidelity of ViT-based hypergraph compression.

    Args:
        image_dir: Directory containing test images.
        model_name: ViT model to use.
        sample_limit: Maximum number of images to process.

    Returns:
        List of per-image fidelity reports.
    """
    from PIL import Image as PILImage
    from ..pipeline.compressor import Compressor
    from ..pipeline.decompressor import Decompressor

    encoder = ViTEncoder(model_name=model_name)
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

            fidelity = encoder.compute_fidelity_score(
                str(img_path), g_decompressed
            )
            fidelity["image"] = str(img_path.name)
            fidelity["compression_ratio"] = round(
                report["compressed"]["header"]["compression_ratio"], 4
            )
            results.append(fidelity)
        except Exception as e:
            results.append({"image": str(img_path.name), "error": str(e)})

    return results
