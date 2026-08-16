"""Audit Likelihood Calibration V2（P0-2）—— 真实经验多项分布似然。

对齐用户方案：删除人为 `L=0.5` 映射，改用真实三状态(G/L/B) × 多结果
(PASS/CLAIM_NOT_SUPPORTED/BREACH_EVIDENCE/INCONCLUSIVE) 的经验计数：

    n_{a,c,x,y} = #{ action=a, breach_family=c, X=x, Y=y }

直接估计（Dirichlet smoothing）：

    Λ_{a,c}(y | x) = (n_{a,c,x,y} + α_y) / (Σ_y' n_{a,c,x,y'} + Σ_y' α_y')

天然满足 Σ_y Λ(y | x) = 1。

三种 ground truth（论文强调 L≠B）：
    G : 数据和声明都正常
    L : 卖方诚实，但 buyer-specific suitability 不足（不触发 breach）
    B : commitment/claim/delivery 存在真实 seller breach

R_cal（calibration 数据）与 R_cert（certification 数据）严格隔离：
    似然只用 R_cal 估计；认证 TP/FN 只用 R_cert。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from valor.core.hashing import content_hash

# 三状态与多结果
STATES = ("G", "L", "B")
OUTCOMES = ("PASS", "CLAIM_NOT_SUPPORTED", "BREACH_EVIDENCE", "INCONCLUSIVE")

# 默认 Dirichlet 先验（平滑；不预设 G/L/B 区分，只防零计数）
DEFAULT_ALPHA = {y: 1.0 for y in OUTCOMES}


@dataclass
class EmpiricalLikelihood:
    """一个 (action, breach_family) 的经验似然 Λ(y|x)。

    counts[x][y] = n_{a,c,x,y}（经验计数）
    alpha[y]     = Dirichlet smoothing 参数
    """

    action_id: str
    breach_family: str
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    alpha: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_ALPHA))

    def add(self, state: str, outcome: str) -> None:
        """记录一次 (X=x, Y=y) 观测。"""
        if state not in STATES:
            raise ValueError(f"未知状态 {state!r}，须在 {STATES}")
        if outcome not in OUTCOMES:
            raise ValueError(f"未知结果 {outcome!r}，须在 {OUTCOMES}")
        self.counts.setdefault(state, {y: 0 for y in OUTCOMES})[outcome] += 1

    def likelihood_rows(self) -> dict[str, dict[str, float]]:
        """Λ(y|x) = (n_{x,y}+α_y)/(Σ n_{x,y'}+Σ α_y')。

        返回 rows[y][x]，供 StateBelief/bayes_update 使用（rows[y][x] = Λ(y|x)）。
        """
        rows: dict[str, dict[str, float]] = {y: {} for y in OUTCOMES}
        for state in STATES:
            counts = self.counts.get(state, {y: 0 for y in OUTCOMES})
            denom = sum(counts.get(y, 0) for y in OUTCOMES) + sum(self.alpha.values())
            for y in OUTCOMES:
                numer = counts.get(y, 0) + self.alpha.get(y, 0.0)
                rows[y][state] = numer / denom if denom > 0 else 0.0
        return rows

    def n_observations(self) -> int:
        return sum(sum(c.values()) for c in self.counts.values())

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "breach_family": self.breach_family,
            "counts": self.counts,
            "alpha": self.alpha,
            "n_observations": self.n_observations(),
            "rows": self.likelihood_rows(),
        }


def empirical_likelihood_from_counts(
    *,
    action_id: str,
    breach_family: str,
    counts: dict[str, dict[str, int]],
    alpha: dict[str, float] | None = None,
) -> EmpiricalLikelihood:
    """从计数直接构造（用于冻结 artifact round-trip）。"""
    lik = EmpiricalLikelihood(action_id=action_id, breach_family=breach_family,
                              counts=counts,
                              alpha=alpha or dict(DEFAULT_ALPHA))
    return lik


def freeze_empirical_likelihood(lik: EmpiricalLikelihood, *, policy_hash: str,
                                calibration_hash: str) -> dict:
    """冻结经验似然 artifact（含确定性 hash）。"""
    data = {
        "action_id": lik.action_id,
        "breach_family": lik.breach_family,
        "counts": lik.counts,
        "alpha": lik.alpha,
        "rows": lik.likelihood_rows(),
        "n_observations": lik.n_observations(),
        "policy_hash": policy_hash,
        "calibration_hash": calibration_hash,
        "normalized_sum_per_state": {
            s: round(sum(lik.likelihood_rows()[y][s] for y in OUTCOMES), 9)
            for s in STATES
        },
    }
    data["artifact_hash"] = content_hash({
        "kind": "audit_likelihood_v2",
        "action_id": lik.action_id, "breach_family": lik.breach_family,
        "counts": lik.counts, "alpha": lik.alpha, "policy_hash": policy_hash,
        "calibration_hash": calibration_hash,
    })
    return data


__all__ = [
    "STATES", "OUTCOMES", "DEFAULT_ALPHA", "EmpiricalLikelihood",
    "empirical_likelihood_from_counts", "freeze_empirical_likelihood",
]
