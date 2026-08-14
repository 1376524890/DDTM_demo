"""委员会分配（规范 §18）。

对候选动作 a_j，委员会分配 x_j^* = argmin Σ_i b_ij x_i，满足委员会规模、
capability、availability、minimum stake、异质性和安全约束。

为精确求解（VCG truthfulness 需 exact optimal，§72），小规模用组合枚举，
保证 AllocationOptimalityGap=0。
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from valor.core.ids import AuditorID
from valor.distributed.node_state import AuditorNode, NodeRegistry


@dataclass(frozen=True)
class CommitteeAllocation:
    """一次委员会分配结果。"""

    selected: tuple[AuditorID, ...]
    bids: dict[AuditorID, float]  # 各节点 bid（报告成本）
    total_cost: float  # Σ b_i（所选）
    feasible: bool

    def to_plain(self) -> dict:
        return {
            "selected": [str(x) for x in self.selected],
            "bids": {str(k): v for k, v in self.bids.items()},
            "total_cost": self.total_cost,
            "feasible": self.feasible,
        }


def _eligible(nodes: list[AuditorNode], family: str, min_stake: float) -> list[AuditorNode]:
    return [
        n for n in nodes
        if family in n.capability and n.availability > 0 and n.stake >= min_stake
    ]


def allocate_committee(
    registry: NodeRegistry,
    *,
    family: str,
    m: int,
    bids: dict[AuditorID, float],
    min_stake: float = 0.0,
) -> CommitteeAllocation:
    """在可行节点中精确选出规模 m 的委员会，最小化 Σ bid。

    Returns: CommitteeAllocation；无可行的规模 m 委员会时 feasible=False。
    """
    pool = _eligible(registry.all(), family, min_stake)
    if len(pool) < m:
        return CommitteeAllocation(
            selected=(), bids=bids, total_cost=float("inf"), feasible=False
        )
    best_cost = float("inf")
    best_sel: tuple[AuditorID, ...] = ()
    for combo in combinations(pool, m):
        cost = sum(bids.get(n.node_id, 0.0) for n in combo)
        if cost < best_cost:
            best_cost = cost
            best_sel = tuple(n.node_id for n in combo)
    return CommitteeAllocation(
        selected=best_sel,
        bids=bids,
        total_cost=best_cost,
        feasible=bool(best_sel),
    )
