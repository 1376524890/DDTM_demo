"""私人效用（规范 §44）。

买方 U_B = V^real - P* - C_I - C_{A,B}^pay - C_R^pay - C_{B,use}^cap - L_B^real
卖方 Π_S = P* - c_D^marg - C_{A,S}^pay - C_B^cap - C_{R,S}^pay - OC_S^real - Penalty_S^real
审计者 U_{A,i} = p_i^A - k_i - κ_A B_{A,i} T_A - Slash_i^real
"""

from __future__ import annotations


def buyer_utility(*, v_real, price, c_i, c_a_b_pay, c_r_pay, c_b_use_cap, l_b_real) -> float:
    """U_B（§44）。"""
    return v_real - price - c_i - c_a_b_pay - c_r_pay - c_b_use_cap - l_b_real


def seller_profit(*, price, c_marg, c_a_s_pay, c_b_cap, c_r_s_pay, oc_s_real, penalty_s_real) -> float:
    """Π_S（§44）。"""
    return price - c_marg - c_a_s_pay - c_b_cap - c_r_s_pay - oc_s_real - penalty_s_real


def auditor_utility(*, p_i_a, k_i, kappa_a, bond_a_i, t_a, slash_i_real) -> float:
    """U_{A,i}（§44）。"""
    return p_i_a - k_i - kappa_a * bond_a_i * t_a - slash_i_real
