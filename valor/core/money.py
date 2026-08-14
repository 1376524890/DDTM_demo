"""统一货币单位与金额校验。

对齐规范：
- §12/§24/§25/§40 统一 Currency Unit [CU]
- §5.2 参数携带 unit；§5.3 单位不一致返回 UNIT_MISMATCH

设计（D102）：经济量以浮点标量 + unit 表示；Money 为带单位的值对象，
单位不一致在赋值处即抛 UnitMismatchError，避免混算。
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import UnitMismatchError

# 统一货币单位标识（规范 §12）
CURRENCY_UNIT = "CU"


def assert_unit(actual: str, expected: str = CURRENCY_UNIT, *, name: str = "值") -> None:
    """断言金额单位一致；否则抛 UNIT_MISMATCH。"""
    if actual != expected:
        raise UnitMismatchError(
            f"[{name}] 单位不一致: 期望 {expected}，实际 {actual}"
        )


def to_cu(value: float) -> "Money":
    """便捷构造 [CU] 金额。"""
    return Money(value, CURRENCY_UNIT)


@dataclass(frozen=True)
class Money:
    """带统一货币单位的金额值对象。

    所有算术自动校验单位一致；相加/相减/比较仅在单位相同时合法。
    """

    amount: float
    unit: str = CURRENCY_UNIT

    def __post_init__(self) -> None:
        assert_unit(self.unit, CURRENCY_UNIT, name="Money")

    # ---- 算术：仅允许同单位 ----
    def _coerce(self, other: "Money") -> float:
        assert_unit(other.unit, self.unit, name="Money 运算")
        return other.amount

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + self._coerce(other), self.unit)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.amount - self._coerce(other), self.unit)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.unit)

    def __mul__(self, scalar: float) -> "Money":
        return Money(self.amount * scalar, self.unit)

    __rmul__ = __mul__

    # ---- 比较 ----
    def __lt__(self, other: "Money") -> bool:
        return self.amount < self._coerce(other)

    def __le__(self, other: "Money") -> bool:
        return self.amount <= self._coerce(other)

    def __gt__(self, other: "Money") -> bool:
        return self.amount > self._coerce(other)

    def __ge__(self, other: "Money") -> bool:
        return self.amount >= self._coerce(other)

    def to_plain(self) -> dict:
        """返回 JSON 原生表示。"""
        return {"amount": self.amount, "unit": self.unit}

    @classmethod
    def from_plain(cls, d: dict) -> "Money":
        """从 to_plain 结果重建（round-trip）。"""
        return cls(d["amount"], d["unit"])
