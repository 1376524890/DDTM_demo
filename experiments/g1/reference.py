"""High-level reference facade: rows → encoded blob → leaves → data root.

This is the single Python implementation that the Go, Rust and gnark verifiers
must reproduce bit-for-bit. It wires quantization, the row codec, the schema
hash, the domain tags and the Poseidon2 Merkle tree together.
"""
from __future__ import annotations

from typing import Sequence

from . import merkle, poseidon, quantize, row_codec, schema


class CanonicalizationError(Exception):
    """Carries a canonical error code (see specs/error-codes-v1.json)."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


# Frozen schema + domain tags, computed once from the spec files.
SCHEMA_HI, SCHEMA_LO = schema.schema_halves()
SCHEMA_SHA256 = schema.schema_sha256_hex()
_TAGS = schema.domain_tags(poseidon.MODULUS)
TAG_ROW = _TAGS["DDTM_ROW_V1"]
TAG_PADDING = _TAGS["DDTM_PADDING_V1"]
TAG_NODE = _TAGS["DDTM_NODE_V1"]


def quantize_features(values: Sequence[float]) -> tuple[int, ...]:
    """Quantize a list of finite floats to clamped Q16.16 int32.

    Raises :class:`CanonicalizationError` (``NON_FINITE_FEATURE``) on NaN/Inf.
    """
    try:
        return tuple(quantize.quantize(v) for v in values)
    except quantize.NonFiniteFeature as exc:
        raise CanonicalizationError("NON_FINITE_FEATURE", str(exc)) from exc


def encode_row(
    row_id: int,
    timestamp: int,
    features: Sequence[float] | Sequence[int],
    missing_mask: bytes,
    label: int,
    valid: int,
) -> bytes:
    """Quantize (if floats) and encode a row to its 548-byte canonical blob."""
    if features and isinstance(features[0], float):
        qfeatures = quantize_features(features)
    else:
        qfeatures = tuple(int(f) for f in features)
    row = row_codec.CanonicalRow(
        row_id=row_id,
        timestamp=timestamp,
        features=qfeatures,
        missing_mask=missing_mask,
        label=label,
        valid=valid,
    )
    return row_codec.encode_row(row)


def row_leaf_for_blob(index: int, blob: bytes) -> int:
    """Compute the row leaf for one already-encoded blob."""
    return merkle.row_leaf(index, blob, SCHEMA_HI, SCHEMA_LO, TAG_ROW)


def padding_leaf_for(index: int) -> int:
    return merkle.padding_leaf(index, SCHEMA_HI, SCHEMA_LO, TAG_PADDING)


def data_root(row_blobs: Sequence[bytes], capacity: int = merkle.TREE_CAPACITY) -> int:
    """Compute the data root for a list of encoded blobs."""
    return merkle.build_root(
        row_blobs,
        SCHEMA_HI,
        SCHEMA_LO,
        TAG_ROW,
        TAG_PADDING,
        TAG_NODE,
        capacity=capacity,
    )


def hex0x(value: int) -> str:
    """Render a field element as a 0x-prefixed lower-case hex string."""
    return "0x" + format(value, "x")
