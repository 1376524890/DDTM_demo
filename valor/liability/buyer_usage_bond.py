"""买方 usage bond（规范 §38）。

    p̲_U^sys ( p_{e,UBond} λ_B B_B + p_{e,UF} F_B ) ≥ G_B^misuse + ε_B
    B_B^use,* = max{ 0, ( (G_B^misuse + ε_B)/p̲_U^sys - p_{e,UF} F_B ) / (p_{e,UBond} λ_B) }

该功能为可配置合同责任；不需要 usage bond 的场景通过显式合同参数令风险结构满足
约束，而不是在代码中默认为零（§38）。
"""

from __future__ import annotations

from valor.core.errors import InfeasibleSecurityError


def buyer_usage_bond_required(
    *,
    p_misuse_lower_sys: float,  # p̲_U^sys 系统误用检测保守概率
    g_misuse: float,  # G_B^misuse 买方偏离收益
    eps_b: float,  # ε_B
    p_e_ubond: float,  # usage bond 执行概率
    p_e_uf: float,  # 额外处罚执行概率
    lambda_b: float,  # slash fraction
    f_b: float,  # 额外处罚额 [CU]
) -> float:
    """B_B^use,*（§38）。"""
    if p_misuse_lower_sys <= 0:
        raise InfeasibleSecurityError("p̲_U^sys 必须 >0（INFEASIBLE_SECURITY）")
    if p_e_ubond <= 0 or lambda_b <= 0:
        raise InfeasibleSecurityError(
            "分母关键参数 p_e_ubond/λ_B 必须 >0（INFEASIBLE_SECURITY）"
        )
    inner = (g_misuse + eps_b) / p_misuse_lower_sys - p_e_uf * f_b
    bond = inner / (p_e_ubond * lambda_b)
    return max(0.0, bond)
