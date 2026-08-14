"""单位定义与校验（规范 §5 / §12 / §5.3 UNIT_MISMATCH）。

记录 VALOR 使用的已知单位集合；单位不在此集合或与预期不符时抛错。
"""

from __future__ import annotations

from valor.core.errors import UnitMismatchError


class KnownUnits:
    """VALOR 已知单位常量。

    核心经济量统一 [CU]（规范 §12）；其余为物理/统计单位。
    """

    CU = "CU"  # 统一货币单位
    UNITLESS = "unitless"  # 无量纲（概率、比例、系数）
    COUNT = "count"  # 次数 / 数量
    TIME = "time"  # 时间（秒/区间）
    PROBABILITY = "probability"  # 概率 [0,1]
    HASH = "hash"  # 哈希摘要（hex）
    RATIO = "ratio"  # 比例 [0,1]


# 已知单位白名单（用于校验 unit 是否合法）
_KNOWN = {
    KnownUnits.CU,
    KnownUnits.UNITLESS,
    KnownUnits.COUNT,
    KnownUnits.TIME,
    KnownUnits.PROBABILITY,
    KnownUnits.HASH,
    KnownUnits.RATIO,
}


def validate_unit(unit: str, *, name: str = "参数") -> str:
    """校验单位是否为已知单位；未知单位抛 UNIT_MISMATCH。"""
    if unit not in _KNOWN:
        raise UnitMismatchError(f"[{name}] 未知单位: {unit!r}")
    return unit
