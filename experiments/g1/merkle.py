"""基于 Poseidon2 sponge 的规范行 Merkle 树。

一行的 548 字节 blob 被打包成 18 个域元素（31 字节小端分块）。行叶子绑定 schema
哈希、行索引与这些打包元素；padding 叶子只绑定 schema 哈希与索引；内部节点绑定
层级与两个孩子。树深度为 17（容量 2^17）。

大树（完整 131072 容量）用进程池构建：叶子层与每个节点层在层内彼此独立，因此可以
干净地跨 CPU 核并行。
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Sequence

from .poseidon import hash_poseidon

ROW_BYTES = 548
PACK_CHUNK = 31
PACKED_ELEMENT_COUNT = 18  # ceil(548 / 31)
TREE_DEPTH = 17
TREE_CAPACITY = 1 << TREE_DEPTH

# 超过这么多叶子时，把（高度可并行的）逐层工作分散到 worker 进程。
_PARALLEL_THRESHOLD = 4096


def pack_row_fields(blob: bytes) -> list[int]:
    """把 548 字节行打包成 18 个域元素（31 字节小端分块）。"""
    if len(blob) != ROW_BYTES:
        raise ValueError("Expected 548-byte row")
    return [
        int.from_bytes(blob[offset : offset + PACK_CHUNK], "little")
        for offset in range(0, len(blob), PACK_CHUNK)
    ]


def row_leaf(
    index: int,
    blob: bytes,
    schema_hi: int,
    schema_lo: int,
    tag_row: int,
) -> int:
    """数据行叶子：H_P(TAG_ROW, [schemaHi, schemaLo, index, r0..r17])。"""
    elements = [schema_hi, schema_lo, index, *pack_row_fields(blob)]
    return hash_poseidon(tag_row, elements)


def padding_leaf(
    index: int,
    schema_hi: int,
    schema_lo: int,
    tag_padding: int,
) -> int:
    """padding 叶子：H_P(TAG_PADDING, [schemaHi, schemaLo, index])。"""
    return hash_poseidon(tag_padding, [schema_hi, schema_lo, index])


def node_hash(
    level: int,
    left: int,
    right: int,
    tag_node: int,
) -> int:
    """内部节点：H_P(TAG_NODE, [level, left, right])。"""
    return hash_poseidon(tag_node, [level, left, right])


# --- worker 函数（模块级，以便能被进程池 pickle）---


def _leaf_chunk_worker(args):
    """为 data/padding 边界 ``data_count`` 计算 [lo, hi) 的叶子。"""
    lo, hi, data_count, blobs, schema_hi, schema_lo, tag_row, tag_padding = args
    out = []
    for index in range(lo, hi):
        if index < data_count:
            out.append(row_leaf(index, blobs[index], schema_hi, schema_lo, tag_row))
        else:
            out.append(padding_leaf(index, schema_hi, schema_lo, tag_padding))
    return out


def _node_chunk_worker(args):
    """哈希某个节点层的一个切片中的 (left, right) 对。"""
    level, slice_pairs, tag_node = args
    return [
        node_hash(level, left, right, tag_node) for left, right in slice_pairs
    ]


def _chunks(total: int, chunk: int):
    """以 ``chunk`` 大小切分 [0, total)，产出 (lo, hi) 边界。"""
    for lo in range(0, total, chunk):
        yield lo, min(lo + chunk, total)


def build_root(
    row_blobs: Sequence[bytes],
    schema_hi: int,
    schema_lo: int,
    tag_row: int,
    tag_padding: int,
    tag_node: int,
    capacity: int = TREE_CAPACITY,
) -> int:
    """为 ``row_blobs``（padding 到 ``capacity`` 叶子）构建数据根。"""
    if len(row_blobs) > capacity:
        raise ValueError(f"row count {len(row_blobs)} exceeds capacity {capacity}")

    row_blobs = list(row_blobs)
    use_parallel = capacity >= _PARALLEL_THRESHOLD and os.cpu_count() and os.cpu_count() > 1

    # 第 0 层：数据叶 + padding 叶。
    if use_parallel:
        leaves = _parallel_leaves(
            row_blobs, capacity, schema_hi, schema_lo, tag_row, tag_padding
        )
    else:
        leaves = [
            row_leaf(i, row_blobs[i], schema_hi, schema_lo, tag_row)
            for i in range(len(row_blobs))
        ]
        leaves.extend(
            padding_leaf(i, schema_hi, schema_lo, tag_padding)
            for i in range(len(row_blobs), capacity)
        )

    # 两两归约到根；层级参与每一个节点哈希。
    level = 0
    while len(leaves) > 1:
        pairs = list(zip(leaves[0::2], leaves[1::2]))
        if use_parallel and len(pairs) >= _PARALLEL_THRESHOLD:
            leaves = _parallel_nodes(level, pairs, tag_node)
        else:
            leaves = [node_hash(level, l, r, tag_node) for l, r in pairs]
        level += 1

    return leaves[0]


def _parallel_leaves(blobs, capacity, schema_hi, schema_lo, tag_row, tag_padding):
    """把叶子层分散到 worker 进程。"""
    workers = min(os.cpu_count() or 1, 8)
    chunk = max(1, capacity // (workers * 4))
    jobs = [
        (lo, hi, len(blobs), blobs, schema_hi, schema_lo, tag_row, tag_padding)
        for lo, hi in _chunks(capacity, chunk)
    ]
    leaves = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(_leaf_chunk_worker, jobs):
            leaves.extend(part)
    return leaves


def _parallel_nodes(level, pairs, tag_node):
    """把一个节点层分散到 worker 进程。"""
    workers = min(os.cpu_count() or 1, 8)
    chunk = max(1, len(pairs) // (workers * 4))
    jobs = [
        (level, pairs[lo:hi], tag_node) for lo, hi in _chunks(len(pairs), chunk)
    ]
    out = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for part in pool.map(_node_chunk_worker, jobs):
            out.extend(part)
    return out
