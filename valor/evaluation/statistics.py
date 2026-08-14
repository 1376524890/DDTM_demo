"""统计规范工具（规范 §66）。

连续指标：mean/median + 95% CI；比例指标：Wilson interval；多 baseline 用 Holm
correction；paired 近似正态用 paired t-test 否则 Wilcoxon signed-rank。
"""

from __future__ import annotations

import numpy as np
from scipy import stats


def mean_ci(x, alpha: float = 0.05) -> tuple[float, float, float]:
    """均值与 (1-alpha) 置信区间（正态近似）。"""
    x = np.asarray(x, dtype=float)
    m = float(np.mean(x))
    se = float(np.std(x, ddof=1)) / np.sqrt(len(x)) if len(x) > 1 else 0.0
    z = stats.norm.ppf(1 - alpha / 2)
    return m, m - z * se, m + z * se


def wilson_interval(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson 比例置信区间。"""
    if n == 0:
        return 0.0, 0.0
    phat = k / n
    z = stats.norm.ppf(1 - alpha / 2)
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = z * np.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return float(centre - half), float(centre + half)


def holm_correction(pvalues) -> list[float]:
    """Holm 多重比较校正（§11/§66）。"""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adj = np.zeros_like(p)
    for i, idx in enumerate(order):
        adj[idx] = min(1.0, (m - i) * p[idx])
    # enforce monotonicity
    for i in range(len(order) - 1):
        adj[order[i]] = min(adj[order[i]], adj[order[i + 1]])
    return adj.tolist()


def paired_test(a, b) -> dict:
    """paired 检验：近似正态用 t-test，否则 Wilcoxon。"""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if len(d) < 2:
        return {"method": "none", "p": 1.0}
    if stats.shapiro(d).pvalue > 0.05:
        t, p = stats.ttest_rel(a, b)
        method = "paired_t"
    else:
        stat, p = stats.wilcoxon(d)
        method = "wilcoxon"
    return {"method": method, "p": float(p)}
