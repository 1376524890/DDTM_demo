"""SchemaHash 与域分离标签（canonical-data-v1）。

SchemaHash 是冻结的 schema 文件*原始字节*的 SHA-256——任何语言都不得在哈希前
重新格式化该 JSON。它被拆成两半 128 位整数，以便干净地装入 BN254 域元素。域标签
为 ``SHA-256(name) mod p``。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "specs" / "canonical-data-v1.schema.json"

DOMAIN_NAMES = (
    "DDTM_ROW_V1",
    "DDTM_PADDING_V1",
    "DDTM_NODE_V1",
    "DDTM_SCHEMA_V1",
)


def schema_digest(path: Path = SCHEMA_PATH) -> bytes:
    """规范化 schema 文件原始字节的 32 字节 SHA-256。"""
    return hashlib.sha256(path.read_bytes()).digest()


def schema_halves(path: Path = SCHEMA_PATH) -> tuple[int, int]:
    """返回 ``(schemaHi, schemaLo)``——两个 128 位大端整数。"""
    digest = schema_digest(path)
    schema_hi = int.from_bytes(digest[:16], "big")
    schema_lo = int.from_bytes(digest[16:], "big")
    return schema_hi, schema_lo


def schema_sha256_hex(path: Path = SCHEMA_PATH) -> str:
    return schema_digest(path).hex()


def domain_tags(modulus: int) -> dict[str, int]:
    """把每个域标签计算为 ``SHA-256(name) mod modulus``。"""
    return {
        name: int.from_bytes(hashlib.sha256(name.encode("ascii")).digest(), "big")
        % modulus
        for name in DOMAIN_NAMES
    }
