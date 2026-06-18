"""SemPkt binary format implementation.

Defines the SemPkt class for encapsulating compressed payloads.
Binary layout:
  - magic: 4 bytes ("ESZP")
  - version: 1 byte (uint8)
  - metadata_len: 4 bytes (uint32, little-endian)
  - metadata: metadata_len bytes (JSON UTF-8)
  - ans_len: 4 bytes (uint32, little-endian)
  - ans_data: ans_len bytes (ANS-encoded payload)
"""

from __future__ import annotations

import json
import struct
from typing import Any, Dict, Optional

from ..coding.ans_coder import ANSCoder
from ..constants import SEMPKT_MAGIC, SEMPKT_VERSION


class SemPkt:
    """SemPkt binary container for compressed EML hypergraph data.

    Attributes:
        payload: The raw payload bytes (serialized SemPktPayload).
        metadata: Optional metadata dictionary.
    """

    def __init__(
        self,
        payload: bytes = b"",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize a SemPkt.

        Args:
            payload: Raw payload bytes.
            metadata: Optional metadata dictionary.
        """
        self.payload = payload
        self.metadata = metadata or {}

    def to_bytes(self) -> bytes:
        """Serialize the SemPkt to binary format.

        Returns:
            Binary bytes of the SemPkt.
        """
        # Encode payload with ANS
        coder = ANSCoder()
        ans_data = coder.encode(self.payload)

        # Metadata to JSON bytes
        meta_bytes = json.dumps(
            self.metadata, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")

        # Build binary packet
        buf = bytearray()
        buf.extend(SEMPKT_MAGIC)
        buf.append(SEMPKT_VERSION & 0xFF)
        buf.extend(len(meta_bytes).to_bytes(4, "little"))
        buf.extend(meta_bytes)
        buf.extend(len(ans_data).to_bytes(4, "little"))
        buf.extend(ans_data)
        return bytes(buf)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SemPkt":
        """Deserialize a SemPkt from binary format.

        Args:
            data: Binary bytes of a SemPkt.

        Returns:
            A new SemPkt instance.

        Raises:
            ValueError: If magic bytes are invalid or version is unsupported.
        """
        # Check minimum length
        if len(data) < 13:
            raise ValueError("SemPkt data too short")

        # Parse magic
        magic = data[0:4]
        if magic != SEMPKT_MAGIC:
            raise ValueError(f"Invalid magic: {magic!r}")

        # Parse version
        version = data[4]
        if version != SEMPKT_VERSION:
            raise ValueError(f"Unsupported version: {version}")

        # Parse metadata
        meta_len = int.from_bytes(data[5:9], "little")
        meta_start = 9
        meta_end = meta_start + meta_len
        metadata = {}
        if meta_len > 0:
            meta_bytes = data[meta_start:meta_end]
            metadata = json.loads(meta_bytes.decode("utf-8"))

        # Parse ANS data
        ans_len_start = meta_end
        ans_len = int.from_bytes(
            data[ans_len_start : ans_len_start + 4], "little"
        )
        ans_start = ans_len_start + 4
        ans_data = data[ans_start : ans_start + ans_len]

        # Decode ANS to get payload
        # First parse header to get original_length
        coder = ANSCoder()
        freq, original_length = coder._parse_header(ans_data)
        payload = coder.decode(ans_data, original_length)

        return cls(payload=payload, metadata=metadata)

    @classmethod
    def is_valid(cls, data: bytes) -> bool:
        """Check if bytes represent a valid SemPkt.

        Args:
            data: Bytes to check.

        Returns:
            True if valid, False otherwise.
        """
        try:
            cls.from_bytes(data)
            return True
        except (ValueError, IndexError, json.JSONDecodeError):
            return False
