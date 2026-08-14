"""动作似然 Λ_j(y, x)（规范 §21.2）。

a_j = (primitive, m, q, ρ, securityProfile, aggregationRule)。
Λ_j(y,x) = P(Y_j = y | X = x, a_j)，包含节点故障、恶意报告、challenge 和
quorum 影响，不能直接等同于单节点 primitive accuracy。
"""

from __future__ import annotations

from dataclasses import dataclass

from valor.core.enums import AuditOutcome, TradeState


@dataclass(frozen=True)
class ActionLikelihood:
    """一个认证审计动作 a_j 的似然 Λ_j。"""

    action_id: str
    rows: dict[str, dict[str, float]]  # rows[y][x] = Λ_j(y, x)

    def row(self, y: str) -> dict[str, float]:
        return self.rows[y]

    def normalize(self) -> "ActionLikelihood":
        """对每个 x 归一化 Σ_y Λ_j(y,x)=1。"""
        out = {}
        for y in AuditOutcome:
            row = self.rows.get(y.value)
            if row is None:
                continue
            out[y.value] = dict(row)
        return ActionLikelihood(action_id=self.action_id, rows=out)

    def to_plain(self) -> dict:
        return {"action_id": self.action_id, "rows": self.rows}
