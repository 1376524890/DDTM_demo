"""质量校准层（规范 §21、§58 RQ2）。

- primitive.py: 估计 λ_p^prim（单节点 primitive 的检出/误报），生成检测曲线
- action.py:    占位（分布式动作似然 Λ_action 属 Phase 3）
- metrics.py:   校准/检测指标工具
"""

from .primitive import estimate_primitive_likelihood, detection_curve

__all__ = ["estimate_primitive_likelihood", "detection_curve"]
