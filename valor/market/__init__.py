"""审计节点市场（规范 §18 Reverse VCG）。

- committee_allocation: 委员会分配（满足规模/capability/stake/可用性约束）
- reverse_vcg:          Reverse VCG 支付（精确最优 + 反事实可行性）
- payments:             支付与 escrow 守卫
"""

from .committee_allocation import CommitteeAllocation, allocate_committee
from .reverse_vcg import reverse_vcg_payments

__all__ = ["CommitteeAllocation", "allocate_committee", "reverse_vcg_payments"]
