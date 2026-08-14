"""Bayes 风险（规范 §24）。

决策 d_Q ∈ {ACCEPT, REJECT, TERMINATE}，状态 x ∈ {G, L, B}。
损失矩阵 ℓ(d, x) 以统一 Currency Unit [CU] 表示。
    R(π) = min_{d_Q} Σ_x π_x ℓ(d_Q, x)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.enums import AuditDecision, TradeState


@dataclass(frozen=True)
class LossMatrix:
    """审计阶段货币损失矩阵 ℓ(d, x)，单位 [CU]。"""

    loss: dict[str, dict[str, float]]  # loss[decision][state]

    def __post_init__(self) -> None:
        for dec in AuditDecision:
            if dec.value not in self.loss:
                raise ValueError(f"缺失决策 {dec.value}")
            for st in TradeState:
                if st.value not in self.loss[dec.value]:
                    raise ValueError(f"缺失 {dec.value}×{st.value}")

    def get(self, decision: str, state: str) -> float:
        return self.loss[decision][state]

    def to_plain(self) -> dict:
        return {"loss": self.loss}


def bayes_risk(belief, loss_matrix: LossMatrix) -> tuple[float, str]:
    """R(π) = min_d Σ_x π_x ℓ(d,x)；返回 (最小风险, 最优决策)。"""
    best = float("inf")
    best_decision = ""
    for dec in AuditDecision:
        r = 0.0
        for st in TradeState:
            r += getattr(belief, f"prob_{st.value.lower()}") * loss_matrix.get(dec.value, st.value)
        if r < best:
            best = r
            best_decision = dec.value
    return best, best_decision
