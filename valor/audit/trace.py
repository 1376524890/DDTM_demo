"""AuditTrace（规范 §54.3）。

某笔交易实际产生的审计步骤序列；禁止用交易结束后的 trace 作为事前 policy
certification hash（§54.3）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuditStep:
    """一次审计动作的执行记录。"""

    action_id: str
    observed_outcome: str  # PASS | QUALITY_FAIL | BREACH_EVIDENCE
    posterior: dict  # 更新后的信念
    mv: float
    voi: float
    cost_paid: float

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "observed_outcome": self.observed_outcome,
            "posterior": self.posterior,
            "mv": self.mv,
            "voi": self.voi,
            "cost_paid": self.cost_paid,
        }


@dataclass(frozen=True)
class AuditTrace:
    """一次交易产生的审计步骤序列。"""

    tx_id: str
    steps: tuple[AuditStep, ...] = ()

    def to_plain(self) -> dict:
        return {"tx_id": self.tx_id, "steps": [s.to_plain() for s in self.steps]}
