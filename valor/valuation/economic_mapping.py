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


# ---------------------------------------------------------------------------
# 多分类经济映射（P1：MNIST 适配 + N_b 语义修复）
#
# 用户明确指出的漏洞：验证集大小不得充当 N_b（部署规模）。
# U_b(θ) = N_b Σ_{y,ŷ} P̂(y,ŷ;θ) r_{y,ŷ}，其中 P̂(y,ŷ) = N_{y,ŷ}/N_eval
# 在 eval 集上估计联合概率，但效用按部署规模 N_b 计（N_b 独立于 eval 大小）。
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuyerContext:
    """买方任务上下文（交接文档第五节）。

    deployment_scale N_b：生产部署规模，独立于验证集大小——绝不把 eval 大小当 N_b。
    payoff_matrix r[y,y_hat]：通用多分类收益矩阵（单位 [CU]）。
    """

    task_id: str
    deployment_scale: int  # N_b
    payoff_matrix: np.ndarray  # shape (n_classes, n_classes)，r[y_true, y_pred]
    application_context: str = ""
    baseline_budget: float | None = None
    rights_requirement: str = ""

    def to_plain(self) -> dict:
        return {
            "task_id": self.task_id,
            "deployment_scale": self.deployment_scale,
            "application_context": self.application_context,
            "baseline_budget": self.baseline_budget,
            "rights_requirement": self.rights_requirement,
        }


def utility_from_artifact(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    payoff_matrix: np.ndarray,
    *,
    deployment_scale: int,
) -> float:
    """U_b(θ) = N_b Σ P̂(y,ŷ;θ) r_{y,ŷ}（多分类，N_b 独立于 eval 大小）。

    P̂(y,ŷ) = N_{y,ŷ}/N_eval 在 eval 集上估计联合经验概率。
    """
    payoff = np.asarray(payoff_matrix, dtype=float)
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    n = len(y_true)
    if n == 0:
        return 0.0
    n_cls = payoff.shape[0]
    # 联合经验频率 P̂(y,ŷ)
    joint = np.zeros((n_cls, n_cls))
    for y, yh in zip(y_true, y_pred):
        if y < n_cls and yh < n_cls:
            joint[y, yh] += 1.0
    joint /= n
    return float(deployment_scale) * float(np.sum(joint * payoff))


def utility_delta_from_artifact(
    base_artifact,
    plus_artifact,
    payoff_matrix: np.ndarray,
    *,
    deployment_scale: int,
) -> tuple[float, float, float]:
    """返回 (U_base, U_plus, ΔU)；ΔU = U(θ_{base+D}) - U(θ_base)。"""
    u_base = utility_from_artifact(
        base_artifact.y_true, base_artifact.y_pred, payoff_matrix,
        deployment_scale=deployment_scale,
    )
    u_plus = utility_from_artifact(
        plus_artifact.y_true, plus_artifact.y_pred, payoff_matrix,
        deployment_scale=deployment_scale,
    )
    return u_base, u_plus, u_plus - u_base
