"""分布式动作似然 Λ_j（规范 §21.2）。

占位：Λ_j(y,x) = P(Y_j=y | X=x, a_j)，包含节点故障/恶意报告/challenge/quorum
影响，不能直接等同于单节点 primitive accuracy。完整实现属 Phase 3
（分布式审计校准）；此处保留接口与说明，避免与 λ_p^prim 混用（§7）。
"""

from __future__ import annotations


class ActionLikelihoodStub:
    """Phase 1 占位：动作级似然在 Phase 3 实现。"""

    def __call__(self, *args, **kwargs):
        raise NotImplementedError(
            "ActionLikelihood 属 Phase 3（分布式审计校准）"
        )
