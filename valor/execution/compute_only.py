"""COMPUTE_ONLY 交付（规范 §36.3）。

原始数据留在控制域，授权算法在受控环境运行，买方只获得允许输出。适合高敏感度
数据、估值和部分质量审计（§36.3 / §27 SecureValuation）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass
class ComputeOnlyDelivery:
    """Compute-Only 交付：只返回授权输出。"""

    def run_authorized(self, df: pd.DataFrame, fn: Callable[[pd.DataFrame], object]) -> object:
        """在控制域执行授权函数，返回输出（不返回原始数据）。"""
        return fn(df)
