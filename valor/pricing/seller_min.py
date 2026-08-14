"""卖方最低可接受价（规范 §40）。

    P_τ^min = c_D^marg + C_{A,S}^pay + C_B^cap + C_{R,S}^pay + R_S^post + OC_S(R_τ) + Π_S^0
固定数据生产成本 F_D 不在每笔交易重复加入（§40/§29）。
"""

from __future__ import annotations


def seller_min_price(
    *,
    c_marg: float,  # c_D^marg 单笔复制/交付边际成本
    c_a_s_pay: float,  # 卖方承担的审计支付
    c_b_cap: float,  # 卖方保证金资本成本
    c_r_s_pay: float,  # 卖方权利执行成本
    r_s_post: float,  # 卖方剩余责任
    oc_s: float,  # 权利束机会成本 OC_S(R_τ)
    pi_s0: float,  # 卖方保留效用
) -> float:
    """P_τ^min（§40）。"""
    return (
        c_marg + c_a_s_pay + c_b_cap + c_r_s_pay + r_s_post + oc_s + pi_s0
    )
