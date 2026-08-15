"""MNIST 行确定性 canonical 二进制序列化。

对齐方案：不用 str(row)/pickle.dumps（跨版本不稳定）。MNISTRow =
    index: uint64
    label: uint8
    image: 28x28 uint8 (784 bytes, C order)

    canonical_row = uint64(index) || uint8(label) || image.tobytes(order="C")
"""

from __future__ import annotations

import struct

import numpy as np

# MNIST 图像尺寸
MNIST_H = 28
MNIST_W = 28
MNIST_FLAT = MNIST_H * MNIST_W  # 784


def canonical_mnist_row(index: int, image: np.ndarray, label: int) -> bytes:
    """序列化单行 MNIST 为确定性字节。

    Args:
        index: 行索引 (uint64)
        image: 形状 (784,) 或 (28,28)，uint8
        label: 0..9 (uint8)
    """
    arr = np.asarray(image)
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    flat = arr.reshape(-1)
    if flat.size != MNIST_FLAT:
        raise ValueError(f"MNIST 行须 {MNIST_FLAT} 像素，实际 {flat.size}")
    if not (0 <= label <= 9):
        raise ValueError(f"label 须 0..9，实际 {label}")
    if index < 0 or index > 2**64 - 1:
        raise ValueError(f"index 越界: {index}")
    head = struct.pack("<Q", int(index))  # uint64 little-endian
    lab = struct.pack("<B", int(label))  # uint8
    return head + lab + flat.tobytes(order="C")


def canonical_row_from_payload(
    payload: bytes, *, index: int | None = None, n_features: int = MNIST_FLAT,
) -> tuple[int, np.ndarray, int]:
    """从 canonical 字节解析回 (index, image, label)。"""
    if len(payload) < 9:
        raise ValueError("payload 过短")
    idx = struct.unpack("<Q", payload[:8])[0]
    label = struct.unpack("<B", payload[8:9])[0]
    img = np.frombuffer(payload[9:], dtype=np.uint8)
    if img.size != n_features:
        raise ValueError(f"图像尺寸 {img.size} != {n_features}")
    if index is not None and idx != index:
        raise ValueError(f"payload index {idx} != 期望 {index}")
    return idx, img, label


__all__ = ["canonical_mnist_row", "canonical_row_from_payload",
           "MNIST_H", "MNIST_W", "MNIST_FLAT"]
