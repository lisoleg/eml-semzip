"""
Differentiable Compression Module for EML-SemZip.

Implements a neural compression model where the ANS encoding step
is replaced with a differentiable approximation using softmax-based
probability prediction. Supports end-to-end gradient optimization.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Differentiable ANS Core
# ---------------------------------------------------------------------------

class DifferentiableANS:
    """Differentiable approximation of ANS using softmax probabilities.

    Instead of discrete ANS encoding, computes the expected code length
    as negative log-likelihood under predicted distributions.
    Fully differentiable via PyTorch autograd.

    Attributes:
        num_symbols: Number of discrete symbols (default 256 for bytes).
        temperature: Softmax temperature for probability sharpening.
    """

    def __init__(self, num_symbols: int = 256, temperature: float = 1.0) -> None:
        """Initialize the differentiable ANS coder.

        Args:
            num_symbols: Number of symbols in the alphabet.
            temperature: Temperature for probability distribution.
        """
        self.num_symbols = num_symbols
        self.temperature = temperature

    def compute_expected_length(self, logits: torch.Tensor) -> torch.Tensor:
        """Compute expected code length (in bits) for a batch of symbol logits.

        Uses the formula: E[length] = -sum(p_i * log2(p_i))
        where p_i = softmax(logits / temperature).

        Args:
            logits: Tensor of shape (batch, num_symbols), raw logits.

        Returns:
            Tensor of shape (batch,) — expected code length per symbol.
        """
        probs = F.softmax(logits / self.temperature, dim=-1)
        # Add small epsilon for numerical stability
        eps = 1e-10
        log_probs = torch.log(probs + eps)
        # Negative log-likelihood in bits
        length = -torch.sum(probs * log_probs, dim=-1) / math.log(2)
        return length

    def compute_loss(
        self, logits: torch.Tensor, targets: torch.Tensor
    ) -> torch.Tensor:
        """Compute the compression loss (cross-entropy in bits).

        This is the differentiable surrogate for ANS encoding cost.

        Args:
            logits: Tensor of shape (batch, num_symbols).
            targets: Tensor of shape (batch,) with symbol indices.

        Returns:
            Scalar loss tensor (average bits per symbol).
        """
        probs = F.softmax(logits / self.temperature, dim=-1)
        eps = 1e-10
        # Gather the probability of each target
        target_probs = probs.gather(1, targets.unsqueeze(1)).squeeze(1)
        # Negative log2 likelihood
        loss = -torch.log(target_probs + eps) / math.log(2)
        return loss.mean()

    def encode_symbol(
        self, logits: torch.Tensor, symbol: int
    ) -> torch.Tensor:
        """Compute the CODELENGTH for a single symbol (forward, differentiable).

        Args:
            logits: Tensor of shape (num_symbols,) or (1, num_symbols).
            symbol: Integer symbol index.

        Returns:
            Scalar tensor: -log2(p(symbol)).
        """
        if logits.dim() == 1:
            logits = logits.unsqueeze(0)
        probs = F.softmax(logits / self.temperature, dim=-1)
        eps = 1e-10
        p = probs[0, symbol]
        return -torch.log(p + eps) / math.log(2)

    def get_probabilities(self, logits: torch.Tensor) -> torch.Tensor:
        """Get the probability distribution from logits.

        Args:
            logits: Tensor of shape (batch, num_symbols).

        Returns:
            Probability tensor of same shape.
        """
        return F.softmax(logits / self.temperature, dim=-1)


# ---------------------------------------------------------------------------
# Neural Compression Model
# ---------------------------------------------------------------------------

class NeuralCompressionModel(nn.Module):
    """Neural network that learns to compress hypergraph data.

    Takes hypergraph features as input and predicts symbol probabilities
    for ANS encoding. The model is trained end-to-end by minimizing
    the expected code length.

    Attributes:
        input_dim: Dimension of input features.
        hidden_dims: List of hidden layer sizes.
        num_symbols: Number of output symbols.
        temperature: Softmax temperature.
    """

    def __init__(
        self,
        input_dim: int = 64,
        hidden_dims: Optional[List[int]] = None,
        num_symbols: int = 256,
        temperature: float = 1.0,
    ) -> None:
        """Initialize the neural compression model.

        Args:
            input_dim: Input feature dimension.
            hidden_dims: List of hidden layer sizes (default [128, 256, 128]).
            num_symbols: Number of output symbols (256 for byte-level).
            temperature: Softmax temperature.
        """
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [128, 256, 128]
        self.temperature = temperature
        self.num_symbols = num_symbols

        layers: List[nn.Module] = []
        prev = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.1))
            prev = h
        layers.append(nn.Linear(prev, num_symbols))
        self.network = nn.Sequential(*layers)
        self.ans = DifferentiableANS(num_symbols, temperature)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass: compute symbol logits.

        Args:
            x: Input tensor of shape (batch, input_dim).

        Returns:
            Logits tensor of shape (batch, num_symbols).
        """
        return self.network(x)

    def compute_compression_loss(
        self, features: torch.Tensor, targets: torch.Tensor
    ) -> torch.Tensor:
        """Compute end-to-end compression loss.

        Args:
            features: Input features (batch, input_dim).
            targets: Target symbols (batch,).

        Returns:
            Scalar loss.
        """
        logits = self.forward(features)
        return self.ans.compute_loss(logits, targets)

    def expected_bits(self, features: torch.Tensor) -> torch.Tensor:
        """Compute expected bits per symbol for the given features.

        Args:
            features: Input features (batch, input_dim).

        Returns:
            Tensor of shape (batch,) — expected bits per symbol.
        """
        logits = self.forward(features)
        return self.ans.compute_expected_length(logits)

    def compress_batch(
        self, features: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compress a batch: return (logits, expected_bits).

        Args:
            features: Input features (batch, input_dim).

        Returns:
            Tuple of (logits, expected_bits).
        """
        logits = self.forward(features)
        bits = self.ans.compute_expected_length(logits)
        return logits, bits

    def get_compression_ratio(
        self, features: torch.Tensor, original_bits: int = 8
    ) -> float:
        """Estimate compression ratio vs. original bit depth.

        Args:
            features: Input features.
            original_bits: Original bits per symbol (8 for bytes).

        Returns:
            Estimated compression ratio (original_bits / avg_expected_bits).
        """
        with torch.no_grad():
            expected = self.expected_bits(features)
            avg_bits = expected.mean().item()
        return original_bits / max(avg_bits, 0.01)


# ---------------------------------------------------------------------------
# Hypergraph Feature Extractor
# ---------------------------------------------------------------------------

class HypergraphFeatureExtractor(nn.Module):
    """Extracts learnable feature vectors from EMLHypergraph objects.

    Converts hypergraph structure (node attributes, edge predicates,
    topological features) into fixed-size feature vectors suitable for
    neural compression.

    Attributes:
        embed_dim: Dimension of the output feature vector.
        predicate_embedding: Learnable embedding for predicate types.
        attr_embedding: Learnable embedding for attribute types.
    """

    def __init__(
        self,
        embed_dim: int = 64,
        max_predicates: int = 128,
        max_attr_types: int = 128,
    ) -> None:
        """Initialize the feature extractor.

        Args:
            embed_dim: Output feature dimension.
            max_predicates: Max number of predicate types (for embedding).
            max_attr_types: Max number of attribute types (for embedding).
        """
        super().__init__()
        self.embed_dim = embed_dim
        self.predicate_embedding = nn.Embedding(max_predicates, embed_dim // 4)
        self.attr_embedding = nn.Embedding(max_attr_types, embed_dim // 4)
        # MLP to combine features into embed_dim
        self.proj = nn.Sequential(
            nn.Linear(embed_dim + 8, embed_dim),
            nn.ReLU(),
            nn.Linear(embed_dim, embed_dim),
        )

    def forward(self, graphs: List[Any]) -> torch.Tensor:
        """Extract feature vectors from a list of hypergraphs.

        Args:
            graphs: List of EMLHypergraph objects (or dicts).

        Returns:
            Tensor of shape (total_edges, embed_dim).
        """
        features = []
        for g in graphs:
            g_feat = self._extract_graph_features(g)
            features.append(g_feat)
        if features:
            return torch.cat(features, dim=0)
        return torch.empty(0, self.embed_dim)

    def _extract_graph_features(self, graph: Any) -> torch.Tensor:
        """Extract features for a single hypergraph.

        Args:
            graph: EMLHypergraph or dict with 'edges' key.

        Returns:
            Tensor of shape (num_edges, embed_dim).
        """
        # Handle both EMLHypergraph objects and dicts
        if hasattr(graph, "E"):
            edges = list(graph.E)
        elif isinstance(graph, dict):
            edges = graph.get("edges", [])
        else:
            edges = []

        feats = []
        for edge in edges:
            f = self._edge_to_feature(edge)
            feats.append(f)
        if feats:
            return torch.stack(feats)
        return torch.empty(0, self.embed_dim)

    def _edge_to_feature(self, edge: Any) -> torch.Tensor:
        """Convert a single edge to feature vector.

        Args:
            edge: HyperEdge object or dict.

        Returns:
            Feature tensor of size embed_dim + 8.
        """
        # Predicate embedding
        pred_id = abs(hash(getattr(edge, "predicate", ""))) % 128
        pred_emb = self.predicate_embedding(
            torch.tensor([pred_id], dtype=torch.long)
        ).squeeze(0)

        # Attribute embedding (average of attr_type embeddings)
        attr_types = getattr(edge, "attr_types", set())
        if attr_types:
            attr_ids = [abs(hash(a)) % 128 for a in attr_types]
            attr_emb = self.attr_embedding(
                torch.tensor(attr_ids, dtype=torch.long)
            ).mean(dim=0)
        else:
            attr_emb = torch.zeros(self.embed_dim // 4)

        # Structural features
        num_nodes = len(getattr(edge, "nodes", set()))
        I_value = getattr(edge, "I_value", 0.5)
        base_weight = getattr(edge, "base_weight", 1.0)
        dir_factor = getattr(edge, "dir_factor", 1.0)

        # Concatenate all features
        struct_feat = torch.tensor(
            [
                num_nodes / 10.0,
                I_value,
                base_weight,
                dir_factor,
                len(attr_types) / 10.0,
                1.0 if num_nodes > 2 else 0.0,
                1.0 if num_nodes > 3 else 0.0,
                1.0 if num_nodes > 4 else 0.0,
            ],
            dtype=torch.float32,
        )
        combined = torch.cat([pred_emb, attr_emb, struct_feat])
        return self.proj(combined.unsqueeze(0)).squeeze(0)


# ---------------------------------------------------------------------------
# End-to-End Trainable Compressor
# ---------------------------------------------------------------------------

class DiffCompressor:
    """End-to-end trainable compressor for EML-SemZip.

    Combines HypergraphFeatureExtractor and NeuralCompressionModel
    into a single trainable pipeline. Supports gradient-based optimization
    of the compression ratio.

    Attributes:
        extractor: Feature extractor module.
        model: Neural compression model.
        ans: Differentiable ANS coder.
        learning_rate: Optimizer learning rate.
        optimizer: Adam optimizer.
    """

    def __init__(
        self,
        embed_dim: int = 64,
        hidden_dims: Optional[List[int]] = None,
        temperature: float = 1.0,
        learning_rate: float = 1e-3,
    ) -> None:
        """Initialize the differentiable compressor.

        Args:
            embed_dim: Feature embedding dimension.
            hidden_dims: Hidden dims for neural model.
            temperature: Softmax temperature.
            learning_rate: Learning rate for optimizer.
        """
        self.extractor = HypergraphFeatureExtractor(embed_dim=embed_dim)
        self.model = NeuralCompressionModel(
            input_dim=embed_dim,
            hidden_dims=hidden_dims,
            num_symbols=256,
            temperature=temperature,
        )
        self.ans = DifferentiableANS(256, temperature)
        self.learning_rate = learning_rate
        self.optimizer = torch.optim.Adam(
            list(self.extractor.parameters()) + list(self.model.parameters()),
            lr=learning_rate,
        )
        self.loss_history: List[float] = []

    def compress(
        self, graphs: List[Any], targets: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """Compress hypergraphs and compute differentiable loss.

        Args:
            graphs: List of EMLHypergraph objects.
            targets: Optional target symbols (if None, uses edge predicates).

        Returns:
            Tuple of (loss_tensor, stats_dict).
        """
        features = self.extractor(graphs)
        if features.shape[0] == 0:
            return torch.tensor(0.0, requires_grad=True), {"bits": 0.0}

        # Auto-generate targets from predicate hashes if not provided
        if targets is None:
            targets = self._auto_targets(graphs, features.shape[0])

        loss = self.model.compute_compression_loss(features, targets)
        bits = self.model.expected_bits(features).detach().cpu().numpy()
        stats = {
            "loss": loss.item(),
            "avg_bits": float(bits.mean()),
            "min_bits": float(bits.min()),
            "max_bits": float(bits.max()),
            "num_edges": features.shape[0],
        }
        return loss, stats

    def train_step(
        self, graphs: List[Any], targets: Optional[torch.Tensor] = None
    ) -> Dict[str, Any]:
        """Single training step: forward + backward + optimize.

        Args:
            graphs: List of EMLHypergraph objects.
            targets: Optional target symbols.

        Returns:
            Stats dict.
        """
        self.optimizer.zero_grad()
        loss, stats = self.compress(graphs, targets)
        loss.backward()
        self.optimizer.step()
        self.loss_history.append(stats["loss"])
        return stats

    def train_epoch(
        self,
        graph_batches: List[List[Any]],
        epochs: int = 1,
    ) -> List[float]:
        """Train for multiple epochs over graph batches.

        Args:
            graph_batches: List of graph batches.
            epochs: Number of epochs.

        Returns:
            List of average loss per epoch.
        """
        epoch_losses = []
        for ep in range(epochs):
            total_loss = 0.0
            count = 0
            for batch in graph_batches:
                stats = self.train_step(batch)
                total_loss += stats["loss"]
                count += 1
            avg = total_loss / max(count, 1)
            epoch_losses.append(avg)
        return epoch_losses

    def evaluate(self, graphs: List[Any]) -> Dict[str, Any]:
        """Evaluate compression performance without gradient update.

        Args:
            graphs: List of EMLHypergraph objects.

        Returns:
            Stats dict.
        """
        self.extractor.eval()
        self.model.eval()
        with torch.no_grad():
            features = self.extractor(graphs)
            if features.shape[0] == 0:
                return {"avg_bits": 0.0, "num_edges": 0}
            bits = self.model.expected_bits(features)
            ratio = self.model.get_compression_ratio(features)
            return {
                "avg_bits": float(bits.mean()),
                "compression_ratio": ratio,
                "num_edges": features.shape[0],
            }

    def _auto_targets(self, graphs: List[Any], n: int) -> torch.Tensor:
        """Auto-generate training targets from graph data.

        Args:
            graphs: List of hypergraphs.
            n: Number of targets needed.

        Returns:
            Target tensor of shape (n,).
        """
        targets = []
        for g in graphs:
            if hasattr(g, "E"):
                edges = list(g.E)
            elif isinstance(g, dict):
                edges = g.get("edges", [])
            else:
                edges = []
            for e in edges:
                pred = getattr(e, "predicate", "")
                # Hash predicate to symbol ID
                tid = abs(hash(pred)) % 256
                targets.append(tid)
        if not targets:
            # Dummy targets
            return torch.zeros(n, dtype=torch.long)
        t = torch.tensor(targets[:n], dtype=torch.long)
        if len(t) < n:
            t = torch.cat([t, torch.zeros(n - len(t), dtype=torch.long)])
        return t[:n]

    def save(self, path: str) -> None:
        """Save model weights to disk.

        Args:
            path: Output file path (.pt).
        """
        torch.save(
            {
                "extractor": self.extractor.state_dict(),
                "model": self.model.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "loss_history": self.loss_history,
            },
            path,
        )

    def load(self, path: str) -> None:
        """Load model weights from disk.

        Args:
            path: Input file path (.pt).
        """
        ckpt = torch.load(path, map_location="cpu")
        self.extractor.load_state_dict(ckpt["extractor"])
        self.model.load_state_dict(ckpt["model"])
        self.optimizer.load_state_dict(ckpt["optimizer"])
        self.loss_history = ckpt.get("loss_history", [])


# ---------------------------------------------------------------------------
# Utility: Differentiable Compression Report
# ---------------------------------------------------------------------------

def diff_compress_report(compressor: DiffCompressor, graphs: List[Any]) -> str:
    """Generate a text report of differentiable compression results.

    Args:
        compressor: Trained DiffCompressor instance.
        graphs: List of hypergraphs to evaluate.

    Returns:
        Multi-line report string.
    """
    stats = compressor.evaluate(graphs)
    lines = [
        "=== Differentiable Compression Report ===",
        f"  Graphs evaluated: {len(graphs)}",
        f"  Total edges: {stats.get('num_edges', 'N/A')}",
        f"  Avg bits/symbol: {stats.get('avg_bits', 0):.4f}",
        f"  Compression ratio (vs. 8-bit): {stats.get('compression_ratio', 0):.2f}x",
        f"  Loss history (last 5): {compressor.loss_history[-5:]}",
    ]
    return "\n".join(lines)
