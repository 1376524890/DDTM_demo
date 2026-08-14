"""Deequ 类声明式结构验证 reference（规范 §9 / §72）。

本环境无 JVM/Spark，故以 Deequ 语义的独立声明式实现作为 reference
（与 native 的显式循环是两条不同代码路径）。完整 Deequ 可通过 Spark 生成
JSON artifact 接入（§72），接口保持一致。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..models import PrimitiveOutput


class DeequReferenceAdapter:
    """声明式约束校验 reference（Deequ semantics）。"""

    def run_structural(
        self,
        X: pd.DataFrame,
        *,
        columns: tuple[str, ...] | None = None,
    ) -> PrimitiveOutput:
        cols = list(columns) if columns else list(X.columns)
        n = len(X)
        metrics: dict = {"n_rows": int(n)}
        for c in cols:
            col = X[c]
            metrics[c] = {
                # 用 pandas 方法（独立于 native 的显式循环）
                "completeness": float(col.notna().mean()),
                "validity": float(col.notna().mean()),
                "uniqueness": float(col.nunique() / n) if n else 0.0,
                "missing_count": int(col.isna().sum()),
                "unique_count": int(col.nunique()),
            }
        # 整行重复率：pandas 原生 duplicated（独立于 native 的 canonical row hash）
        dup_rate = float(X.duplicated(keep="first").mean()) if n else 0.0
        metrics["duplicate_rate"] = dup_rate
        metrics["n_unique_rows"] = int(n - X.duplicated(keep="first").sum())
        return PrimitiveOutput(
            algorithm_id="structural_reference", metrics=metrics,
            detail={"columns": cols},
        )

    def run_exact_duplicates(
        self,
        X: pd.DataFrame,
        *,
        columns: tuple[str, ...] | None = None,
    ) -> PrimitiveOutput:
        """精确重复 reference（pandas duplicated，独立于 native canonical hash）。"""
        cols = list(columns) if columns else list(X.columns)
        sub = X[cols]
        # 与 native 相同语义：第二个及以后出现的重复行计入
        dup_mask = sub.duplicated(keep="first").to_numpy()
        duplicate_indices = list(np.where(dup_mask)[0])
        n = len(sub)
        metrics = {
            "n_rows": int(n),
            "n_exact_duplicate_rows": int(dup_mask.sum()),
            "exact_duplicate_rate": float(dup_mask.mean()) if n else 0.0,
            "n_unique_rows": int(n - dup_mask.sum()),
        }
        return PrimitiveOutput(
            algorithm_id="exact_duplicates_reference",
            metrics=metrics,
            detail={"duplicate_indices": duplicate_indices, "columns": cols},
        )
