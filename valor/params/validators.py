"""参数校验器（fail-closed）。

所有校验基于显式传入的 ResolvedParameter，不引入隐藏默认值。
校验失败抛对应 VALORError。
"""

from __future__ import annotations

from valor.core.errors import UnresolvedParameterError

from .models import ResolvedParameter
from .units import validate_unit


def require_unit(p: ResolvedParameter, expected: str) -> ResolvedParameter:
    """断言参数单位与期望一致（规范 §5.3 UNIT_MISMATCH）。"""
    validate_unit(p.unit, name=p.name)
    if p.unit != expected:
        from valor.core.errors import UnitMismatchError

        raise UnitMismatchError(
            f"[{p.name}] 期望单位 {expected}，实际 {p.unit}"
        )
    return p


def require_positive(p: ResolvedParameter) -> ResolvedParameter:
    """断言参数为有限正数（无默认值，直接校验显式值）。"""
    v = p.value
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise UnresolvedParameterError(
            f"[{p.name}] 非数值参数，无法做正数校验: {v!r}"
        )
    if not (v > 0):
        from valor.core.errors import OutOfCertifiedRangeError

        raise OutOfCertifiedRangeError(f"[{p.name}] 必须为正数，实际 {v}")
    return p


def require_probability(p: ResolvedParameter) -> ResolvedParameter:
    """断言参数为 [0,1] 概率。"""
    v = p.value
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise UnresolvedParameterError(
            f"[{p.name}] 非数值参数，无法做概率校验: {v!r}"
        )
    if not (0.0 <= v <= 1.0):
        from valor.core.errors import OutOfCertifiedRangeError

        raise OutOfCertifiedRangeError(f"[{p.name}] 概率越界 [0,1]: {v}")
    return p
