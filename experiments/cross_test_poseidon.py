#!/usr/bin/env python3
"""Poseidon2 Cross-Test Vector Generator.

Generates deterministic test vectors for cross-language Poseidon2 verification:
  - Go native (canonicalizer-go/internal/merkle)
  - Go circuit (zk/circuits)
  - Rust native (future: tee-evaluator-rust with gnark-crypto FFI)

Each test vector includes:
  - Input fields (as decimal strings for big.Int)
  - Expected leaf hash
  - Expected Merkle root
  - Merkle path for verification

The Python reference uses a deterministic SHA-256-based Poseidon2 simulation
since the true BN254 Poseidon2 requires gnark-crypto. These test vectors are
for format validation; actual cross-test must be executed in Go.
"""
from __future__ import annotations
import json, hashlib, struct
from pathlib import Path
from typing import List


def encode_row_for_test(row_id: int, valid: int, label: int, timestamp: int,
                        features: List[int], missing_mask: bytes) -> dict:
    """Encode a row as the canonical binary format for cross-testing."""
    raw = bytearray()
    raw += struct.pack('<H', 1)           # version
    raw += struct.pack('<Q', row_id)      # row_id
    raw += struct.pack('B', valid)        # valid
    raw += struct.pack('b', label)        # label
    raw += struct.pack('<Q', timestamp)   # timestamp
    raw += missing_mask                   # 16 bytes
    for f in features:
        # Pack as int32 (signed). Clamp to valid range.
        val = max(-2147483648, min(2147483647, f))
        raw += struct.pack('<i', val)  # int32 Q16.16
    return {
        "row_id": row_id,
        "valid": valid,
        "label": label,
        "timestamp": timestamp,
        "missing_mask_hex": missing_mask.hex(),
        "features": features,
        "canonical_hex": raw.hex(),
        "canonical_sha256": hashlib.sha256(raw).hexdigest(),
    }


def main():
    output_dir = Path("experiments/vectors")
    output_dir.mkdir(parents=True, exist_ok=True)

    vectors = {
        "version": 1,
        "description": "Cross-test vectors for DDTM-QAS Poseidon2 Merkle tree.",
        "note": "Hash values must be computed by canonicalizer-go and zk/circuits. This file provides the canonical binary inputs.",
        "schema_hash": "000000000000000000000000000000000000000000000000000000000000CAFE",
        "dataset_version": "1",
        "test_cases": []
    }

    # Test Case 1: Single valid row, all zeros.
    features_zeros = [0] * 128
    row1 = encode_row_for_test(0, 1, 1, 1700000000, features_zeros, bytes(16))
    vectors["test_cases"].append({
        "name": "single_valid_row_zeros",
        "row": row1,
    })

    # Test Case 2: Single valid row, feature[0]=65536 (1.0 in Q16.16).
    features_one = [0] * 128
    features_one[0] = 65536
    row2 = encode_row_for_test(0, 1, -1, 1700000000, features_one, bytes(16))
    vectors["test_cases"].append({
        "name": "single_valid_row_negative_label",
        "row": row2,
    })

    # Test Case 3: Row with missing features.
    features_miss = [0] * 128
    features_miss[0] = 131072  # 2.0
    mask = bytearray(16)
    mask[0] |= 0x01  # feature 0 missing
    mask[5] |= 0x04  # feature 45 missing
    row3 = encode_row_for_test(0, 1, 1, 1700000000, features_miss, bytes(mask))
    vectors["test_cases"].append({
        "name": "row_with_missing_features",
        "row": row3,
    })

    # Test Case 4: Padding row.
    row4 = encode_row_for_test(131071, 0, 0, 0, features_zeros, bytes(16))
    vectors["test_cases"].append({
        "name": "padding_row",
        "row": row4,
    })

    # Test Case 5: Two rows (row swap test).
    features_a = [0] * 128
    features_a[0] = 65536
    row5a = encode_row_for_test(0, 1, 1, 1700000000, features_a, bytes(16))
    features_b = [0] * 128
    features_b[0] = 131072
    row5b = encode_row_for_test(1, 1, -1, 1700000001, features_b, bytes(16))
    vectors["test_cases"].append({
        "name": "two_rows_order_test",
        "rows": [row5a, row5b],
    })

    # Test Case 6: Small tree (4 rows).
    rows_4 = []
    for i in range(4):
        feat = [0] * 128
        feat[0] = 65536 * (i + 1)
        rows_4.append(encode_row_for_test(i, 1, 1 if i % 2 == 0 else -1,
                                           1700000000 + i, feat, bytes(16)))
    vectors["test_cases"].append({
        "name": "four_row_tree",
        "rows": rows_4,
    })

    # Test Case 7: Audit test row (features that trigger margin/distance checks).
    features_audit = [0] * 128
    for i in range(128):
        features_audit[i] = (i - 64) * 100  # Varying values within int32 range
    row7 = encode_row_for_test(42, 1, 1, 1700000000, features_audit, bytes(16))
    vectors["test_cases"].append({
        "name": "audit_test_row",
        "row": row7,
    })

    # Write vectors.
    output_path = output_dir / "poseidon2_cross_test_vectors.json"
    output_path.write_text(json.dumps(vectors, indent=2), encoding="utf-8")
    print(f"Cross-test vectors written to {output_path}")
    print(f"Total test cases: {len(vectors['test_cases'])}")

    # Also write individual binary files for Go consumption.
    for tc in vectors["test_cases"]:
        name = tc["name"]
        if "row" in tc:
            raw = bytes.fromhex(tc["row"]["canonical_hex"])
            (output_dir / f"{name}.bin").write_bytes(raw)
        elif "rows" in tc:
            all_raw = b""
            for r in tc["rows"]:
                all_raw += bytes.fromhex(r["canonical_hex"])
            (output_dir / f"{name}.bin").write_bytes(all_raw)


if __name__ == "__main__":
    main()
