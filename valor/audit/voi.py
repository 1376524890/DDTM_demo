"""Audit-VOI 计算（规范 §24/§25）。

    P(y | π, a_j) = Σ_x Λ_j(y,x) π_x
    π'(y)         = Bayes update
    ER(a_j)       = Σ_y P(y|π,a_j) R(π'(y))
    MV_A(a_j)     = R(π) - ER(a_j)
    VOI_A^private(a_j) = MV_A(a_j) - MĈ_A^pay(a_j)
    若 max_j VOI_A^private ≤ 0 → STOP
"""

from __future__ import annotations

from .bayes_update import bayes_update
from .loss import LossMatrix, bayes_risk
from .state_model import StateBelief


def expected_posterior_risk(
    belief: StateBelief,
    likelihood,
    loss: LossMatrix,
    y: str,
) -> float:
    """ER 对单个观测 y 的期望后验风险贡献前的后验风险 R(π'(y))。"""
    updated = bayes_update(belief, likelihood.row(y))
    risk, _ = bayes_risk(updated, loss)
    return risk


def marginal_value_of_audit(
    belief: StateBelief,
    likelihood,
    loss: LossMatrix,
) -> tuple[float, dict]:
    """MV_A(a_j) = R(π) - Σ_y P(y|π,a_j) R(π'(y))。"""
    current_risk, _ = bayes_risk(belief, loss)
    expected = 0.0
    detail: dict[str, float] = {}
    for y in likelihood.rows:
        # P(y | π, a_j) = Σ_x Λ_j(y,x) π_x
        py = sum(
            likelihood.rows[y].get(st.value, 0.0)
            * getattr(belief, f"prob_{st.value.lower()}")
            for st in __import__(
                "valor.core.enums", fromlist=["TradeState"]
            ).TradeState
        )
        er_y = expected_posterior_risk(belief, likelihood, loss, y)
        expected += py * er_y
        detail[y] = py
    mv = current_risk - expected
    return mv, detail


def choose_best_action(
    belief: StateBelief,
    actions: dict[str, tuple],
    loss: LossMatrix,
    costs: dict[str, float],
) -> tuple[str | None, float, dict]:
    """在候选认证动作中选择 VOI 最大者；全部 ≤0 → None（STOP）。

    actions: {action_id: likelihood}; costs: {action_id: MĈ_A^pay}。
    """
    best_action: str | None = None
    best_voi = float("-inf")
    details: dict[str, float] = {}
    for aid, likelihood in actions.items():
        mv, _ = marginal_value_of_audit(belief, likelihood, loss)
        voi = mv - costs.get(aid, 0.0)
        details[aid] = voi
        if voi > best_voi:
            best_voi = voi
            best_action = aid
    if best_action is None or best_voi <= 0:
        return None, best_voi, details
    return best_action, best_voi, details


def stop_decision(best_voi: float) -> bool:
    """VOI ≤ 0 → STOP（§25）。"""
    return best_voi <= 0
