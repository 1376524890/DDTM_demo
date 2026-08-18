"""Privacy Audit 核心模型（VALOR Privacy-Preserving Commit-and-Challenge Audit）。

对齐方案：七个核心对象
    DatasetCommitment + AggregateClaim + PrivacyAuditAction +
    RowChallenge + RowOpening + AuditEvidence + DisclosureState

本层只负责产生 Evidence 与 MC_A^pay（及校准后 Λ_j），不改变原主链经济机制。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuditExecutionMode(str, Enum):
    """审计执行模式。正式 MNIST 默认 COMMIT_CHALLENGE。"""

    FULL_DATA = "FULL_DATA"  # 测试/reference（Cleanlab 等）
    COMMIT_CHALLENGE = "COMMIT_CHALLENGE"
    TEE = "TEE"  # 后续
    ZK = "ZK"  # 后续


class ClaimType(str, Enum):
    """卖方可声明的聚合统计类型（第一版）。"""

    ROW_COUNT = "ROW_COUNT"
    LABEL_DISTRIBUTION = "LABEL_DISTRIBUTION"
    PIXEL_MEAN = "PIXEL_MEAN"
    PIXEL_VARIANCE = "PIXEL_VARIANCE"
    ZERO_FRACTION = "ZERO_FRACTION"
    VALUE_RANGE = "VALUE_RANGE"
    DUPLICATE_RATE = "DUPLICATE_RATE"


class PrimitiveResult(str, Enum):
    """primitive 层结果（不直接返回 SELLER_BREACH）。"""

    PASS = "PASS"
    CLAIM_NOT_SUPPORTED = "CLAIM_NOT_SUPPORTED"
    BREACH_EVIDENCE = "BREACH_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"


class DecisionRule(str, Enum):
    """抽样统计决策规则（第一版）。"""

    MULTINOMIAL_GOF = "MULTINOMIAL_GOF"  # LabelDistribution
    CHI_SQUARE = "CHI_SQUARE"
    CI_CONTAINMENT = "CI_CONTAINMENT"  # PixelMoment：声称值是否落入抽样 CI
    RANGE_CHECK = "RANGE_CHECK"  # Range/Malformed
    RATE_THRESHOLD = "RATE_THRESHOLD"  # Duplicate


@dataclass(frozen=True)
class PrivacyAuditAction:
    """一个隐私审计动作（进入 Audit-VOI 的 a_j）。"""

    action_id: str
    primitive_id: str
    execution_mode: AuditExecutionMode
    claim_type: ClaimType
    challenge_size: int  # k
    sampling_method: str  # "uniform_random"
    decision_rule_id: str
    payer: str = "SELLER"
    trigger: str = "BASE_LISTING"
    privacy_budget_cost_model_id: str = "rows_disclosed"
    computation_cost_model_id: str = "auditor_rows"
    likelihood_model_id: str = "cc_calibrated"
    execution_spec_hash: str = ""
    action_profile_hash: str = ""

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "primitive_id": self.primitive_id,
            "execution_mode": self.execution_mode.value,
            "claim_type": self.claim_type.value,
            "challenge_size": self.challenge_size,
            "sampling_method": self.sampling_method,
            "decision_rule_id": self.decision_rule_id,
            "payer": self.payer,
            "trigger": self.trigger,
            "privacy_budget_cost_model_id": self.privacy_budget_cost_model_id,
            "computation_cost_model_id": self.computation_cost_model_id,
            "likelihood_model_id": self.likelihood_model_id,
            "execution_spec_hash": self.execution_spec_hash,
            "action_profile_hash": self.action_profile_hash,
        }


__all__ = [
    "AuditExecutionMode", "ClaimType", "PrimitiveResult", "DecisionRule",
    "PrivacyAuditAction",
]
