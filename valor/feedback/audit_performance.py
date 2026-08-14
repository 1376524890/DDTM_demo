"""Primitive 敏感度/误报 posterior（规范 §46）。

    s_j ~ Beta(a_j^s + TP_j, b_j^s + FN_j)
    f_j ~ Beta(a_j^f + FP_j, b_j^f + TN_j)
"""

from __future__ import annotations

from .eligibility import GroundTruthEligibilityGate


def update_primitive_beta(
    a_s: float,
    b_s: float,
    a_f: float,
    b_f: float,
    *,
    tp: int,
    fn: int,
    fp: int,
    tn: int,
    event_type: str,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """更新敏感度与误报 posterior，返回 ((a_s',b_s'),(a_f',b_f'))。"""
    GroundTruthEligibilityGate.eligible_or_raise(event_type)
    return (a_s + tp, b_s + fn), (a_f + fp, b_f + tn)
