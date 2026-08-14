"""QP-03 类别特征分布变化（规范 §11）。

类别特征使用合同指定的类别分布检验，保存 contingency statistics。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from ..models import PrimitiveOutput


def run_categorical_shift(
    candidate: pd.Series,
    reference: pd.Series,
    *,
    column: str,
    alpha_shift: float,
) -> PrimitiveOutput:
    """对单列类别特征做卡方分布变化检验。"""
    cat = pd.concat([candidate, reference], axis=0)
    # 统一类别域（并集）
    cats = sorted(cat.dropna().unique())
    obs_c = candidate.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
    obs_r = reference.value_counts().reindex(cats, fill_value=0).to_numpy(dtype=float)
    # 卡方：2×k 列联表（candidate vs reference 类别分布）
    table = np.vstack([obs_c, obs_r])
    chi2, p_value, dof, _ = stats.chi2_contingency(table)
    metrics = {
        "chi2_statistic": chi2,
        "dof": dof,
        "p_value": p_value,
        "n_categories": len(cats),
        "reject_H0": bool(p_value < alpha_shift),
        "alpha_shift": float(alpha_shift),
    }
    return PrimitiveOutput(
        algorithm_id="categorical_shift", metrics=metrics,
        detail={"column": column, "categories": cats},
    )
