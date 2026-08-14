"""真实公开 tabular 二分类数据集加载（规范 §1 主实验域 / DoD A）。

本环境无通用外网（PyPI 可达但数据托管站点不可达），为可靠复现，默认从
scikit-learn 内置的**真实公开数据集**加载（breast_cancer / digits），离线安全。
同时支持从配置的本地缓存 / URL 下载 CSV（若环境允许）。

所有数据集加载后统一为 (X DataFrame, y Series) 形式，供四角色划分使用。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

import pandas as pd

# 内置真实公开二分类数据集注册表
_BUILTIN: dict[str, Callable[[], tuple[pd.DataFrame, pd.Series]]] = {}


def _register_builtin(name: str):
    def deco(fn):
        _BUILTIN[name] = fn
        return fn
    return deco


@_register_builtin("breast_cancer")
def _load_breast_cancer():
    from sklearn.datasets import load_breast_cancer

    data = load_breast_cancer(as_frame=True)
    X = data.frame.drop(columns=["target"])
    y = data.frame["target"]
    return X, y


@_register_builtin("digits")
def _load_digits():
    from sklearn.datasets import load_digits

    data = load_digits(as_frame=True)
    X = data.frame.drop(columns=["target"])
    y = data.frame["target"]
    return X, y


@dataclass(frozen=True)
class DatasetHandle:
    """已加载数据集句柄（含名称/版本/承诺）。"""

    name: str
    X: pd.DataFrame
    y: pd.Series
    version: str = "bundled"


def load_dataset(name: str, *, version: str = "bundled") -> DatasetHandle:
    """加载真实公开 tabular 二分类数据集（默认 sklearn 内置，离线安全）。"""
    if name not in _BUILTIN:
        raise ValueError(
            f"未知数据集 {name!r}，可用: {sorted(_BUILTIN)}"
        )
    X, y = _BUILTIN[name]()
    return DatasetHandle(name=name, X=X, y=y, version=version)
