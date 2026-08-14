"""质量 reference 实现（锁定版本 / 独立代码路径，规范 §15）。

reference 与 native 使用相同数据、相同约束和相同对象承诺，但由独立实现产生，
供 Reference Reproduction Gate 比较（§47 Q0）。
"""

from .deequ_adapter import DeequReferenceAdapter
from .cleanlab_adapter import CleanlabReferenceAdapter
from .scipy_stats_adapter import ScipyStatsReferenceAdapter

__all__ = [
    "DeequReferenceAdapter",
    "CleanlabReferenceAdapter",
    "ScipyStatsReferenceAdapter",
]
