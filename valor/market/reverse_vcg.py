"""Reverse VCG 支付（规范 §18）。

被选节点支付：p_ij^A = b_ij + C_{j,-i}^* - C_j^*
其中 C_{j,-i}^* 必须是删除 winner 后仍可行的精确最优解；若不存在替补委员会
→ COUNTERFACTUAL_INFEASIBLE（该配置不可进入 VCG payment）。

VCG truthfulness 主实验只在单参数成本、准线性效用、公开可行集假设下声明。
"""

from __future__ import annotations

from valor.core.errors import CounterfactualInfeasibleError
from valor.core.ids import AuditorID

from .committee_allocation import allocate_committee


def reverse_vcg_payments(
    registry,
    *,
    family: str,
    m: int,
    bids: dict[AuditorID, float],
    min_stake: float = 0.0,
) -> tuple[dict[AuditorID, float], dict[AuditorID, float]]:
    """计算 Reverse VCG 支付。

    Returns: (payments, counterfactual_costs)。
    """
    base = allocate_committee(
        registry, family=family, m=m, bids=bids, min_stake=min_stake
    )
    if not base.feasible:
        raise CounterfactualInfeasibleError("无可行委员会，VCG 支付不可计算")
    payments: dict[AuditorID, float] = {}
    cfcosts: dict[AuditorID, float] = {}
    for winner in base.selected:
        # 删除 winner 后的反事实最优
        # 用临时 registry 排除 winner（构造不含该节点的 bid/eligible 视图）
        cfcost = _counterfactual_cost(
            registry, family=family, m=m, bids=bids, exclude=winner,
            min_stake=min_stake,
        )
        if cfcost is None:
            raise CounterfactualInfeasibleError(
                f"删除 winner {winner} 后无替补委员会（COUNTERFACTUAL_INFEASIBLE）"
            )
        cfcosts[winner] = cfcost
        # p = b_i + C_{j,-i}^* - C_j^*
        payments[winner] = bids.get(winner, 0.0) + cfcost - base.total_cost
    return payments, cfcosts


def _counterfactual_cost(registry, *, family, m, bids, exclude, min_stake) -> float | None:
    """删除 exclude 节点后规模 m 委员会的最优成本；不可行为 None。"""
    # 构造排除后的 registry
    from valor.distributed.node_state import NodeRegistry

    sub = NodeRegistry()
    for n in registry.all():
        if n.node_id != exclude:
            sub.register(n)
    alloc = allocate_committee(
        sub, family=family, m=m, bids=bids, min_stake=min_stake
    )
    return alloc.total_cost if alloc.feasible else None
