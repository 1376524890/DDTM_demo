"""参数溯源与 fail-closed 解析（规范 §5）。

提供 ResolvedParameter、ParameterResolver、require_resolved()、ResolveAll()
以及单位与校验工具。核心算法只接受已解析来源的参数，无来源默认值一律 fail closed。
"""

from .models import ParameterManifest, ResolvedParameter
from .resolver import ParameterResolver, require_resolved
from .units import KnownUnits, validate_unit
from .validators import require_positive, require_unit

__all__ = [
    "ParameterManifest",
    "ResolvedParameter",
    "ParameterResolver",
    "require_resolved",
    "KnownUnits",
    "validate_unit",
    "require_positive",
    "require_unit",
]
