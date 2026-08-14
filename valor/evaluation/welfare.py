"""社会福利（规范 §44）。

SW_full = V^real - C_D^marg - C_I - C_audit-service^res - C_protocol^res - C_B^cap
          - C_{A,cap} - C_{B,use}^cap - ExpectedResidualLoss
C_audit-service^res = Σ_i k_i；C_protocol^res = C_BFT + C_network + C_chain +
C_challenge + C_dispute + C_lineage + C_usage-enforcement。
交易价、审计支付、可重新分配的罚没是内部转移，不在包含全部参与者的社会福利里
重复扣除（§44 / §73 第 11 条）。
"""

from __future__ import annotations


def audit_service_resource_cost(k_i_list: list[float]) -> float:
    """C_audit-service^res = Σ k_i（§44）。"""
    return sum(k_i_list)


def protocol_resource_cost(*, bft, network, chain, challenge, dispute,
                           lineage, usage_enforcement) -> float:
    """C_protocol^res（§44）。"""
    return (bft + network + chain + challenge + dispute + lineage + usage_enforcement)


def social_welfare_full(
    *,
    v_real,
    c_d_marg,
    c_i,
    c_audit_service_res,
    c_protocol_res,
    c_b_cap,
    c_a_cap,
    c_b_use_cap,
    expected_residual_loss,
) -> float:
    """SW_full（§44）。"""
    return (
        v_real - c_d_marg - c_i - c_audit_service_res - c_protocol_res
        - c_b_cap - c_a_cap - c_b_use_cap - expected_residual_loss
    )
