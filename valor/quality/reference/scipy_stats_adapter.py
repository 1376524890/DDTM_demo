"""scipy/sklearn 统计 reference（规范 §11/§12）。

独立实现 KS / 类别卡方 / MMD 的 reference 版本：
- KS 用 scipy.stats.ks_2samp（native 显式计算 ECDF 上确界）
- 类别卡方用 scipy.stats.chisquare
- MMD 用 sklearn 的 rbf_kernel（native 自带 RBF 实现）
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ..models import PrimitiveOutput


class ScipyStatsReferenceAdapter:
    """scipy/sklearn 统计参考实现。"""

    def run_ks(self, candidate: pd.Series, reference: pd.Series, *,
               column: str, alpha_shift: float) -> PrimitiveOutput:
        a = candidate.dropna().to_numpy()
        b = reference.dropna().to_numpy()
        stat, p = stats.ks_2samp(a, b)
        return PrimitiveOutput(
            algorithm_id="ks_shift_reference",
            metrics={
                "ks_statistic": float(stat),
                "p_value": float(p),
                "n_candidate": int(len(a)),
                "n_reference": int(len(b)),
                "reject_H0": bool(p < alpha_shift),
                "alpha_shift": float(alpha_shift),
            },
            detail={"column": column},
        )

    def run_categorical(self, candidate: pd.Series, reference: pd.Series, *,
                        column: str, alpha_shift: float) -> PrimitiveOutput:
        cats = sorted(pd.concat([candidate, reference]).dropna().unique())
        obs_c = candidate.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
        obs_r = reference.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
        chi2, p, dof, _ = stats.chi2_contingency(np.vstack([obs_c, obs_r]))
        return PrimitiveOutput(
            algorithm_id="categorical_shift_reference",
            metrics={
                "chi2_statistic": float(chi2),
                "p_value": float(p),
                "n_categories": len(cats),
                "reject_H0": bool(p < alpha_shift),
                "alpha_shift": float(alpha_shift),
            },
            detail={"column": column},
        )

    def run_mmd(self, candidate: pd.DataFrame, reference: pd.DataFrame, *,
                bandwidth: float | None = None) -> PrimitiveOutput:
        from sklearn.metrics.pairwise import rbf_kernel

        X = candidate.select_dtypes(include=[np.number]).to_numpy(dtype=float)
        Y = reference.select_dtypes(include=[np.number]).to_numpy(dtype=float)
        n, m = len(X), len(Y)
        if bandwidth is None:
            Z = np.vstack([X, Y])
            d = np.linalg.norm(Z[:, None, :] - Z[None, :, :], axis=2)
            bandwidth = float(np.median(d[d > 0])) if np.any(d > 0) else 1.0
        Kxx = rbf_kernel(X, X, gamma=1.0 / (2 * bandwidth ** 2))
        Kyy = rbf_kernel(Y, Y, gamma=1.0 / (2 * bandwidth ** 2))
        Kxy = rbf_kernel(X, Y, gamma=1.0 / (2 * bandwidth ** 2))
        np.fill_diagonal(Kxx, 0.0)
        np.fill_diagonal(Kyy, 0.0)
        mmd = (Kxx.sum() / (n * (n - 1)) if n > 1 else 0.0) \
            + (Kyy.sum() / (m * (m - 1)) if m > 1 else 0.0) \
            - 2.0 * Kxy.sum() / (n * m)
        return PrimitiveOutput(
            algorithm_id="mmd_reference",
            metrics={
                "mmd_u2": float(mmd),
                "bandwidth": float(bandwidth),
                "n_candidate": int(n),
                "n_reference": int(m),
            },
            detail={"kernel": "rbf_sklearn"},
        )
