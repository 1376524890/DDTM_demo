#!/usr/bin/env python3
"""Generate the canonical G1 test-vector manifest.

Python is the **golden** generator: it encodes every positive case, computes
the Poseidon2 row leaves and the Merkle data root, and writes ``manifest.json``
plus the ``.bin`` blobs. Negative cases (NaN / ±Inf) record only the expected
rejection code — no blob is emitted. Large "generated" cases store the
deterministic generator parameters and the expected root instead of a giant
binary.

Each small positive case uses a small tree capacity (the leaf / node primitives
are capacity-agnostic, so a capacity-8 tree exercises the same code as a
capacity-131072 tree). Only the scale cases use the full 131072 capacity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from experiments.g1 import reference as R
from experiments.g1.row_codec import CanonicalRow, encode_row, make_padding_row

REPO_ROOT = Path(__file__).resolve().parents[2]
VECTORS_DIR = REPO_ROOT / "experiments" / "vectors"
GENERATED_DIR = VECTORS_DIR / "generated"
DEFINITIONS_DIR = VECTORS_DIR / "definitions"

MASK_ZERO = b"\x00" * 16
MASK_FF = b"\xff" * 16


def _blob_sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _row(row_id, timestamp, features, mask, label, valid) -> bytes:
    """Build an encoded blob from already-int32 features."""
    return encode_row(
        CanonicalRow(
            row_id=row_id,
            timestamp=timestamp,
            features=tuple(int(f) for f in features),
            missing_mask=mask,
            label=label,
            valid=valid,
        )
    )


def _q(value: float) -> int:
    """Quantize a single float (used for boundary cases)."""
    return R.quantize_features([value])[0]


def generated_features(i: int) -> list[int]:
    """Deterministic synthetic-v1 feature vector (re-implemented in every lang)."""
    return [((i + 1) * (j + 1)) & 0xFFFF for j in range(128)]


def build_positive_cases() -> list[dict]:
    """Define every small positive case as (id, capacity, [blobs])."""
    raw = []

    def add(case_id, capacity, blobs, note=""):
        raw.append({"id": case_id, "capacity": capacity, "blobs": blobs, "note": note})

    z = [0] * 128
    add("tc01_all_zeros", 2,
        [_row(0, 1700000000, z, MASK_ZERO, 1, 1)])
    add("tc02_negative_label", 2,
        [_row(0, 1700000000, z, MASK_ZERO, -1, 1)])
    m3 = bytearray(MASK_ZERO)
    m3[0] |= 0x01
    m3[1] |= 0x04
    add("tc03_missing_features", 2,
        [_row(0, 1700000000, z, bytes(m3), 1, 1)])
    add("tc04_padding_row", 2,
        [encode_row(make_padding_row(0))])
    add("tc05_two_row_tree", 2,
        [_row(0, 1700000000, [65536] + z[1:], MASK_ZERO, 1, 1),
         _row(1, 1700000001, [131072] + z[1:], MASK_ZERO, -1, 1)])
    add("tc06_row_order", 2,
        [_row(0, 1700000000, [65536] + z[1:], MASK_ZERO, 1, 1),
         _row(1, 1700000001, [131072] + z[1:], MASK_ZERO, -1, 1)])
    add("tc07_int32_max", 2,
        [_row(0, 1700000000, [2147483647] + z[1:], MASK_ZERO, 1, 1)])
    add("tc08_int32_min", 2,
        [_row(0, 1700000000, [-2147483648] + z[1:], MASK_ZERO, -1, 1)])
    add("tc09_q16_pos_boundary", 2,
        [_row(0, 1700000000, [_q(1.0)] + [_q((2**16 - 1) / 2**16)] + z[2:], MASK_ZERO, 1, 1)])
    add("tc10_q16_neg_boundary", 2,
        [_row(0, 1700000000, [_q(-1.0)] + [_q(-(2**16 - 1) / 2**16)] + z[2:], MASK_ZERO, -1, 1)])
    add("tc11_identical_rows", 2,
        [_row(0, 1700000000, [65536] + z[1:], MASK_ZERO, 1, 1),
         _row(1, 1700000000, [65536] + z[1:], MASK_ZERO, 1, 1)])
    add("tc12_single_bit_mutation", 2,
        [_row(0, 1700000000, z, MASK_ZERO, 1, 1),
         _row(1, 1700000000, [1] + z[1:], MASK_ZERO, 1, 1)])
    add("tc13_label_mutation", 2,
        [_row(0, 1700000000, [65536] + z[1:], MASK_ZERO, 1, 1),
         _row(1, 1700000000, [65536] + z[1:], MASK_ZERO, -1, 1)])
    add("tc14_same_data_diff_rowid", 2,
        [_row(0, 1700000000, [100000] + z[1:], MASK_ZERO, 1, 1),
         _row(1, 1700000000, [100000] + z[1:], MASK_ZERO, 1, 1)])
    m15 = bytearray(MASK_ZERO)
    m15[0] |= 0x01
    add("tc15_missing_vs_zero", 2,
        [_row(0, 1700000000, z, MASK_ZERO, 1, 1),
         _row(1, 1700000000, z, bytes(m15), 1, 1)])
    add("tc16_four_row_tree", 4,
        [_row(i, 1700000000 + i, [(i + 1) * 65536] + z[1:], MASK_ZERO,
              1 if i % 2 == 0 else -1, 1) for i in range(4)])
    add("tc17_timestamp_distinct", 8,
        [_row(i, 1700000000 + i * 1000, z, MASK_ZERO, 1, 1) for i in range(3)])
    return raw


def build_negative_definitions() -> list[dict]:
    """Write the negative-case input definitions and return manifest entries."""
    DEFINITIONS_DIR.mkdir(parents=True, exist_ok=True)
    cases = [
        ("neg01_nan_reject", "NaN", float("nan")),
        ("neg02_positive_infinity_reject", "+Inf", float("inf")),
        ("neg03_negative_infinity_reject", "-Inf", float("-inf")),
    ]
    entries = []
    for case_id, label, value in cases:
        definition = {
            "id": case_id,
            "kind": "negative",
            "row": {
                "row_id": 0,
                "timestamp": 1700000000,
                "features": ["__sentinel__"] + [0.0] * 127,
                "feature_sentinel": label,
                "missing_mask_hex": "00" * 16,
                "label": 1,
                "valid": 1,
            },
            "expected_error": "NON_FINITE_FEATURE",
        }
        path = DEFINITIONS_DIR / f"{case_id}.json"
        path.write_text(json.dumps(definition, indent=2), encoding="utf-8")
        entries.append({
            "id": case_id,
            "kind": "negative",
            "input": f"definitions/{case_id}.json",
            "expected_error": "NON_FINITE_FEATURE",
        })
    return entries


def materialize_positive(case: dict) -> dict:
    """Encode blobs, compute leaves + root, write .bin, return manifest entry."""
    blobs = case["blobs"]
    capacity = case["capacity"]
    blob_all = b"".join(blobs)
    bin_path = GENERATED_DIR / f"{case['id']}.bin"
    bin_path.write_bytes(blob_all)

    leaves = [R.row_leaf_for_blob(i, b) for i, b in enumerate(blobs)]
    root = R.data_root(blobs, capacity=capacity)

    return {
        "id": case["id"],
        "kind": "positive",
        "row_count": len(blobs),
        "capacity": capacity,
        "blob": f"generated/{case['id']}.bin",
        "blob_sha256": _blob_sha256(blob_all),
        "expected_row_leaves": [R.hex0x(x) for x in leaves],
        "expected_data_root": R.hex0x(root),
        "note": case.get("note", ""),
    }


def materialize_generated(case_id, row_count, capacity, seed) -> dict:
    """Generate a large synthetic dataset, compute its root (no .bin stored)."""
    blobs = [
        _row(i, 1700000000 + i, generated_features(i), MASK_ZERO,
              1 if i % 2 == 0 else -1, 1)
        for i in range(row_count)
    ]
    root = R.data_root(blobs, capacity=capacity)
    first_leaf = R.row_leaf_for_blob(0, blobs[0])
    return {
        "id": case_id,
        "kind": "generated",
        "generator": "synthetic-v1",
        "seed": seed,
        "row_count": row_count,
        "capacity": capacity,
        "expected_data_root": R.hex0x(root),
        "expected_first_leaf": R.hex0x(first_leaf),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--large-rows", type=int, default=8000,
                        help="row count for the tc18 large/generated case")
    parser.add_argument("--capacity-rows", type=int, default=1000,
                        help="data row count for the tc19 capacity case")
    parser.add_argument("--capacity", type=int, default=8192,
                        help="Merkle tree capacity for the large/generated cases "
                             "(production uses 131072 via the identical code path)")
    args = parser.parse_args()

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    print("Encoding positive cases...")
    cases = [materialize_positive(c) for c in build_positive_cases()]

    print("Writing negative definitions...")
    cases.extend(build_negative_definitions())

    print(f"Generating tc18 large case ({args.large_rows} rows, cap {args.capacity})...")
    cases.append(materialize_generated(
        "tc18_large_generated", args.large_rows, args.capacity, seed=20260731))

    print(f"Generating tc19 capacity case ({args.capacity_rows} rows, cap {args.capacity})...")
    cases.append(materialize_generated(
        "tc19_capacity_root", args.capacity_rows, args.capacity, seed=20260731))

    manifest = {
        "protocol": "DDTM-QAS",
        "version": 1,
        "canonical_specification": "DDTM-CANONICAL-V1",
        "poseidon_parameters": "poseidon2-bn254-v1",
        "schema_sha256": R.SCHEMA_SHA256,
        "schema_hi": R.hex0x(R.SCHEMA_HI),
        "schema_lo": R.hex0x(R.SCHEMA_LO),
        "cases": cases,
    }
    manifest_path = VECTORS_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    pos = sum(1 for c in cases if c["kind"] == "positive")
    neg = sum(1 for c in cases if c["kind"] == "negative")
    gen = sum(1 for c in cases if c["kind"] == "generated")
    print(f"\nmanifest written: {manifest_path}")
    print(f"cases: {pos} positive, {neg} negative, {gen} generated (total {len(cases)})")


if __name__ == "__main__":
    main()
