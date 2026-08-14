"""参数校验器（fail-closed）。

- require_unit / require_positive / require_probability：基于显式 ResolvedParameter
- validate_source_mode：来源模式门禁（检查单 B2）——production/experiment 禁 TEST_FIXTURE
"""

from __future__ import annotations

from valor.core.enums import ConfigMode, ParamSource
from valor.core.errors import (
    InvalidSourceKindError,
    UnresolvedParameterError,
)

from .models import ResolvedParameter
from .units import validate_unit

# TEST_FIXTURE 仅允许出现在 TEST 模式（检查单 B2）
_FIXTURE_ALLOWED_MODES = {ConfigMode.TEST}


def validate_source_mode(
    source_kind: ParamSource, mode: ConfigMode
) -> ParamSource:
    """校验来源类型与使用模式是否兼容（检查单 B2）。

    mode == TEST：允许 TEST_FIXTURE。
    mode in {EXPERIMENT, PRODUCTION}：禁止 TEST_FIXTURE。

    不允许把 TEST_FIXTURE 改名成 CONTRACT_INPUT 绕过（改名的本质是换来源，
    由 source_ref 的 scheme 校验与代码审查共同约束）。
    """
    if source_kind == ParamSource.TEST_FIXTURE and mode not in _FIXTURE_ALLOWED_MODES:
        raise InvalidSourceKindError(
            f"TEST_FIXTURE 不允许用于 mode={mode.value}（仅 TEST 模式可用）"
        )
    return source_kind


def require_unit(p: ResolvedParameter, expected: str) -> ResolvedParameter:
    """断言参数单位与期望一致（UNIT_MISMATCH）。"""
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
    """断言参数为 [0,1] 概率（检查单 F：probability 自动验证）。"""
    v = p.value
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise UnresolvedParameterError(
            f"[{p.name}] 非数值参数，无法做概率校验: {v!r}"
        )
    if not (0.0 <= v <= 1.0):
        from valor.core.errors import OutOfCertifiedRangeError

        raise OutOfCertifiedRangeError(f"[{p.name}] 概率越界 [0,1]: {v}")
    return p
