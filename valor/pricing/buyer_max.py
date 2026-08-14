"""买方最高愿付（规范 §39）。

    P_τ^max = max{ 0, min[ W_B^rem, V̲_{D,R}^gross - C_I - C_{A,B}^pay - C_R^pay - C_{B,use}^cap - R_B^post ] }
Buyer Usage Bond 本金不扣除，只扣其资本机会成本 C_{B,use}^cap（§39）。
"""

from __future__ import annotations


def buyer_max_price(
    *,
    w_b_rem: float,  # W_B^rem 买方剩余预算
    v_gross_lower: float,  # V̲_{D,R}^gross 保守下界
    c_i: float,  # 整合成本
    c_a_b_pay: float,  # 买方承担的审计支付
    c_r_pay: float,  # 权利执行现金成本
    c_b_use_cap: float,  # usage bond 资本机会成本
    r_b_post: float,  # 买方剩余风险
) -> float:
    """P_τ^max（§39）。"""
    val = v_gross_lower - c_i - c_a_b_pay - c_r_pay - c_b_use_cap - r_b_post
    return max(0.0, min(w_b_rem, val))
