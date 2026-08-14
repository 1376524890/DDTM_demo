"""卖方最低保证金 B_S^*（规范 §30）。

Seller IC：p̲_B^sys ( p_{e,Bond} λ_S B_S + p_{e,F} F_S ) ≥ G_S^dev + ε_S
    B_S^* = max{ 0, ( (G_S^dev + ε_S)/p̲_B^sys - p_{e,F} F_S ) / (p_{e,Bond} λ_S) }
若任何分母关键参数为零或未解析 → INFEASIBLE_SECURITY。
"""

from __future__ import annotations

from valor.core.errors import InfeasibleSecurityError


def seller_bond_required(
    *,
    p_breach_lower_sys: float,  # p̲_B^sys（certified）
    g_dev: float,  # G_S^dev 偏离收益
    eps_s: float,  # ε_S
    p_e_bond: float,  # bond 自动执行概率
    p_e_f: float,  # 链下额外处罚执行概率
    lambda_s: float,  # slash fraction
    f_s: float,  # F_S 链下额外处罚额 [CU]
) -> float:
    """B_S^*（§30）。"""
    if p_breach_lower_sys <= 0:
        raise InfeasibleSecurityError("p̲_B^sys 必须 >0（INFEASIBLE_SECURITY）")
    if p_e_bond <= 0 or lambda_s <= 0:
        raise InfeasibleSecurityError(
            "分母关键参数 p_e_bond/λ_S 必须 >0（INFEASIBLE_SECURITY）"
        )
    inner = (g_dev + eps_s) / p_breach_lower_sys - p_e_f * f_s
    bond = inner / (p_e_bond * lambda_s)
    return max(0.0, bond)
