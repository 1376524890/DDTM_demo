"""Auditor 可靠度 posterior（规范 §46）。

    r_i ~ Beta(a_i^r + Correct_i, b_i^r + Incorrect_i)
"""

from __future__ import annotations

from .eligibility import GroundTruthEligibilityGate


def update_auditor_beta(
    a: float,
    b: float,
    *,
    correct: int,
    incorrect: int,
    event_type: str,
) -> tuple[float, float]:
    """更新 auditor 可靠度 posterior。"""
    GroundTruthEligibilityGate.eligible_or_raise(event_type)
    return a + correct, b + incorrect
