"""卖方资格硬门槛（规范 §6 Entitled(S, A_D, R_τ)）。

硬约束失败时交易不进入 Data-VOI / Audit-VOI，抛 EntitlementError。
该层处理不可通过经济权衡放松的约束（卖方无权授予某排他权、数据版本被撤销等）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.errors import EntitlementError


@dataclass(frozen=True)
class Entitled:
    """卖方资格评估结果。

    grant_authority:   卖方对该资产/版本是否有权授权（True/False）
    version_revoked:   该数据版本是否已被撤销（True/False）
    reasons:           判定理由列表（供审计/日志）
    """

    grant_authority: bool
    version_revoked: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passes(self) -> bool:
        """Entitled=1 当且仅当卖方有权且版本未撤销。"""
        return self.grant_authority and not self.version_revoked

    def enforce(self) -> None:
        """硬门槛校验；不通过抛 EntitlementError。"""
        if not self.passes:
            raise EntitlementError(
                "卖方资格硬门槛不通过",
                detail=self.to_plain(),
            )

    def to_plain(self) -> dict:
        return {
            "grant_authority": self.grant_authority,
            "version_revoked": self.version_revoked,
            "passes": self.passes,
            "reasons": list(self.reasons),
        }
