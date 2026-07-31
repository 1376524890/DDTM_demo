#!/usr/bin/env python3
"""生成规范化的 G1 测试向量清单。

Python 是 **golden** 生成器：它编码每一个正向用例，计算 Poseidon2 行叶子与 Merkle
数据根，写出 ``manifest.json`` 与 ``.bin`` blob。负向用例（NaN / ±Inf）只记录预期
的拒绝码——不输出 blob。大型「生成」用例存储确定性生成器参数与预期根，而非一个
巨大的二进制。

每个小型正向用例使用小的树容量（叶子 / 节点原语与容量无关，因此容量为 8 的树与
容量为 131072 的树走的是同一段代码）。只有规模用例使用完整 131072 容量；为让各语言
都跑得快，本实现默认用 8192（算法完全相同，仅深度不同；生产用 131072 同路径）。
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
    """从已是 int32 的特征构造一个已编码 blob。"""
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
    """量化单个浮点（用于边界用例）。"""
    return R.quantize_features([value])[0]


def generated_features(i: int) -> list[int]:
    """synthetic-v1 的确定性特征向量（每种语言都重新实现同样的公式）。"""
    return [((i + 1) * (j + 1)) & 0xFFFF for j in range(128)]


def build_positive_cases() -> list[dict]:
    """把每个小型正向用例定义为 (id, capacity, [blobs])。"""
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
    """写出负向用例的输入定义并返回清单条目。"""
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
    """编码 blob、计算叶子 + 根、写 .bin、返回清单条目。"""
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
    """生成一个大型合成数据集，计算其根（不存 .bin）。"""
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
                        help="tc18 大型/生成用例的行数")
    parser.add_argument("--capacity-rows", type=int, default=1000,
                        help="tc19 容量用例的数据行数")
    parser.add_argument("--capacity", type=int, default=8192,
                        help="大型/生成用例的 Merkle 树容量"
                             "（生产用 131072，走相同代码路径）")
    args = parser.parse_args()

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    print("编码正向用例...")
    cases = [materialize_positive(c) for c in build_positive_cases()]

    print("写负向定义...")
    cases.extend(build_negative_definitions())

    print(f"生成 tc18 大型用例（{args.large_rows} 行，cap {args.capacity}）...")
    cases.append(materialize_generated(
        "tc18_large_generated", args.large_rows, args.capacity, seed=20260731))

    print(f"生成 tc19 容量用例（{args.capacity_rows} 行，cap {args.capacity}）...")
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
    print(f"\n清单已写入：{manifest_path}")
    print(f"用例：{pos} 正向、{neg} 负向、{gen} 生成（共 {len(cases)}）")


if __name__ == "__main__":
    main()
