"""Buyer misuse / usage violation 证据（规范 §38 / P0-N）。

UsageViolationEvidence 由真实 UsageRequest + DENY/bypass 派生（§37 DENY 也产生
审计事件）。BuyerBreachResolver 由 evidence 判定是否构成 BUYER_BREACH（区分普通
DENY 与 breach）。Mechanism 不读取 scenario 的 expected label。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


class UsageViolationType:
    USE_AFTER_EXPIRY = "USE_AFTER_EXPIRY"
    USAGE_COUNT_EXCEEDED = "USAGE_COUNT_EXCEEDED"
    UNAUTHORIZED_PURPOSE = "UNAUTHORIZED_PURPOSE"
    UNAUTHORIZED_ACTOR = "UNAUTHORIZED_ACTOR"
    UNAUTHORIZED_ENVIRONMENT = "UNAUTHORIZED_ENVIRONMENT"
    REDISSEMINATION = "UNAUTHORIZED_REDISSEMINATION"
    SUBLICENSE = "SUBLICENSE_VIOLATION"
    EXPORT_BYPASS = "EXPORT_BYPASS"
    DELETE_DUTY_VIOLATION = "DELETE_DUTY_VIOLATION"
    PRIVACY_BUDGET_EXCEEDED = "PRIVACY_BUDGET_EXCEEDED"
    UNSUPPORTED_EXPORT = "UNSUPPORTED_EXPORT"
    UNAUTHORIZED_ALGORITHM = "UNAUTHORIZED_ALGORITHM"


@dataclass(frozen=True)
class UsageViolationEvidence:
    """一次用途违规/拒绝的证据（§38 / P0-N）。"""

    evidence_id: str
    receipt_id: str
    tx_id: str
    violation_type: str
    actor: str
    requested_action: str
    contract_clause: str
    severity: int  # 1-5
    breach_triggering: bool
    evidence_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_hash", content_hash({
            "evidence_id": self.evidence_id, "receipt_id": self.receipt_id,
            "tx_id": self.tx_id, "violation_type": self.violation_type,
            "actor": self.actor, "requested_action": self.requested_action,
            "contract_clause": self.contract_clause, "severity": self.severity,
            "breach_triggering": self.breach_triggering,
        }))

    def to_plain(self) -> dict:
        return {
            "evidence_id": self.evidence_id, "receipt_id": self.receipt_id,
            "tx_id": self.tx_id, "violation_type": self.violation_type,
            "actor": self.actor, "requested_action": self.requested_action,
            "contract_clause": self.contract_clause, "severity": self.severity,
            "breach_triggering": self.breach_triggering,
            "evidence_hash": self.evidence_hash,
        }


def evidence_from_deny(
    *, receipt_id: str, tx_id: str, request, violations: list[str],
    contract_clause: str = "", severity: int = 1,
) -> UsageViolationEvidence:
    """从一次 DENY 请求派生 UsageViolationEvidence（§37 DENY 也产生事件）。

    violations 是 PEP 判定返回的违反约束列表，映射到 violation_type。
    一次普通被拒请求不一定自动 breach（breach_triggering 由 resolver 判定）。
    """
    vmap = {
        "时间超出有效期": UsageViolationType.USE_AFTER_EXPIRY,
        "使用次数达上限": UsageViolationType.USAGE_COUNT_EXCEEDED,
        "用途不在授权集合": UsageViolationType.UNAUTHORIZED_PURPOSE,
        "主体未授权": UsageViolationType.UNAUTHORIZED_ACTOR,
        "环境未授权": UsageViolationType.UNAUTHORIZED_ENVIRONMENT,
        "隐私预算超限": UsageViolationType.PRIVACY_BUDGET_EXCEEDED,
        "权利已撤销": UsageViolationType.USE_AFTER_EXPIRY,
    }
    vtype = vmap.get(violations[0], "USAGE_VIOLATION") if violations \
        else "USAGE_VIOLATION"
    return UsageViolationEvidence(
        evidence_id="uv-" + content_hash({
            "r": receipt_id, "t": tx_id, "a": request.actor,
            "p": request.purpose, "v": violations})[:16],
        receipt_id=receipt_id, tx_id=tx_id, violation_type=vtype,
        actor=request.actor, requested_action=request.action,
        contract_clause=contract_clause, severity=severity,
        breach_triggering=False,  # 由 resolver 判定
    )


@dataclass
class BuyerBreachResolver:
    """由 UsageViolationEvidence[] 判定是否构成 BUYER_BREACH（§38 / P0-N）。

    区分普通 DENY 与 breach，依据：contract clause / violation type / severity /
    repeated attempts / bypass evidence / explicit policy。Mechanism 不读取
    scenario 标准答案。
    """

    contract_clauses: dict[str, dict] = field(default_factory=dict)
    # 例如 {"USAGE_COUNT_EXCEEDED": {"breach": True, "threshold_severity": 3}}
    repeated_threshold: int = 3

    def resolve(self, evidences: list[UsageViolationEvidence]) -> dict:
        """判定 breach。返回 {breach: bool, reasons, evidence_ids}。"""
        reasons: list[str] = []
        if not evidences:
            return {"breach": False, "reasons": ["无违规证据"], "evidence_ids": []}
        # 显式 contract clause 判定的 breach（最高优先级）
        for ev in evidences:
            clause = self.contract_clauses.get(ev.violation_type, {})
            if clause.get("breach", False) and ev.severity >= clause.get(
                    "threshold_severity", 1):
                reasons.append(
                    f"contract clause 判定 {ev.violation_type} 为 breach"
                    f"（severity={ev.severity}）")
                return {"breach": True, "reasons": reasons,
                        "evidence_ids": [e.evidence_id for e in evidences]}
        # repeated attempts：同一 violation_type 多次
        from collections import Counter

        counts = Counter(e.violation_type for e in evidences)
        for vtype, n in counts.items():
            if n >= self.repeated_threshold:
                reasons.append(
                    f"重复违规 {vtype}（{n} 次 ≥ {self.repeated_threshold}）")
                return {"breach": True, "reasons": reasons,
                        "evidence_ids": [e.evidence_id for e in evidences]}
        # bypass evidence / 高严重度
        for ev in evidences:
            if ev.breach_triggering or ev.severity >= 5:
                reasons.append(f"高严重度/绕过证据 {ev.violation_type}")
                return {"breach": True, "reasons": reasons,
                        "evidence_ids": [e.evidence_id for e in evidences]}
        return {"breach": False,
                "reasons": ["普通被拒请求，未构成 buyer breach"], "evidence_ids": []}


__all__ = [
    "UsageViolationEvidence", "UsageViolationType", "evidence_from_deny",
    "BuyerBreachResolver",
]
