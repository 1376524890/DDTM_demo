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


def bootstrap_ci(x, *, n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float, float]:
    """95% bootstrap CI（非正态稳健）。返回 (mean, ci_low, ci_high)。"""
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for i in range(n_boot):
        sample = rng.choice(x, size=len(x), replace=True)
        means[i] = np.mean(sample)
    lo = np.percentile(means, 100 * alpha / 2)
    hi = np.percentile(means, 100 * (1 - alpha / 2))
    return float(np.mean(x)), float(lo), float(hi)


def cohens_dz(a, b) -> float:
    """Cohen's dz（paired）：mean(diff) / std(diff)。"""
    d = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    sd = np.std(d, ddof=1)
    if sd == 0 or len(d) < 2:
        return 0.0
    return float(np.mean(d) / sd)


def rank_biserial(a, b) -> float:
    """非参数 effect size：rank-biserial correlation（Wilcoxon 的效应量）。"""
    from scipy.stats import mannwhitneyu

    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) == 0 or len(b) == 0:
        return 0.0
    n1, n2 = len(a), len(b)
    # 全同 → 无效应量（避免 scipy tie 除零）
    if np.all(a == a[0]) and np.all(b == b[0]) and a[0] == b[0]:
        return 0.0
    try:
        with np.errstate(divide="ignore", invalid="ignore"):
            u, _ = mannwhitneyu(a, b)
    except ValueError:
        return 0.0
    if n1 * n2 == 0 or np.isnan(u):
        return 0.0
    return float(1.0 - 2.0 * u / (n1 * n2))


def descriptive_stats(x) -> dict:
    """描述统计：n/mean/median/std/IQR。"""
    x = np.asarray(x, dtype=float)
    if len(x) == 0:
        return {"n": 0}
    q25, q75 = np.percentile(x, [25, 75])
    return {
        "n": int(len(x)),
        "mean": float(np.mean(x)),
        "median": float(np.median(x)),
        "std": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0,
        "iqr": float(q75 - q25),
    }
