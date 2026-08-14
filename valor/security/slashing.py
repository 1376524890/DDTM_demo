"""质押与罚没（规范 §19）。

诚实效用 U_i^H = p_i^A - k_i - κ_A B_{A,i} T_A。
挑战概率 ρ、强验证成功证明作恶概率 p_{v,i}、slash fraction λ_A：
    ρ p_{v,i} λ_A B_{A,i} ≥ G_i^dev + ε_A
最低 stake：
    B_{A,i}^min = (G_i^dev + ε_A) / (ρ p_{v,i} λ_A)
ρ、p_{v,i}、G_i^dev 都必须解析来源；不存在全局默认 challenge rate。
"""

from __future__ import annotations


def minimum_auditor_stake(
    *,
    g_dev: float,  # 相对诚实执行的额外收益（含贿赂/串谋）
    epsilon_a: float,  # IC 松弛
    rho: float,  # 挑战概率（解析来源）
    p_v: float,  # 强验证证明作恶概率
    lambda_a: float,  # slash fraction
) -> float:
    """B_{A,i}^min = (G_i^dev + ε_A)/(ρ p_v λ_A)（§19）。"""
    if not (0 < rho <= 1) or not (0 < p_v <= 1) or not (0 < lambda_a <= 1):
        from valor.core.errors import InfeasibleSecurityError

        raise InfeasibleSecurityError(
            "ρ / p_v / λ_A 须在 (0,1]，否则最低 stake 不可行"
        )
    return (g_dev + epsilon_a) / (rho * p_v * lambda_a)
