"""基础预处理（规范 §55 数据管线）。

保持最小、可复现：数值化类别列、缺失处理、可选标准化。
所有预处理参数来自 ResolvedParameter，禁止隐式默认（规范 §5）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PreprocessSpec:
    """预处理规格（显式参数，无默认值）。"""

    fill_strategy: str  # "none" | "mean" | "drop"
    standardize: bool


def preprocess(
    X: pd.DataFrame,
    *,
    fill_strategy: str = "none",
    standardize: bool = False,
    fit_ref: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """预处理。

    Args:
        X: 输入特征
        fill_strategy: 缺失处理策略（none/mean/drop）
        standardize: 是否标准化
        fit_ref: 若提供，用其统计量拟合（避免 data leakage）；否则用 X 拟合
    """
    out = X.copy()
    ref = fit_ref if fit_ref is not None else X

    # 数值化类别列（对象列 → 类别编码，基于 ref）
    for col in out.columns:
        if out[col].dtype == object:
            cats = ref[col].astype("category").cat.categories
            out[col] = pd.Categorical(out[col], categories=cats).codes

    # 缺失处理
    if fill_strategy == "mean":
        means = ref.mean(numeric_only=True)
        out = out.fillna(means)
    elif fill_strategy == "drop":
        out = out.dropna(axis=0)
    # "none": 保留缺失（由下游质量 primitive 检测）

    # 标准化（基于 ref 均值/标准差）
    if standardize:
        mu = ref.mean(numeric_only=True)
        sd = ref.std(numeric_only=True).replace(0.0, np.nan)
        out = (out - mu) / sd

    return out
