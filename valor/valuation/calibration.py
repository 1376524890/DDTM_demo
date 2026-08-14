"""价值校准与保守下界（规范 §28）。

    ê_t = V_t^real - V̂_t^gross（严格独立 residual）
    V̲_{t+1}^gross = V̂_{t+1}^gross + Quantile_{α_V}(Ê_t)
    Coverage_V = P(V^real ≥ V̲^gross)
"""

from __future__ import annotations

import numpy as np


def value_lower_bound_quantile(
    realized: np.ndarray,
    predicted: np.ndarray,
    alpha_v: float,
) -> float:
    """用历史 residual 的 α_V 分位数求保守下界增量。"""
    residuals = np.asarray(realized) - np.asarray(predicted)
    q = np.quantile(residuals, alpha_v)
    return float(q)


class ValueCalibrator:
    """价值校准器：维护独立 residual 集，输出 V̲_gross。"""

    def __init__(self, alpha_v: float) -> None:
        self.alpha_v = alpha_v
        self._residuals: list[float] = []

    def update(self, realized: float, predicted: float) -> None:
        self._residuals.append(realized - predicted)

    def lower_bound_adjustment(self) -> float:
        if not self._residuals:
            return 0.0
        return float(np.quantile(self._residuals, self.alpha_v))

    def coverage(self) -> float | None:
        """Coverage_V = P(V^real ≥ V̲^gross)，基于已观察 residual。"""
        if not self._residuals:
            return None
        adj = self.lower_bound_adjustment()
        covered = sum(1 for r in self._residuals if r >= adj)
        return covered / len(self._residuals)
