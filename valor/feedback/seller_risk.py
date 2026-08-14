"""卖方 breach posterior（规范 §46）。

θ_S ~ Beta(a_S, b_S)，仅 ground-truth-eligible outcome 更新。
"""

from __future__ import annotations

from .eligibility import GroundTruthEligibilityGate


def update_seller_beta(
    a: float,
    b: float,
    *,
    tp: int,
    fn: int,
    event_type: str,
) -> tuple[float, float]:
    """用 TP/FN 更新 θ_S ~ Beta(a+TP, b+FN)；不合格事件拒绝更新。"""
    GroundTruthEligibilityGate.eligible_or_raise(event_type)
    return a + tp, b + fn
