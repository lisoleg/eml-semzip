"""Tests for eml_semzip.coding: ANSCoder, serializer, SemPkt."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eml_semzip.coding.ans_coder import ANSCoder
from eml_semzip.coding.serializer import (
    SemPktPayload,
    serialize,
    deserialize,
)
from eml_semzip.coding.sempkt import SemPkt
from eml_semzip.constants import SEMPKT_MAGIC, SEMPKT_VERSION
from eml_semzip.models.hyperedge import HyperEdge


class TestANSCoder(unittest.TestCase):
    """Tests for rANS entropy coder."""

    def setUp(self):
        self.coder = ANSCoder()

    def test_encode_empty(self):
        result = self.coder.encode(b"")
        self.assertTrue(len(result) > 0)

    def test_encode_decode_simple(self):
        data = b"hello world"
        encoded = self.coder.encode(data)
        decoded = self.coder.decode(encoded, len(data))
        self.assertEqual(decoded, data)

    def test_encode_decode_single_byte(self):
        data = b"\x00"
        encoded = self.coder.encode(data)
        decoded = self.coder.decode(encoded, 1)
        self.assertEqual(decoded, data)

    def test_encode_decode_repeated(self):
        data = b"aaaa" * 100
        encoded = self.coder.encode(data)
        decoded = self.coder.decode(encoded, len(data))
        self.assertEqual(decoded, data)

    def test_encode_decode_random(self):
        import random
        random.seed(42)
        data = bytes(random.randint(0, 255) for _ in range(200))
        encoded = self.coder.encode(data)
        decoded = self.coder.decode(encoded, len(data))
        self.assertEqual(decoded, data)

    def test_encode_decode_long_text(self):
        data = b"The quick brown fox jumps over the lazy dog. " * 50
        encoded = self.coder.encode(data)
        decoded = self.coder.decode(encoded, len(data))
        self.assertEqual(decoded, data)

    def test_encode_decode_utf8_text(self):
        text = "你好世界 EML压缩测试 日本語テスト"
        data = text.encode("utf-8")
        encoded = self.coder.encode(data)
        decoded = self.coder.decode(encoded, len(data))
        self.assertEqual(decoded, data)
        self.assertEqual(decoded.decode("utf-8"), text)

    def test_compression_ratio_simple(self):
        """Repeated data should compress well."""
        data = b"AAAA" * 200
        encoded = self.coder.encode(data)
        self.assertLess(len(encoded), len(data))

    def test_decode_empty(self):
        encoded = self.coder.encode(b"")
        decoded = self.coder.decode(encoded, 0)
        self.assertEqual(decoded, b"")

    def test_encode_roundtrip_large(self):
        data = os.urandom(500)
        encoded = self.coder.encode(data)
        decoded = self.coder.decode(encoded, len(data))
        self.assertEqual(decoded, data)

    def test_m_config(self):
        self.assertEqual(self.coder.M, 1 << 16)
        self.assertEqual(self.coder.MASK, 0xFFFF)
        self.assertEqual(self.coder.STATE_BYTES, 8)


class TestSemPktPayload(unittest.TestCase):
    """Tests for SemPktPayload serialization."""

    def test_create_empty(self):
        p = SemPktPayload()
        self.assertEqual(p.V_star, set())
        self.assertEqual(p.E_star, [])
        self.assertEqual(p.theta_dead, 0.0)
        self.assertEqual(p.kb_sig, "")

    def test_create_with_data(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            I_value=0.9,
            predicate="knows",
        )
        p = SemPktPayload(
            V_star={"n1", "n2"},
            E_star=[edge],
            theta_dead=0.45,
            kb_sig="abc123",
        )
        self.assertEqual(p.V_star, {"n1", "n2"})
        self.assertEqual(len(p.E_star), 1)
        self.assertEqual(p.theta_dead, 0.45)
        self.assertEqual(p.kb_sig, "abc123")

    def test_to_dict(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            I_value=0.9,
            predicate="knows",
        )
        p = SemPktPayload(
            V_star={"n2", "n1"},
            E_star=[edge],
            theta_dead=0.5,
            kb_sig="sig",
            pruned_summary=[{"edge_id": "x"}],
        )
        d = p.to_dict()
        self.assertEqual(set(d["V_star"]), {"n1", "n2"})
        self.assertEqual(len(d["E_star"]), 1)

    def test_from_dict(self):
        data = {
            "V_star": ["n1", "n2"],
            "E_star": [{
                "edge_id": "e1",
                "nodes": ["n1", "n2"],
                "I_value": 0.9,
                "predicate": "knows",
            }],
            "theta_dead": 0.4,
            "kb_sig": "test",
        }
        p = SemPktPayload.from_dict(data)
        self.assertEqual(p.V_star, {"n1", "n2"})
        self.assertEqual(len(p.E_star), 1)
        self.assertEqual(p.theta_dead, 0.4)

    def test_serialize_deserialize_roundtrip(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            I_value=0.9,
            predicate="knows",
        )
        p = SemPktPayload(
            V_star={"n1", "n2"},
            E_star=[edge],
            theta_dead=0.45,
            kb_sig="sha256...",
            pruned_summary=[{"edge_id": "pruned_e"}],
        )
        serialized = serialize(p)
        self.assertIsInstance(serialized, bytes)
        restored = deserialize(serialized)
        self.assertEqual(restored.V_star, p.V_star)
        self.assertEqual(restored.theta_dead, p.theta_dead)
        self.assertEqual(restored.kb_sig, p.kb_sig)
        self.assertEqual(len(restored.E_star), 1)
        self.assertEqual(restored.E_star[0].edge_id, "e1")
        self.assertEqual(len(restored.pruned_summary), 1)

    def test_serialize_utf8(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1"},
            predicate="测试",
        )
        p = SemPktPayload(V_star={"n1"}, E_star=[edge])
        data = serialize(p)
        restored = deserialize(data)
        self.assertEqual(restored.E_star[0].predicate, "测试")


class TestSemPkt(unittest.TestCase):
    """Tests for SemPkt binary format."""

    def test_create(self):
        pkt = SemPkt(payload=b"test payload")
        self.assertEqual(pkt.payload, b"test payload")
        self.assertEqual(pkt.metadata, {})

    def test_create_with_metadata(self):
        pkt = SemPkt(payload=b"data", metadata={"version": 1})
        self.assertEqual(pkt.payload, b"data")
        self.assertEqual(pkt.metadata, {"version": 1})

    def test_to_bytes_and_from_bytes(self):
        pkt = SemPkt(
            payload=b"hello eml semzip test payload content",
            metadata={"author": "test"},
        )
        binary = pkt.to_bytes()
        self.assertIsInstance(binary, bytes)
        self.assertTrue(len(binary) > 0)

        restored = SemPkt.from_bytes(binary)
        self.assertEqual(restored.payload, pkt.payload)
        self.assertEqual(restored.metadata, pkt.metadata)

    def test_from_bytes_empty_payload(self):
        pkt = SemPkt(payload=b"")
        binary = pkt.to_bytes()
        restored = SemPkt.from_bytes(binary)
        self.assertEqual(restored.payload, b"")

    def test_magic_bytes(self):
        pkt = SemPkt(payload=b"test")
        binary = pkt.to_bytes()
        self.assertTrue(binary.startswith(SEMPKT_MAGIC))

    def test_version_byte(self):
        pkt = SemPkt(payload=b"test")
        binary = pkt.to_bytes()
        self.assertEqual(binary[4], SEMPKT_VERSION & 0xFF)

    def test_from_bytes_invalid_magic(self):
        invalid = b"BAD0" + bytes(100)
        with self.assertRaises(ValueError):
            SemPkt.from_bytes(invalid)

    def test_from_bytes_too_short(self):
        with self.assertRaises(ValueError):
            SemPkt.from_bytes(b"short")

    def test_is_valid_true(self):
        pkt = SemPkt(payload=b"valid test")
        binary = pkt.to_bytes()
        self.assertTrue(SemPkt.is_valid(binary))

    def test_is_valid_false(self):
        self.assertFalse(SemPkt.is_valid(b"not valid data"))
        self.assertFalse(SemPkt.is_valid(b""))

    def test_roundtrip_large_payload(self):
        """Test with a larger, more complex payload."""
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2", "n3"},
            I_value=0.9,
            predicate="collaborates",
        )
        payload_obj = SemPktPayload(
            V_star={"n1", "n2", "n3"},
            E_star=[edge],
            theta_dead=0.5,
            kb_sig="sig123",
        )
        serialized = serialize(payload_obj)
        pkt = SemPkt(payload=serialized)
        binary = pkt.to_bytes()
        restored = SemPkt.from_bytes(binary)
        self.assertEqual(restored.payload, serialized)


if __name__ == "__main__":
    unittest.main()
