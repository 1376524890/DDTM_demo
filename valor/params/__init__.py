"""参数溯源与 fail-closed 解析（规范 §5，检查单 B/G/O）。

提供 ResolvedParameter、Interval、ComputedValue/MechanismResult、
ParameterResolver、require_resolved()、ResolveAll()，以及单位、来源模式
与校验工具。核心算法只接受已解析来源的参数。
"""

from .models import (
    ComputedValue,
    Interval,
    MechanismResult,
    ParameterManifest,
    ResolvedParameter,
)
from .resolver import ParameterResolver, require_resolved
from .units import (
    KnownUnits,
    assert_compatible,
    assert_money,
    compatible,
    dimension,
    validate_unit,
)
from .validators import (
    require_positive,
    require_probability,
    require_unit,
    validate_source_mode,
)
from .refs import validate_source_ref

__all__ = [
    "ComputedValue",
    "Interval",
    "MechanismResult",
    "ParameterManifest",
    "ResolvedParameter",
    "ParameterResolver",
    "require_resolved",
    "KnownUnits",
    "assert_compatible",
    "assert_money",
    "compatible",
    "dimension",
    "validate_unit",
    "require_positive",
    "require_probability",
    "require_unit",
    "validate_source_mode",
    "validate_source_ref",
]
