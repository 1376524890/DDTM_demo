"""PrivacyAuditTask —— COMMIT_CHALLENGE 审计任务载体（PPA-4）。

独立于现有 TaskEnvelope（保留 FULL_DATA 路径不破坏）。
包含：commitment + claim + challenge + openings + primitive_id + task_hash。
auditor 只收到此载体，不含全量数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash, sha256_hex

from .challenge import RowChallenge
from .claims import AggregateClaim
from .commitment import DatasetCommitment
from .models import AuditExecutionMode
from .opening import RowOpening


@dataclass
class PrivacyAuditTask:
    task_id: str
    tx_id: str
    commitment: DatasetCommitment
    claim: AggregateClaim
    primitive_id: str
    execution_mode: AuditExecutionMode = AuditExecutionMode.COMMIT_CHALLENGE
    challenge: RowChallenge | None = None
    openings: list[RowOpening] = field(default_factory=list)

    @property
    def task_hash(self) -> str:
        return sha256_hex(content_hash({
            "task_id": self.task_id, "tx_id": self.tx_id,
            "commitment_hash": self.commitment.commitment_hash,
            "claim_hash": self.claim.claim_hash,
            "primitive_id": self.primitive_id,
            "execution_mode": self.execution_mode.value,
            "challenge_hash": self.challenge.challenge_hash if self.challenge else "",
            "opening_hashes": [o.opening_hash for o in self.openings],
        }).encode())

    def to_plain(self) -> dict:
        return {
            "task_id": self.task_id,
            "tx_id": self.tx_id,
            "commitment": self.commitment.to_plain(),
            "claim": self.claim.to_plain(),
            "primitive_id": self.primitive_id,
            "execution_mode": self.execution_mode.value,
            "challenge": self.challenge.to_plain() if self.challenge else None,
            "openings": [o.to_plain() for o in self.openings],
            "task_hash": self.task_hash,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "PrivacyAuditTask":
        return cls(
            task_id=d["task_id"], tx_id=d["tx_id"],
            commitment=DatasetCommitment.from_plain(d["commitment"]),
            claim=AggregateClaim.from_plain(d["claim"]),
            primitive_id=d["primitive_id"],
            execution_mode=AuditExecutionMode(d["execution_mode"]),
            challenge=(RowChallenge.from_plain(d["challenge"])
                       if d.get("challenge") else None),
            openings=[RowOpening.from_plain(o) for o in d.get("openings", [])],
        )


__all__ = ["PrivacyAuditTask"]
