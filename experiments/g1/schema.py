"""Schema hash and domain-separation tags (canonical-data-v1).

The SchemaHash is the SHA-256 of the *raw bytes* of the frozen schema file —
no language may reformat the JSON before hashing. It is split into two 128-bit
halves so it fits cleanly into BN254 field elements. Domain tags are
``SHA-256(name) mod p``.
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
    """Raw 32-byte SHA-256 of the canonical schema file bytes."""
    return hashlib.sha256(path.read_bytes()).digest()


def schema_halves(path: Path = SCHEMA_PATH) -> tuple[int, int]:
    """Return ``(schemaHi, schemaLo)`` as two 128-bit big-endian integers."""
    digest = schema_digest(path)
    schema_hi = int.from_bytes(digest[:16], "big")
    schema_lo = int.from_bytes(digest[16:], "big")
    return schema_hi, schema_lo


def schema_sha256_hex(path: Path = SCHEMA_PATH) -> str:
    return schema_digest(path).hex()


def domain_tags(modulus: int) -> dict[str, int]:
    """Compute every domain tag as ``SHA-256(name) mod modulus``."""
    return {
        name: int.from_bytes(hashlib.sha256(name.encode("ascii")).digest(), "big")
        % modulus
        for name in DOMAIN_NAMES
    }
