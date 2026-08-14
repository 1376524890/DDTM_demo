"""权利兼容性校验（规范 §32 Compatible(R_τ, L_D(t))）。

新权利授予前必须满足 Compatible(R_τ, L_D(t)) = 1。
例如：已存在 exclusive license 时，新的冲突授权不得同时存在。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.errors import EntitlementError

from .models import RightsBundle


@dataclass(frozen=True)
class Compatible:
    """兼容性评估结果。

    conflict:          是否存在冲突（True=不兼容）
    reasons:           冲突/通过原因列表
    """

    conflict: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passes(self) -> bool:
        """Compatible=1 当且仅当无冲突。"""
        return not self.conflict

    def enforce(self) -> None:
        """硬门槛校验；不通过抛 EntitlementError。"""
        if self.conflict:
            raise EntitlementError(
                "权利兼容性校验不通过（重复出售冲突）",
                detail=self.to_plain(),
            )

    def to_plain(self) -> dict:
        return {"conflict": self.conflict, "passes": self.passes,
                "reasons": list(self.reasons)}


def check_compatible(
    new: RightsBundle,
    existing: list[RightsBundle],
) -> Compatible:
    """检查新权利束与已有活跃许可的兼容性。

    规则（原型最小实现，后续可扩展）：
    - 新排他授权与任一已有排他授权冲突；
    - 新授权范围与已有排他授权范围重叠时冲突（此处按 scope 相同判定冲突）。
    """
    reasons: list[str] = []
    conflict = False
    for old in existing:
        if new.exclusivity and old.exclusivity:
            conflict = True
            reasons.append(
                f"与已有排他授权冲突（新 exclusive × 已有 exclusive）"
            )
        elif old.exclusivity and new.scope == old.scope:
            conflict = True
            reasons.append(
                f"新授权 scope={new.scope} 与已有排他授权 scope 重叠"
            )
    return Compatible(conflict=conflict, reasons=tuple(reasons))
