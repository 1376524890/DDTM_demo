"""QP-03 单变量分布变化（规范 §11）。

连续特征采用两样本 Kolmogorov–Smirnov statistic：
    D_j^KS = sup_x |F_{D,j}(x) - F_{ref,j}(x)|
显著性水平 alpha_shift 必须为 ResolvedParameter，不允许使用库隐式阈值。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ..models import PrimitiveOutput


def _ecdf_sup(a: np.ndarray, b: np.ndarray) -> float:
    """原生计算两样本 KS 统计量 D（ECDF 上确界）。"""
    a = np.sort(np.asarray(a, dtype=float))
    b = np.sort(np.asarray(b, dtype=float))
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 1.0
    all_ = np.sort(np.concatenate([a, b]))
    fa = np.searchsorted(a, all_, side="right") / n
    fb = np.searchsorted(b, all_, side="right") / m
    return float(np.max(np.abs(fa - fb)))


def run_ks_shift(
    candidate: pd.Series,
    reference: pd.Series,
    *,
    column: str,
    alpha_shift: float,
) -> PrimitiveOutput:
    """对单列连续特征计算 KS 分布变化。"""
    a = candidate.dropna().to_numpy()
    b = reference.dropna().to_numpy()
    d = _ecdf_sup(a, b)
    # p-value 用两样本 KS（与 scipy reference 一致，避免 p 值分叉）
    ks_stat, p_value = stats.ks_2samp(a, b)
    # effect size（Cliff's delta）
    delta = _cliffs_delta(a, b)
    metrics = {
        "ks_statistic": float(ks_stat),
        "native_ks_statistic": d,
        "p_value": float(p_value),
        "effect_size_cliffs_delta": float(delta),
        "n_candidate": int(len(a)),
        "n_reference": int(len(b)),
        "reject_H0": bool(p_value < alpha_shift),
        "alpha_shift": float(alpha_shift),
    }
    return PrimitiveOutput(
        algorithm_id="ks_shift", metrics=metrics,
        detail={"column": column},
    )


def _cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Cliff's delta（无分布效应量）。"""
    if len(a) == 0 or len(b) == 0:
        return 0.0
    gt = 0
    lt = 0
    for x in a:
        gt += np.sum(b < x)
        lt += np.sum(b > x)
    return float((gt - lt) / (len(a) * len(b)))
