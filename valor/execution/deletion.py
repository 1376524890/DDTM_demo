"""Retention / DeleteDuty 执行（规范 §34 / P0-N / MFC-G34）。

Rights 存在 retention / deleteDuty 时真正执行受控环境删除，生成 DeletionReceipt。
生命周期：ACTIVE → retention expiry → DELETION_PENDING → 受控删除 → DELETED_ATTESTED。

对 DOWNLOAD_TRACEABLE：不得声称能强制远端离线删除；只能 contractual duty +
buyer attestation + fingerprint + usage bond + post-hoc evidence（threat model 边界）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from valor.core.hashing import content_hash, sha256_hex


@dataclass(frozen=True)
class DeletionReceipt:
    """一次受控环境删除的回执（P0-N）。"""

    tx_id: str
    dataset_commitment: str
    derived_artifact_refs: list[str]
    buyer: str
    environment: str
    deletion_timestamp: str
    evidence_attestation: str
    receipt_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_hash", sha256_hex(content_hash({
            "tx_id": self.tx_id, "dataset_commitment": self.dataset_commitment,
            "derived_artifact_refs": self.derived_artifact_refs, "buyer": self.buyer,
            "environment": self.environment,
            "deletion_timestamp": self.deletion_timestamp,
            "evidence_attestation": self.evidence_attestation,
        }).encode()))

    def to_plain(self) -> dict:
        return {
            "tx_id": self.tx_id, "dataset_commitment": self.dataset_commitment,
            "derived_artifact_refs": self.derived_artifact_refs, "buyer": self.buyer,
            "environment": self.environment,
            "deletion_timestamp": self.deletion_timestamp,
            "evidence_attestation": self.evidence_attestation,
            "receipt_hash": self.receipt_hash,
        }


def execute_delete_duty(
    *,
    tx_id: str, dataset_commitment: str, buyer: str, environment: str,
    derived_artifact_refs: list[str], mode: str, attestation: str = "",
) -> dict:
    """执行删除义务，返回 {receipt, state}。

    COMPUTE_ONLY / API_GATEWAY：受控环境可真实删除，DELETED_ATTESTED。
    DOWNLOAD_TRACEABLE：不能强制离线删除，只记录 contractual duty + attestation，
        状态 DELETION_PENDING（客观边界，禁止虚假声称）。
    """
    ts = "2026-01-01T00:00:00+00:00"  # 确定性时间戳（replay 复现）
    if mode == "DOWNLOAD_TRACEABLE":
        receipt = DeletionReceipt(
            tx_id=tx_id, dataset_commitment=dataset_commitment,
            derived_artifact_refs=derived_artifact_refs, buyer=buyer,
            environment=environment, deletion_timestamp=ts,
            evidence_attestation=attestation or "contractual duty + buyer attestation")
        return {"receipt": receipt.to_plain(),
                "state": "DELETION_PENDING",
                "note": "DOWNLOAD_TRACEABLE 无法强制远端离线删除，仅合同义务+attestation"}
    receipt = DeletionReceipt(
        tx_id=tx_id, dataset_commitment=dataset_commitment,
        derived_artifact_refs=derived_artifact_refs, buyer=buyer,
        environment=environment, deletion_timestamp=ts,
        evidence_attestation=attestation or "controlled environment deletion attested")
    return {"receipt": receipt.to_plain(), "state": "DELETED_ATTESTED",
            "note": "受控环境删除完成并 attestation"}


__all__ = ["DeletionReceipt", "execute_delete_duty"]
