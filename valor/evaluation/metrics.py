"""实验指标（规范 §57/§66）。

RQ1 估值指标：Spearman、Kendall tau、MAE、RMSE、Top-k regret。
"""

from __future__ import annotations

import numpy as np
from scipy.stats import kendalltau, spearmanr


def spearman(a, b) -> float:
    r, _ = spearmanr(a, b)
    return float(r) if not np.isnan(r) else 0.0


def kendall(a, b) -> float:
    t, _ = kendalltau(a, b)
    return float(t) if not np.isnan(t) else 0.0


def mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def rmse(a, b) -> float:
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def topk_regret(values_true, values_est, k: int) -> float:
    """Top-k regret：真实 top-k 集合在估计排序中的遗憾。"""
    order_true = np.argsort(-np.asarray(values_true))
    order_est = np.argsort(-np.asarray(values_est))
    top_true = set(order_true[:k])
    top_est = set(order_est[:k])
    return float(len(top_true - top_est) / k)
