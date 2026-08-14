"""估值器协议（规范 §27 SecureValuation 接口）。

SecureValuation(H(D), BuyerModelSpec, ValuationSpec) → ΔÛ_D。
P0 public-data 原型可直接读取本地 committed dataset 完成算法验证；敏感数据
deployment 将 DataAccessHandle 解析到 Compute-Only/TEE/MPC provider。
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class DataAccessHandle(Protocol):
    """数据访问句柄（§27）。P0 直接持有 committed DataFrame。"""

    def load(self) -> pd.DataFrame: ...


class LocalDataHandle:
    """本地 committed dataset 句柄（P0 public-data）。"""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def load(self) -> pd.DataFrame:
        return self._df


class ValuationEstimator(Protocol):
    """估值器接口：返回批次边际货币价值估计。"""

    def estimate(self, *args, **kwargs) -> float: ...
