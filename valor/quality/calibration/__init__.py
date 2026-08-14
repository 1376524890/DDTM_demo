"""质量校准层（规范 §21、§58 RQ2）。

- primitive.py: 估计 λ_p^prim（单节点 primitive 的检出/误报），生成检测曲线
- action.py:    估计分布式动作似然 Λ_j（§21.2）
- metrics.py:   校准/检测指标工具
"""

from .primitive import estimate_primitive_likelihood, detection_curve
from .action import estimate_action_likelihood

__all__ = [
    "estimate_primitive_likelihood",
    "detection_curve",
    "estimate_action_likelihood",
]
