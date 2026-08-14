"""分布式动作似然 Λ_j（规范 §21.2 / Phase 3）。

Λ_j(y,x) = P(Y_j = y | X = x, a_j)，用独立校准数据 + 受控注入估计。
包含节点故障/恶意报告/challenge/quorum 影响，不能直接等同于单节点
primitive accuracy（§7 三层禁止混用）。
"""

from __future__ import annotations

from valor.audit.likelihood import ActionLikelihood


def estimate_action_likelihood(
    action_id: str,
    *,
    observations: list[tuple[str, str]],  # [(true_state, observed_outcome)]
    states: tuple[str, ...] = ("G", "L", "B"),
    outcomes: tuple[str, ...] = ("PASS", "QUALITY_FAIL", "BREACH_EVIDENCE"),
) -> ActionLikelihood:
    """从 (true_state, observed_outcome) 校准数据估计 Λ_j(y,x)。

    对每个状态 x，统计各观测 y 的频率并归一化 Σ_y Λ_j(y,x)=1。
    """
    rows: dict[str, dict[str, float]] = {y: {x: 0.0 for x in states} for y in outcomes}
    state_total = {x: 0.0 for x in states}
    for true_state, obs in observations:
        if true_state not in state_total or obs not in rows:
            continue
        rows[obs][true_state] += 1.0
        state_total[true_state] += 1.0
    for x in states:
        tot = state_total[x] if state_total[x] > 0 else 1.0
        for y in outcomes:
            rows[y][x] = rows[y][x] / tot
    return ActionLikelihood(action_id=action_id, rows=rows)
