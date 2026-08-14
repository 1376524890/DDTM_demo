"""买方/交易合规硬门槛（规范 §6 Compliant(A_D, R_τ, B)）。

检查买方是否具备必要访问资格、权利菜单与既有许可是否冲突等硬约束。
失败抛 EntitlementError，交易不进入价值与审计。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.errors import EntitlementError


@dataclass(frozen=True)
class Compliant:
    """合规评估结果。

    buyer_eligible:   买方是否具备必要访问资格
    menu_conflict:    权利菜单是否与既有许可冲突（True=冲突）
    reasons:          判定理由列表
    """

    buyer_eligible: bool
    menu_conflict: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passes(self) -> bool:
        """Compliant=1 当且仅当买方合格且无菜单冲突。"""
        return self.buyer_eligible and not self.menu_conflict

    def enforce(self) -> None:
        """硬门槛校验；不通过抛 EntitlementError。"""
        if not self.passes:
            raise EntitlementError(
                "交易合规硬门槛不通过",
                detail=self.to_plain(),
            )

    def to_plain(self) -> dict:
        return {
            "buyer_eligible": self.buyer_eligible,
            "menu_conflict": self.menu_conflict,
            "passes": self.passes,
            "reasons": list(self.reasons),
        }
