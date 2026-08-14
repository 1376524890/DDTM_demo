"""Feedback Ground-Truth Eligibility Gate（规范 §45）。

普通 PASS、TRADE 或 unchallenged report 不能自动作为 ground truth。只有
ADJUDICATED_DISPUTE / STRONG_CHALLENGE / INDEPENDENT_FULL_AUDIT /
CONTROLLED_CANARY / EXTERNAL_VERIFIED_GROUND_TRUTH / VERIFIED_LEAK_FINGERPRINT
等事件才能更新需要真实标签的 posterior。因此 PASS ⇏ TN，且
ExperimentalOracleFeedback ≠ ProductionObservableFeedback。
"""

from __future__ import annotations

from enum import Enum


class EligibleEventType(str, Enum):
    """可更新真实标签 posterior 的 ground-truth 事件（§45）。"""

    ADJUDICATED_DISPUTE = "ADJUDICATED_DISPUTE"
    STRONG_CHALLENGE = "STRONG_CHALLENGE"
    INDEPENDENT_FULL_AUDIT = "INDEPENDENT_FULL_AUDIT"
    CONTROLLED_CANARY = "CONTROLLED_CANARY"
    EXTERNAL_VERIFIED_GROUND_TRUTH = "EXTERNAL_VERIFIED_GROUND_TRUTH"
    VERIFIED_LEAK_FINGERPRINT = "VERIFIED_LEAK_FINGERPRINT"


class GroundTruthEligibilityGate:
    """ground-truth 反馈资格门。"""

    @classmethod
    def is_eligible(cls, event_type: str) -> bool:
        """仅上述事件可更新真实标签 posterior（§45）。"""
        try:
            EligibleEventType(event_type)
            return True
        except ValueError:
            return False

    @classmethod
    def eligible_or_raise(cls, event_type: str) -> None:
        """不合格则抛错（禁止 PASS 当 TN）。"""
        if not cls.is_eligible(event_type):
            from valor.core.errors import VALORError

            raise VALORError(
                f"事件 {event_type} 不具备 ground-truth 资格（PASS 不⇒TN，§45）",
            )
