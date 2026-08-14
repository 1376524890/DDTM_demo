"""QP-05 重复与近重复检测（规范 §13）。

精确重复使用 canonical row hash，不依赖相似度阈值；近重复为可选 primitive。
近重复输出不能覆盖精确重复结果。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valor.core.hashing import content_hash

from ..models import PrimitiveOutput


def _row_hash(row) -> str:
    return content_hash(list(row))


def run_exact_duplicates(
    X: pd.DataFrame,
    *,
    columns: tuple[str, ...] | None = None,
) -> PrimitiveOutput:
    """精确重复检测（§13）：canonical row hash，无相似度阈值。"""
    cols = list(columns) if columns else list(X.columns)
    sub = X[cols]
    hashes = [_row_hash(r) for r in sub.itertuples(index=False)]
    seen: dict[str, int] = {}
    duplicate_indices: list[int] = []
    for i, h in enumerate(hashes):
        if h in seen:
            duplicate_indices.append(i)
        else:
            seen[h] = i
    metrics = {
        "n_rows": int(len(sub)),
        "n_exact_duplicate_rows": int(len(duplicate_indices)),
        "exact_duplicate_rate": len(duplicate_indices) / len(sub) if len(sub) else 0.0,
        "n_unique_rows": int(len(seen)),
    }
    return PrimitiveOutput(
        algorithm_id="exact_duplicates",
        metrics=metrics,
        detail={"duplicate_indices": duplicate_indices, "columns": cols},
    )
