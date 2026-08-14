"""分布式审计任务与证据模型（规范 §16）。

每次审计任务 T_a = (txID, dataCommitment, rightsCommitment, algorithmSpecHash,
paramManifestHash, executionSpecHash, deadline)。
节点输出 E_i = (nodeID, T_a, result, rawMetrics, evidenceArtifacts,
executionHash, timestamp, signature)。

必须满足：
    H(D_node) = H(D)_τ
    H(AlgorithmSpec_node) = H(AlgorithmSpec)_{T_a}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from valor.core.hashing import content_hash, sha256_hex, stable_hash
from valor.core.ids import AuditorID, TransactionID


@dataclass(frozen=True)
class TaskEnvelope:
    """审计任务信封（§16 T_a）。"""

    tx_id: TransactionID
    data_commitment: str  # H(D)_τ
    rights_commitment: str  # H(R_τ)
    algorithm_spec_hash: str  # H(AlgorithmSpec)_{T_a}
    param_manifest_hash: str
    execution_spec_hash: str
    deadline: str
    task_id: str = ""

    def __post_init__(self) -> None:
        if not self.task_id:
            object.__setattr__(
                self, "task_id",
                f"task-{sha256_hex(self.tx_id.value.encode())[:12]}",
            )

    @property
    def task_hash(self) -> str:
        """任务承诺哈希（节点必须据此校验数据/算法一致性）。"""
        return content_hash(self.to_plain())

    def to_plain(self) -> dict:
        return {
            "task_id": self.task_id,
            "tx_id": str(self.tx_id),
            "data_commitment": self.data_commitment,
            "rights_commitment": self.rights_commitment,
            "algorithm_spec_hash": self.algorithm_spec_hash,
            "param_manifest_hash": self.param_manifest_hash,
            "execution_spec_hash": self.execution_spec_hash,
            "deadline": self.deadline,
        }


@dataclass(frozen=True)
class AuditEvidence:
    """节点审计证据（§16 E_i）。"""

    node_id: AuditorID
    task: TaskEnvelope
    result: str  # PASS | QUALITY_FAIL | BREACH_EVIDENCE
    raw_metrics: dict[str, Any]
    execution_hash: str  # H(算法输出 + 数据承诺 + 算法spec)
    timestamp: str
    signature: str = ""
    evidence_id: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id:
            object.__setattr__(
                self, "evidence_id",
                f"evt-{sha256_hex(self.execution_hash.encode())[:12]}",
            )

    def verify_commitment(self, expected: TaskEnvelope) -> bool:
        """校验节点执行与任务承诺一致（§16）。"""
        return (
            self.task.data_commitment == expected.data_commitment
            and self.task.algorithm_spec_hash == expected.algorithm_spec_hash
            and self.task.param_manifest_hash == expected.param_manifest_hash
        )

    @property
    def evidence_hash(self) -> str:
        return content_hash(self.to_plain())

    def sign(self, private_key: bytes) -> str:
        """用节点私钥签名证据（cryptography Ed25519）。"""
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        key = serialization.load_der_private_key(private_key, password=None)
        payload = self.evidence_hash.encode("utf-8")
        sig = key.sign(payload)
        object.__setattr__(self, "signature", sig.hex())
        return self.signature

    def to_plain(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "node_id": str(self.node_id),
            "task_id": self.task.task_id,
            "result": self.result,
            "raw_metrics": self.raw_metrics,
            "execution_hash": self.execution_hash,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }
