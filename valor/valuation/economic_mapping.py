"""经济映射：效用 → 货币毛价值（规范 §26）。

cost-sensitive payoff 矩阵 R_b = [[r_TN, r_FP],[r_FN, r_TP]]（单位 [CU]）。
    U_b(θ) = N_b Σ_{y,ŷ} P(y,ŷ; θ) r_{y,ŷ}
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from valor.core.money import CURRENCY_UNIT


@dataclass(frozen=True)
class PayoffMatrix:
    """cost-sensitive payoff 矩阵（§26），单位 [CU]。"""

    r_tn: float
    r_fp: float
    r_fn: float
    r_tp: float
    unit: str = CURRENCY_UNIT

    def to_matrix(self) -> np.ndarray:
        # [[r_TN, r_FP],[r_FN, r_TP]]
        return np.array([[self.r_tn, self.r_fp], [self.r_fn, self.r_tp]])


def utility_from_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    payoff: PayoffMatrix,
) -> float:
    """U_b(θ) = N_b Σ P(y,ŷ) r_{y,ŷ}（§26）。"""
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    n = len(y_true)
    if n == 0:
        return 0.0
    # confusion
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    return float(
        n * (tn * payoff.r_tn + fp * payoff.r_fp + fn * payoff.r_fn + tp * payoff.r_tp) / n
    )


def gross_value(
    u_base_plus: float,
    u_base: float,
    *,
    competition_loss: float = 0.0,
) -> float:
    """V_{D,R}^{gross,*} = U(θ_{base+D}) - U(θ_base,∅) - L_b^comp（§26）。"""
    return u_base_plus - u_base - competition_loss
