"""Built-in example KB and factory functions."""

from __future__ import annotations

from ..models.hyperedge import HyperEdge
from .eml_lite_kb import EMLLiteKB


def create_empty_kb() -> EMLLiteKB:
    """Create an empty EML-Lite KB.

    Returns:
        A new empty :class:`EMLLiteKB` instance.
    """
    return EMLLiteKB()


def create_builtin_kb() -> EMLLiteKB:
    """Create a built-in KB with common predicate patterns.

    The built-in KB contains frequently used predicate patterns for
    isomorphic absorption during compression. Covers person relations,
    organization relations, spatial relations, event relations, and
    attribute relations.

    Returns:
        A new :class:`EMLLiteKB` instance with pre-loaded patterns.
    """
    kb = EMLLiteKB()

    # === Person Relations (人物关系) ===

    # Pattern: "knows" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_knows_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="knows",
        attr_types={"name", "type"},
    ))

    # Pattern: "friend_of" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_friend_of_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="friend_of",
        attr_types={"name", "type"},
    ))

    # Pattern: "family_of" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_family_of_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="family_of",
        attr_types={"name", "type", "role"},
    ))

    # Pattern: "colleague_of" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_colleague_of_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="colleague_of",
        attr_types={"name", "type"},
    ))

    # === Organization Relations (组织关系) ===

    # Pattern: "works_at" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_works_at_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="works_at",
        attr_types={"name", "type"},
    ))

    # Pattern: "member_of" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_member_of_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="member_of",
        attr_types={"name", "type"},
    ))

    # Pattern: "founder_of" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_founder_of_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="founder_of",
        attr_types={"name", "type"},
    ))

    # === Spatial Relations (地理关系) ===

    # Pattern: "located_in" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_located_in_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="located_in",
        attr_types={"name", "type"},
    ))

    # Pattern: "near" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_near_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="near",
        attr_types={"name", "type", "distance"},
    ))

    # Pattern: "part_of" predicate with 3 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_partof_3",
        nodes={"n_a", "n_b", "n_c"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="part_of",
        attr_types={"name", "type"},
    ))

    # === Event Relations (事件关系) ===

    # Pattern: "participated_in" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_participated_in_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="participated_in",
        attr_types={"name", "type", "date"},
    ))

    # Pattern: "occurred_at" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_occurred_at_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="occurred_at",
        attr_types={"name", "type", "date"},
    ))

    # === Attribute Relations (属性关系) ===

    # Pattern: "has_attribute" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_has_attribute_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="has_attribute",
        attr_types={"name", "type"},
    ))

    # Pattern: "is_a" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_is_a_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="is_a",
        attr_types={"name", "type"},
    ))

    # Pattern: "instance_of" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_instance_of_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="instance_of",
        attr_types={"name", "type"},
    ))

    # === Causal Relations (因果关系) ===

    # Pattern: "causes" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_causes_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="causes",
        attr_types={"name", "type"},
    ))

    # Pattern: "related_to" predicate with 2 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_related_2",
        nodes={"n_a", "n_b"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="related_to",
        attr_types={"name"},
    ))

    # Pattern: "interacts_with" predicate with 3 nodes
    kb.add_pattern(HyperEdge(
        edge_id="pat_interacts_3",
        nodes={"n_a", "n_b", "n_c"},
        I_value=1.0,
        base_weight=1.0,
        dir_factor=1.0,
        predicate="interacts_with",
        attr_types={"name", "type"},
    ))

    kb.compute_sig()
    return kb


def create_sample_kb() -> EMLLiteKB:
    """Create a sample KB with diverse patterns for testing.

    Returns a KB with 15+ patterns covering common knowledge graph
    predicates. Useful for demonstrations and integration tests.

    Returns:
        A new :class:`EMLLiteKB` instance with sample patterns.
    """
    return create_builtin_kb()
