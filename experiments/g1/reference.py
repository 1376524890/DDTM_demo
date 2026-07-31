"""高层参考门面：行 → 编码 blob → 叶子 → 数据根。

这是 Go、Rust、gnark 验证器必须逐位重现的唯一 Python 实现。它把量化、行编解码、
schema 哈希、域标签与 Poseidon2 Merkle 树串联起来。
"""
from __future__ import annotations

from typing import Sequence

from . import merkle, poseidon, quantize, row_codec, schema


class CanonicalizationError(Exception):
    """携带一个规范错误码（见 specs/error-codes-v1.json）。"""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


# 冻结的 schema + 域标签，由规范文件一次性算出。
SCHEMA_HI, SCHEMA_LO = schema.schema_halves()
SCHEMA_SHA256 = schema.schema_sha256_hex()
_TAGS = schema.domain_tags(poseidon.MODULUS)
TAG_ROW = _TAGS["DDTM_ROW_V1"]
TAG_PADDING = _TAGS["DDTM_PADDING_V1"]
TAG_NODE = _TAGS["DDTM_NODE_V1"]


def quantize_features(values: Sequence[float]) -> tuple[int, ...]:
    """把一列有限浮点数量化为裁剪后的 Q16.16 int32。

    遇到 NaN/Inf 抛出 :class:`CanonicalizationError`（``NON_FINITE_FEATURE``）。
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
    """量化（若是浮点）并把一行编码为其 548 字节规范 blob。"""
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
    """为单个已编码 blob 计算行叶子。"""
    return merkle.row_leaf(index, blob, SCHEMA_HI, SCHEMA_LO, TAG_ROW)


def padding_leaf_for(index: int) -> int:
    return merkle.padding_leaf(index, SCHEMA_HI, SCHEMA_LO, TAG_PADDING)


def data_root(row_blobs: Sequence[bytes], capacity: int = merkle.TREE_CAPACITY) -> int:
    """为一列已编码 blob 计算数据根。"""
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
    """把域元素渲染为 0x 前缀的小写十六进制字符串。"""
    return "0x" + format(value, "x")
