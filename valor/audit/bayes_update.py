"""贝叶斯更新（规范 §24）。

    π'_x = Λ_j(y,x) π_x / Σ_{x'} Λ_j(y,x') π_{x'}
"""

from __future__ import annotations

from .state_model import StateBelief


def bayes_update(
    belief: StateBelief,
    likelihood_row: dict[str, float],  # {state: Λ_j(y, state)}
) -> StateBelief:
    """按观测结果 y 更新信念。"""
    probs = {
        "g": belief.prob_g * likelihood_row.get("G", 0.0),
        "l": belief.prob_l * likelihood_row.get("L", 0.0),
        "b": belief.prob_b * likelihood_row.get("B", 0.0),
    }
    total = sum(probs.values())
    if total <= 0:
        raise ValueError("后验未归一化（total<=0），似然或先验非法")
    return StateBelief(
        prob_g=probs["g"] / total,
        prob_l=probs["l"] / total,
        prob_b=probs["b"] / total,
    )
