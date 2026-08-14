"""QP-01 声明式结构与完整性验证（规范 §9）。

原生复现 Deequ 类约束语义：
    Completeness_j = 1 - (1/n) Σ 1[x_ij ∈ Missing]
    Validity_j     = (1/n) Σ 1[x_ij ∈ Ω_j]
    Uniqueness_j   = |{x_ij}| / n
    DuplicateRate  = 1 - |{h_i}| / n,  h_i = H(Canonicalize(row_i))

所有阈值必须来自卖方声明/买方要求/calibration，不在代码里固化（§9）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valor.core.hashing import content_hash

from ..models import PrimitiveOutput


def _valid_domain(x: pd.Series) -> np.ndarray:
    """有效性域 Ω_j：非缺失即视为有效（域约束由调用方给定 domain 覆盖）。"""
    return x.notna().to_numpy()


def run_structural(
    X: pd.DataFrame,
    *,
    columns: tuple[str, ...] | None = None,
) -> PrimitiveOutput:
    """计算结构完整性指标（每列 completeness/validity/uniqueness + 整行重复率）。

    Args:
        X: 数据（DataFrame）
        columns: 目标列；None 表示全部列
    """
    cols = list(columns) if columns else list(X.columns)
    n = len(X)
    metrics: dict = {"n_rows": int(n)}
    for c in cols:
        col = X[c]
        not_missing = col.notna().to_numpy()
        completeness = float(not_missing.sum()) / n
        validity = float(_valid_domain(col).sum()) / n
        n_unique = int(col.dropna().nunique())
        uniqueness = n_unique / n
        metrics[c] = {
            "completeness": completeness,
            "validity": validity,
            "uniqueness": uniqueness,
            "missing_count": int((~not_missing).sum()),
            "unique_count": n_unique,
        }
    # 整行重复率：canonical row hash（§9）
    if n > 0:
        row_hashes = {content_hash(list(row)) for row in X.itertuples(index=False)}
        duplicate_rate = 1.0 - len(row_hashes) / n
    else:
        duplicate_rate = 0.0
    metrics["duplicate_rate"] = duplicate_rate
    metrics["n_unique_rows"] = len(row_hashes) if n else 0
    return PrimitiveOutput(
        algorithm_id="structural", metrics=metrics,
        detail={"columns": cols},
    )
