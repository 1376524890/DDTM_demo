"""保证金资本成本（规范 §31）。

    C_B^cap = κ_S ∫ B_S(t) dt
P0 分段实现：C_B^cap = κ_S ( B_S^pre T_pre + B_S^* T_post )。
时间区间不得重叠计费。
"""

from __future__ import annotations


def capital_cost(
    *,
    kappa_s: float,  # 资本占用费率（时间单位^-1）
    bond_pre: float,
    bond_required: float,
    t_pre: float,
    t_post: float,
) -> float:
    """C_B^cap = κ_S (B_S^pre T_pre + B_S^* T_post)（§31）。"""
    return kappa_s * (bond_pre * t_pre + bond_required * t_post)
