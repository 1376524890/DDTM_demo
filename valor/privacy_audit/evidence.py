"""PrivacyAuditEvidence —— 隐私审计证据（方案 §21）。

不把完整 MNIST row 塞进 evidence artifact；只保存 opening hash/index/verification
结果 + 抽样统计（test_statistic/p_value）+ 披露量。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from valor.core.hashing import content_hash, sha256_hex


@dataclass(frozen=True)
class PrivacyAuditEvidence:
    node_id: str
    task_id: str
    execution_mode: str
    claim_hash: str
    commitment_hash: str
    challenge_id: str
    challenge_hash: str
    opening_indices: tuple[int, ...]
    opening_commitment_hashes: tuple[str, ...]
    merkle_verification_passed: bool
    disclosed_rows: int
    disclosed_bytes: int
    test_statistic: float | None
    p_value: float | None
    result: str  # PrimitiveResult
    execution_hash: str
    timestamp: str
    signature: str = ""
    evidence_id: str = ""

    def to_plain(self) -> dict:
        return {
            "node_id": self.node_id,
            "task_id": self.task_id,
            "execution_mode": self.execution_mode,
            "claim_hash": self.claim_hash,
            "commitment_hash": self.commitment_hash,
            "challenge_id": self.challenge_id,
            "challenge_hash": self.challenge_hash,
            "opening_indices": list(self.opening_indices),
            "opening_commitment_hashes": list(self.opening_commitment_hashes),
            "merkle_verification_passed": self.merkle_verification_passed,
            "disclosed_rows": self.disclosed_rows,
            "disclosed_bytes": self.disclosed_bytes,
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "result": self.result,
            "execution_hash": self.execution_hash,
            "timestamp": self.timestamp,
            "signature": self.signature,
            "evidence_id": self.evidence_id,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "PrivacyAuditEvidence":
        return cls(
            node_id=d["node_id"], task_id=d["task_id"],
            execution_mode=d["execution_mode"], claim_hash=d["claim_hash"],
            commitment_hash=d["commitment_hash"],
            challenge_id=d["challenge_id"], challenge_hash=d["challenge_hash"],
            opening_indices=tuple(d["opening_indices"]),
            opening_commitment_hashes=tuple(d["opening_commitment_hashes"]),
            merkle_verification_passed=d["merkle_verification_passed"],
            disclosed_rows=d["disclosed_rows"], disclosed_bytes=d["disclosed_bytes"],
            test_statistic=d["test_statistic"], p_value=d["p_value"],
            result=d["result"], execution_hash=d["execution_hash"],
            timestamp=d["timestamp"], signature=d.get("signature", ""),
            evidence_id=d.get("evidence_id", ""),
        )


def compute_execution_hash(node_id, task_id, opening_hashes, result,
                           test_statistic, p_value, merkle_ok) -> str:
    return sha256_hex(content_hash({
        "node_id": node_id, "task_id": task_id,
        "opening_hashes": list(opening_hashes), "result": result,
        "test_statistic": test_statistic, "p_value": p_value,
        "merkle_ok": merkle_ok,
    }).encode())


def build_evidence(
    *, node_id: str, task_id: str, execution_mode: str, claim_hash: str,
    commitment_hash: str, challenge_id: str, challenge_hash: str,
    opening_indices: list[int], opening_hashes: list[str],
    merkle_verification_passed: bool, disclosed_bytes: int,
    test_statistic: float | None, p_value: float | None, result: str,
    signature: str = "",
) -> PrivacyAuditEvidence:
    exec_hash = compute_execution_hash(
        node_id, task_id, opening_hashes, result, test_statistic, p_value,
        merkle_verification_passed)
    return PrivacyAuditEvidence(
        node_id=node_id, task_id=task_id, execution_mode=execution_mode,
        claim_hash=claim_hash, commitment_hash=commitment_hash,
        challenge_id=challenge_id, challenge_hash=challenge_hash,
        opening_indices=tuple(opening_indices),
        opening_commitment_hashes=tuple(opening_hashes),
        merkle_verification_passed=merkle_verification_passed,
        disclosed_rows=len(opening_indices), disclosed_bytes=disclosed_bytes,
        test_statistic=test_statistic, p_value=p_value, result=result,
        execution_hash=exec_hash,
        timestamp=datetime.now(timezone.utc).isoformat(), signature=signature,
        evidence_id=f"evt-{sha256_hex(exec_hash.encode())[:12]}",
    )


__all__ = ["PrivacyAuditEvidence", "build_evidence", "compute_execution_hash"]
