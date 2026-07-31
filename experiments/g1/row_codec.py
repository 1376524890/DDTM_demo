"""Canonical 548-byte row codec (row-layout-v1), little-endian.

Layout:

    offset 0   row_id     uint64
    offset 8   timestamp  uint64
    offset 16  features   int32[128]   (512 bytes)
    offset 528 missing_mask uint8[16]
    offset 544 label      int8
    offset 545 valid      uint8
    offset 546 reserved   uint16  (== 0)

Encode and decode are exact inverses; both validate the field constraints.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

ROW_SIZE = 548
FEATURE_COUNT = 128
MASK_SIZE = 16

VALID_LABELS = (-1, 1)


@dataclass(frozen=True)
class CanonicalRow:
    """A validated canonical row. ``features`` are already-quantized int32."""

    row_id: int
    timestamp: int
    features: tuple[int, ...]
    missing_mask: bytes
    label: int
    valid: int

    def validate(self) -> None:
        if len(self.features) != FEATURE_COUNT:
            raise ValueError("Expected 128 features")
        if len(self.missing_mask) != MASK_SIZE:
            raise ValueError("Expected 16-byte missing mask")
        if self.valid == 1 and self.label not in VALID_LABELS:
            raise ValueError("data row label must be -1 or +1")
        if self.valid not in (0, 1):
            raise ValueError("valid must be 0 or 1")
        if self.row_id < 0:
            raise ValueError("row_id must be non-negative")
        if self.timestamp < 0:
            raise ValueError("timestamp must be non-negative")
        for feature in self.features:
            if not -(1 << 31) <= feature < (1 << 31):
                raise OverflowError("feature outside int32")


def encode_row(row: CanonicalRow) -> bytes:
    """Serialize a canonical row to exactly 548 bytes."""
    row.validate()

    output = bytearray(ROW_SIZE)

    struct.pack_into("<Q", output, 0, row.row_id)
    struct.pack_into("<Q", output, 8, row.timestamp)

    for index, feature in enumerate(row.features):
        struct.pack_into("<i", output, 16 + index * 4, feature)

    output[528:544] = row.missing_mask
    struct.pack_into("<b", output, 544, row.label)
    struct.pack_into("<B", output, 545, row.valid)
    struct.pack_into("<H", output, 546, 0)  # reserved == 0

    assert len(output) == ROW_SIZE, "Incorrect row size"
    return bytes(output)


def decode_row(blob: bytes) -> CanonicalRow:
    """Parse 548 bytes into a validated CanonicalRow."""
    if len(blob) != ROW_SIZE:
        raise ValueError(f"Expected {ROW_SIZE} bytes, got {len(blob)}")

    reserved = struct.unpack_from("<H", blob, 546)[0]
    if reserved != 0:
        raise ValueError("reserved must be zero")

    row_id = struct.unpack_from("<Q", blob, 0)[0]
    timestamp = struct.unpack_from("<Q", blob, 8)[0]
    features = tuple(
        struct.unpack_from("<i", blob, 16 + i * 4)[0] for i in range(FEATURE_COUNT)
    )
    missing_mask = bytes(blob[528:544])
    label = struct.unpack_from("<b", blob, 544)[0]
    valid = struct.unpack_from("<B", blob, 545)[0]

    row = CanonicalRow(
        row_id=row_id,
        timestamp=timestamp,
        features=features,
        missing_mask=missing_mask,
        label=label,
        valid=valid,
    )
    row.validate()
    return row


def make_padding_row(leaf_index: int) -> CanonicalRow:
    """Build the deterministic padding row placed at ``leaf_index``."""
    return CanonicalRow(
        row_id=leaf_index,
        timestamp=0,
        features=tuple(0 for _ in range(FEATURE_COUNT)),
        missing_mask=b"\xff" * MASK_SIZE,
        label=-1,
        valid=0,
    )
