"""单位定义、维度与兼容校验（检查单 F，规范 §5/§12）。

要求：
- 明确区分 money / rate / duration / count / ratio / probability（dimensionless）/ time
- 不兼容单位相加必须抛 UNIT_MISMATCH
- probability 明确为 dimensionless，输入自动校验 0<=p<=1（见 validators）
- 资本成本不得"年利率 × 小时"直接相乘而不转换单位 → 用维度区分 rate 与 time
- resolver 在算法调用前执行 unit compatibility validation
"""

from __future__ import annotations

from valor.core.errors import UnitMismatchError


class KnownUnits:
    """VALOR 已知单位常量。"""

    CU = "CU"  # 统一货币单位
    UNITLESS = "unitless"  # 无量纲（纯系数）
    COUNT = "count"  # 次数 / 数量
    TIME = "time"  # 时间（秒/区间）
    DURATION = "duration"  # 持续时长
    RATE = "rate"  # 单位时间速率（如年利率、挑战率）
    PROBABILITY = "probability"  # 概率 [0,1]（dimensionless）
    RATIO = "ratio"  # 比例 [0,1]（dimensionless）
    HASH = "hash"  # 哈希摘要（hex）


# 单位 → 维度（检查单 F：维度区分）
UNIT_DIMENSION: dict[str, str] = {
    KnownUnits.CU: "money",
    KnownUnits.UNITLESS: "dimensionless",
    KnownUnits.COUNT: "count",
    KnownUnits.TIME: "time",
    KnownUnits.DURATION: "time",
    KnownUnits.RATE: "rate",
    KnownUnits.PROBABILITY: "dimensionless",
    KnownUnits.RATIO: "dimensionless",
    KnownUnits.HASH: "hash",
}

# 已知单位白名单
_KNOWN = set(UNIT_DIMENSION)


def validate_unit(unit: str, *, name: str = "参数") -> str:
    """校验单位是否为已知单位；未知抛 UNIT_MISMATCH。"""
    if unit not in _KNOWN:
        raise UnitMismatchError(f"[{name}] 未知单位: {unit!r}")
    return unit


def dimension(unit: str) -> str:
    """返回单位所属维度；未知单位抛 UNIT_MISMATCH。"""
    validate_unit(unit)
    return UNIT_DIMENSION[unit]


def compatible(a: str, b: str, *, name: str = "单位") -> bool:
    """判断两单位是否同维度（可兼容运算）。"""
    return dimension(a) == dimension(b)


def assert_compatible(a: str, b: str, *, name: str = "单位") -> None:
    """断言两单位同维度；否则抛 UNIT_MISMATCH。"""
    if not compatible(a, b):
        raise UnitMismatchError(
            f"[{name}] 单位不兼容: {a}（{dimension(a)}） vs {b}（{dimension(b)}）"
        )


def assert_money(unit: str, *, name: str = "金额") -> None:
    """断言单位为 [CU]（money 维度）；否则抛 UNIT_MISMATCH。"""
    if dimension(unit) != "money":
        raise UnitMismatchError(f"[{name}] 期望货币单位 [CU]，实际 {unit!r}")
