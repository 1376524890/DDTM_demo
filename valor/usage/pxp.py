"""PXP —— Policy Execution Point（规范 §35）。

执行扣次数、更新隐私预算、生成 receipt、触发删除等 duty。ALLOW 与 DENY 都
产生 receipt/event。
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import UsageState


@dataclass
class PXPOutcome:
    """PXP 执行结果。"""

    decision: str  # ALLOW | DENY
    usage_state: UsageState
    usage_count_after: int
    privacy_budget_used_after: float
    duty_triggered: list[str]
    receipt_id: str = ""

    def to_plain(self) -> dict:
        return {
            "decision": self.decision,
            "usage_count_after": self.usage_count_after,
            "privacy_budget_used_after": self.privacy_budget_used_after,
            "duty_triggered": self.duty_triggered,
            "receipt_id": self.receipt_id,
        }


def execute(
    *,
    decision: str,
    usage_state: UsageState,
    privacy_cost: float = 0.0,
    max_uses: int = 0,
    retention_state: str = "",
) -> PXPOutcome:
    """执行 PXP：ALLOW 则扣次数/更新预算；DENY 只记录。

    触发删除 duty：当 usage 达上限或保留到期 → DELETION_PENDING duty 触发
    （由 retention 模块实际执行删除并生成 DeletionReceipt）。
    """
    duty: list[str] = []
    if decision == "ALLOW":
        usage_state.usage_count += 1
        usage_state.privacy_budget_used += privacy_cost
    if max_uses and usage_state.usage_count >= max_uses:
        duty.append("DELETION_PENDING")
    if retention_state == "EXPIRED":
        duty.append("DELETION_PENDING")
    return PXPOutcome(
        decision=decision, usage_state=usage_state,
        usage_count_after=usage_state.usage_count,
        privacy_budget_used_after=usage_state.privacy_budget_used,
        duty_triggered=duty,
    )


__all__ = ["PXPOutcome", "execute"]
