"""Audit-VOI 层（规范 §23–§25 / Phase 3）。

- state_model:  三状态先验 π=(π_G,π_L,π_B)（§23）
- loss:         Bayes 风险 R(π) 与货币损失矩阵 ℓ(d,x)（§24）
- bayes_update: 贝叶斯更新 π'（§24）
- likelihood:   动作似然 Λ_j(y,x)（§21.2）
- voi:          MV_A、VOI_A^private 与 STOP 规则（§24/§25）
- action_catalog: 认证动作目录
- policy:       AuditPolicySpec / 顺序审计策略
"""

from .state_model import StateBelief
from .loss import LossMatrix, bayes_risk
from .bayes_update import bayes_update
from .likelihood import ActionLikelihood
from .voi import (
    expected_posterior_risk,
    marginal_value_of_audit,
    choose_best_action,
    stop_decision,
)

__all__ = [
    "StateBelief",
    "LossMatrix",
    "bayes_risk",
    "bayes_update",
    "ActionLikelihood",
    "expected_posterior_risk",
    "marginal_value_of_audit",
    "choose_best_action",
    "stop_decision",
]
