"""Merkle tree over canonical rows using the Poseidon2 sponge.

A row's 548-byte blob is packed into 18 field elements (31-byte little-endian
chunks). The row leaf binds the schema hash, the row index and the packed
elements; padding leaves bind only the schema hash and index; internal nodes
bind the level and the two children. The tree has depth 17 (capacity 2^17).

Large trees (full 131072 capacity) are built with a process pool: the leaf
layer and every node layer are independent within a layer, so they parallelise
cleanly across CPU cores.
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

# Above this many leaves we spread the (embarrassingly parallel) per-layer work
# across worker processes.
_PARALLEL_THRESHOLD = 4096


def pack_row_fields(blob: bytes) -> list[int]:
    """Pack a 548-byte row into 18 field elements (31-byte LE chunks)."""
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
    """Data-row leaf: H_P(TAG_ROW, [schemaHi, schemaLo, index, r0..r17])."""
    elements = [schema_hi, schema_lo, index, *pack_row_fields(blob)]
    return hash_poseidon(tag_row, elements)


def padding_leaf(
    index: int,
    schema_hi: int,
    schema_lo: int,
    tag_padding: int,
) -> int:
    """Padding leaf: H_P(TAG_PADDING, [schemaHi, schemaLo, index])."""
    return hash_poseidon(tag_padding, [schema_hi, schema_lo, index])


def node_hash(
    level: int,
    left: int,
    right: int,
    tag_node: int,
) -> int:
    """Internal node: H_P(TAG_NODE, [level, left, right])."""
    return hash_poseidon(tag_node, [level, left, right])


# --- Worker functions (module-level so they pickle for the process pool). ---


def _leaf_chunk_worker(args):
    """Compute leaves [lo, hi) for the data/padding boundary at ``data_count``."""
    lo, hi, data_count, blobs, schema_hi, schema_lo, tag_row, tag_padding = args
    out = []
    for index in range(lo, hi):
        if index < data_count:
            out.append(row_leaf(index, blobs[index], schema_hi, schema_lo, tag_row))
        else:
            out.append(padding_leaf(index, schema_hi, schema_lo, tag_padding))
    return out


def _node_chunk_worker(args):
    """Hash the (left, right) pairs in one slice of a node layer."""
    level, slice_pairs, tag_node = args
    return [
        node_hash(level, left, right, tag_node) for left, right in slice_pairs
    ]


def _chunks(total: int, chunk: int):
    """Yield (lo, hi) bounds splitting [0, total) into ``chunk``-sized pieces."""
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
    """Build the data root for ``row_blobs`` padded up to ``capacity`` leaves."""
    if len(row_blobs) > capacity:
        raise ValueError(f"row count {len(row_blobs)} exceeds capacity {capacity}")

    row_blobs = list(row_blobs)
    use_parallel = capacity >= _PARALLEL_THRESHOLD and os.cpu_count() and os.cpu_count() > 1

    # Layer 0: data leaves then padding leaves.
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

    # Reduce pairwise up to the root; level participates in every node hash.
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
    """Spread the leaf layer across worker processes."""
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
    """Spread one node layer across worker processes."""
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

