"""受控 ground truth 标签（规范 §8 / §15.4 注入 ground-truth）。

真实生产里 NO_TRADE 数据通常无 realised value；实验 Oracle 可计算，但不能让
production feedback 假装观察到（§45）。本模块提供实验用 ground truth 载体。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class GroundTruth:
    """实验 ground truth：真实标签 + 每行质量状态标记。

    true_label: 真实标签（注入后仍为真）
    is_error:   该行是否被注入质量错误（供 TP/FP/FN/TN 计算）
    error_type: 错误类型（缺失/重复/标签翻转等），无错误为 None
    """

    true_label: pd.Series
    is_error: np.ndarray
    error_type: np.ndarray  # 每行错误类型（object），None 表示无错误

    def label_error_indices(self) -> np.ndarray:
        """返回标签翻转行索引（label_flip 类型）。"""
        return np.where(self.error_type == "label_flip")[0]

    def any_error_indices(self) -> np.ndarray:
        return np.where(self.is_error)[0]
