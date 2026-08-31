"""RandomnessManifest for deterministic replay (Round 7 P0-21).

Production/FORMAL safety randomness must come from CSPRNG/approved RNG once and
then be recorded in a protected/private manifest; public reports only hold
hashes/refs. This module provides the public manifest and a protected store
abstraction without leaking secret salts or nonces.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class RandomnessReference:
    kind: str
    reference: str  # public hash/ref to the protected randomness
    producer: str = ""
    note: str = ""

    def to_plain(self) -> dict:
        return {"kind": self.kind, "reference": self.reference,
                "producer": self.producer, "note": self.note}


@dataclass
class RandomnessManifest:
    """Public manifest of randomness references. Secrets stay in protected store."""

    run_id: str = ""
    entries: dict[str, RandomnessReference] = field(default_factory=dict)
    logical_clock_origin: str = ""

    def add(self, *, kind: str, reference: str, producer: str = "",
            note: str = "") -> None:
        self.entries[kind] = RandomnessReference(
            kind=kind, reference=reference, producer=producer, note=note)

    @property
    def artifact_hash(self) -> str:
        return content_hash({
            "run_id": self.run_id,
            "logical_clock_origin": self.logical_clock_origin,
            "entries": {k: v.to_plain() for k, v in sorted(self.entries.items())},
        })

    def to_plain(self) -> dict:
        return {
            "run_id": self.run_id,
            "logical_clock_origin": self.logical_clock_origin,
            "entries": {k: v.to_plain() for k, v in self.entries.items()},
            "artifact_hash": self.artifact_hash,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "RandomnessManifest":
        m = cls(run_id=d.get("run_id", ""),
                logical_clock_origin=d.get("logical_clock_origin", ""))
        for k, v in (d.get("entries") or {}).items():
            m.entries[k] = RandomnessReference(**v)
        return m


class ProtectedRandomnessStore:
    """Holds secret randomness bytes; public manifest only stores hashes/refs."""

    def __init__(self, root: str | Path = "seller_private/randomness") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def store(self, *, kind: str, data: bytes) -> str:
        ref = content_hash({"kind": kind, "data": data.hex()})
        (self._root / f"{kind}.{ref[:16]}.bin").write_bytes(data)
        return ref

    def resolve(self, kind: str, reference: str) -> bytes:
        path = self._root / f"{kind}.{reference[:16]}.bin"
        if not path.exists():
            raise FileNotFoundError(f"PROTECTED_RANDOMNESS_MISSING: {kind} {reference}")
        data = path.read_bytes()
        if content_hash({"kind": kind, "data": data.hex()}) != reference:
            raise ValueError(f"PROTECTED_RANDOMNESS_HASH_MISMATCH: {kind}")
        return data


__all__ = ["RandomnessReference", "RandomnessManifest", "ProtectedRandomnessStore"]
