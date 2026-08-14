"""权利束与持续权利状态模型（规范 §3.2、§43、§54.4）。

R_τ = (r^class, a, t_0, t_1, q, Ψ, G, e, δ, χ, ε, retention, deleteDuty)

§54.4：核心字段均 required；不适用字段使用显式 None + not_applicable_reason，
不使用隐式 default。RightsBundle 提供 canonicalize/content_hash 供承诺绑定 H(R_τ)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from valor.core.enums import DeliveryMode, RightsState
from valor.core.hashing import content_hash
from valor.core.canonical_json import canonicalize


@dataclass(frozen=True)
class RightsBundle:
    """机器可读权利束（规范 §3.2）。

    r_class:        权利类别
    access_mode:    访问模式 a（DOWNLAD/API/COMPUTE，规范 §36）
    t0 / t1:        有效时间 [t0, t1]
    q:              最大使用次数
    purposes:       允许用途集合 Ψ（受控词汇表）
    scope:          地域/组织范围 G
    exclusivity:    排他性 e
    redistribution: 转授权/再分发权限 δ
    derivative:     衍生数据/模型权限 χ
    privacy_budget: 差分隐私总预算 ε（不适用时为 None）
    retention:      允许保留周期（不适用时为 None）
    delete_duty:    删除义务（不适用时为 None）
    not_applicable_reason: 上述不适用字段的原因（§54.4）
    """

    r_class: str
    access_mode: DeliveryMode
    t0: str
    t1: str
    q: int
    purposes: frozenset[str]
    scope: str
    exclusivity: bool
    redistribution: bool
    derivative: bool
    # 可选字段：显式 None + not_applicable_reason（§54.4）
    privacy_budget: Optional[float] = None
    retention: Optional[str] = None
    delete_duty: Optional[bool] = None
    not_applicable_reason: Optional[str] = None

    def __post_init__(self) -> None:
        from valor.core.errors import InvalidRightsError

        # 无效枚举拒绝（检查单 K：无效枚举被拒绝，用机器可读错误而非 ValueError）
        try:
            if not isinstance(self.access_mode, DeliveryMode):
                object.__setattr__(self, "access_mode", DeliveryMode(self.access_mode))
        except ValueError as e:
            raise InvalidRightsError(
                f"无效 access_mode 枚举: {self.access_mode!r}"
            ) from e
        # 负值/时间矛盾拒绝（检查单 K）
        if self.q < 0:
            raise InvalidRightsError(f"q（最大使用次数）不能为负: {self.q}")
        if self.t0 > self.t1:
            raise InvalidRightsError(f"权利有效期非法: t0={self.t0} > t1={self.t1}")
        if self.privacy_budget is not None and self.privacy_budget < 0:
            raise InvalidRightsError(
                f"privacy_budget 不能为负: {self.privacy_budget}"
            )
        # 矛盾权利：差分隐私预算仅适用于 API/Compute 查询；DOWNLOAD 不适用（§3.2）
        if (
            self.privacy_budget is not None
            and self.access_mode == DeliveryMode.DOWNLOAD_TRACEABLE
        ):
            raise InvalidRightsError(
                "矛盾权利: privacy_budget 仅适用于 API/COMPUTE 查询，"
                "与 DOWNLOAD_TRACEABLE 冲突"
            )
        # 可选字段已使用则不得同时声明 not_applicable_reason（§54.4）
        used_optional = any(
            x is not None
            for x in (self.privacy_budget, self.retention, self.delete_duty)
        )
        if used_optional and self.not_applicable_reason is not None:
            raise InvalidRightsError(
                "可选字段已使用，不应同时声明 not_applicable_reason"
            )

    @property
    def rights_hash(self) -> str:
        """H(R_τ)：权利束内容哈希（用于承诺绑定与 UsageReceipt）。"""
        return content_hash(self.to_plain())

    def to_plain(self) -> dict:
        return {
            "r_class": self.r_class,
            "access_mode": self.access_mode.value,
            "t0": self.t0,
            "t1": self.t1,
            "q": self.q,
            "purposes": sorted(self.purposes),
            "scope": self.scope,
            "exclusivity": self.exclusivity,
            "redistribution": self.redistribution,
            "derivative": self.derivative,
            "privacy_budget": self.privacy_budget,
            "retention": self.retention,
            "delete_duty": self.delete_duty,
            "not_applicable_reason": self.not_applicable_reason,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "RightsBundle":
        """从 to_plain 结果重建（round-trip）。"""
        return cls(
            r_class=d["r_class"],
            access_mode=DeliveryMode(d["access_mode"]),
            t0=d["t0"],
            t1=d["t1"],
            q=d["q"],
            purposes=frozenset(d["purposes"]),
            scope=d["scope"],
            exclusivity=d["exclusivity"],
            redistribution=d["redistribution"],
            derivative=d["derivative"],
            privacy_budget=d.get("privacy_budget"),
            retention=d.get("retention"),
            delete_duty=d.get("delete_duty"),
            not_applicable_reason=d.get("not_applicable_reason"),
        )


@dataclass(frozen=True)
class RightsStateRecord:
    """一个已授予权利的持续状态（规范 §34 U_τ(t) 与 §43 RightsState）。

    U_τ(t) = (n_t, t, purpose_t, actor_t, env_t, ε_t, revoked_t, retentionState)
    """

    rights_hash: str
    state: RightsState
    usage_count: int = 0
    privacy_budget_used: float = 0.0
    revoked: bool = False

    def to_plain(self) -> dict:
        return {
            "rights_hash": self.rights_hash,
            "state": self.state.value,
            "usage_count": self.usage_count,
            "privacy_budget_used": self.privacy_budget_used,
            "revoked": self.revoked,
        }
