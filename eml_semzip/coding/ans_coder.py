"""rANS (range Asymmetric Numeral Systems) byte-level entropy coder.

Implements a streaming rANS encoder/decoder for byte-level data.
The encoded format consists of:
  - Frequency table: 256 * 2 bytes (uint16 little-endian per symbol)
  - Original length: 4 bytes (uint32 little-endian)
  - rANS stream: remaining bytes

The rANS algorithm processes symbols in reverse order during encoding
and forward order during decoding, using a renormalization scheme
that emits/reads 16-bit words to keep the state bounded.
"""

from __future__ import annotations

from typing import List, Tuple


class ANSCoder:
    """rANS byte-level entropy coder using 16-bit renormalization.

    The coder uses a frequency table of size M = 2^16 = 65536. Each byte
    symbol (0-255) is assigned a normalized frequency such that the total
    equals M. The rANS state is an integer that grows during encoding and
    is periodically renormalized by emitting 16-bit words.
    """

    M: int = 1 << 16  # 65536
    MASK: int = M - 1  # 0xFFFF
    STATE_BYTES: int = 8  # bytes for final state storage

    def encode(self, data: bytes) -> bytes:
        """Encode bytes using rANS.

        Args:
            data: The input bytes to encode.

        Returns:
            Encoded bytes including frequency table header and rANS stream.
        """
        if not data:
            return self._build_header([0] * 256, 0)

        # Count byte frequencies
        counts: List[int] = [0] * 256
        for b in data:
            counts[b] += 1

        # Normalize to M
        freq = self._normalize(counts)

        # Build cumulative frequency table
        cum = self._build_cumulative(freq)

        # rANS encode
        state = self.M
        buf = bytearray()

        for b in reversed(data):
            f = freq[b]
            if f == 0:
                # Should not happen with correct normalization
                continue
            # Renormalize: emit 16-bit words while state is too large
            while state >= (f << 16):
                buf.append(state & 0xFF)
                buf.append((state >> 8) & 0xFF)
                state >>= 16
            # rANS encoding step
            state = ((state // f) << 16) + cum[b] + (state % f)

        # Write final state (little-endian, STATE_BYTES bytes)
        for i in range(self.STATE_BYTES):
            buf.append((state >> (i * 8)) & 0xFF)

        # Reverse buffer so decoder reads forward
        buf.reverse()

        # Build header + payload
        return self._build_header(freq, len(data)) + bytes(buf)

    def decode(self, data: bytes, original_length: int) -> bytes:
        """Decode rANS-encoded bytes back to original.

        Args:
            data: The encoded bytes (header + rANS stream).
            original_length: The number of bytes in the original data.

        Returns:
            The decoded original bytes.
        """
        if original_length == 0:
            return b""

        # Parse header
        freq, _ = self._parse_header(data)

        # Build cumulative frequency table
        cum = self._build_cumulative(freq)

        # Build symbol lookup table
        lookup = self._build_lookup(freq, cum)

        # Payload starts after header
        header_size = 256 * 2 + 4
        payload = data[header_size:]

        # Read final state from first STATE_BYTES bytes (big-endian after reversal)
        state = 0
        for i in range(self.STATE_BYTES):
            state = (state << 8) | payload[i]
        pos = self.STATE_BYTES

        output = bytearray()

        for _ in range(original_length):
            slot = state & self.MASK
            s = lookup[slot]
            output.append(s)
            f = freq[s]
            state = (state >> 16) * f + (slot - cum[s])
            # Renormalize: read 16-bit words while state is too small
            while state < self.M and pos + 1 < len(payload):
                word = (payload[pos] << 8) | payload[pos + 1]
                state = (state << 16) | word
                pos += 2

        return bytes(output)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize(self, counts: List[int]) -> List[int]:
        """Normalize raw counts to sum to M.

        Ensures each symbol that appears in the data gets frequency >= 1.
        Handles the single-symbol case by allocating a dummy symbol.

        Args:
            counts: Raw byte frequency counts.

        Returns:
            Normalized frequency list summing to M.
        """
        total = sum(counts)
        if total == 0:
            return [0] * 256

        active = [i for i in range(256) if counts[i] > 0]

        # Special case: only one symbol
        if len(active) == 1:
            freq = [0] * 256
            freq[active[0]] = self.M - 1
            dummy = (active[0] + 1) % 256
            freq[dummy] = 1
            return freq

        # Initial allocation
        freq = [0] * 256
        for i in active:
            freq[i] = max(1, round(counts[i] * self.M / total))

        # Adjust to make sum exactly M
        diff = self.M - sum(freq)
        if diff != 0:
            idx = 0
            max_iterations = self.M * 2
            while diff != 0 and max_iterations > 0:
                i = active[idx % len(active)]
                if diff > 0:
                    freq[i] += 1
                    diff -= 1
                else:
                    if freq[i] > 1:
                        freq[i] -= 1
                        diff += 1
                idx += 1
                max_iterations -= 1

        return freq

    def _build_cumulative(self, freq: List[int]) -> List[int]:
        """Build cumulative frequency table from frequency table.

        Args:
            freq: Frequency list for symbols 0-255.

        Returns:
            Cumulative frequency list where cum[i] = sum(freq[0:i]).
        """
        cum = [0] * 256
        for i in range(1, 256):
            cum[i] = cum[i - 1] + freq[i - 1]
        return cum

    def _build_lookup(self, freq: List[int], cum: List[int]) -> List[int]:
        """Build a symbol lookup table indexed by slot value.

        For each slot value v in [0, M), the table maps v to the symbol
        whose cumulative range [cum[s], cum[s]+freq[s]) contains v.

        Args:
            freq: Frequency list.
            cum: Cumulative frequency list.

        Returns:
            A list of size M mapping slot values to symbol indices.
        """
        lookup = [0] * self.M
        for s in range(256):
            for v in range(cum[s], cum[s] + freq[s]):
                if 0 <= v < self.M:
                    lookup[v] = s
        return lookup

    def _build_header(self, freq: List[int], original_length: int) -> bytes:
        """Build the frequency table header.

        Format: 256 * 2 bytes (uint16 LE per symbol) + 4 bytes (uint32 LE).

        Args:
            freq: Frequency list.
            original_length: Original data length.

        Returns:
            Header bytes.
        """
        header = bytearray()
        for i in range(256):
            header.append(freq[i] & 0xFF)
            header.append((freq[i] >> 8) & 0xFF)
        header.extend(original_length.to_bytes(4, "little"))
        return bytes(header)

    def _parse_header(self, data: bytes) -> Tuple[List[int], int]:
        """Parse the frequency table header.

        Args:
            data: Encoded data including header.

        Returns:
            A tuple of (frequency_list, original_length).
        """
        freq = [0] * 256
        for i in range(256):
            freq[i] = data[i * 2] | (data[i * 2 + 1] << 8)
        original_length = int.from_bytes(data[512:516], "little")
        return freq, original_length
