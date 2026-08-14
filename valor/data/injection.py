"""质量错误受控注入（规范 §15.4 InjectionSpec / Ground-truth injection）。

为每种质量错误建立受控注入，输出损坏数据 + GroundTruth（每行错误类型），
供复现 Gate 的 TP/FP/FN/TN 计算与检测曲线使用。

注入类型（§15.4）：
    missingness_injection / schema_violation / exact_duplicate /
    near_duplicate / label_flip / covariate_shift / label_shift /
    metadata_false_claim / committed_dataset_replacement

注入参数同样必须有 InjectionSpec，实验扫描值来自实验设计，不隐藏在代码中。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from .ground_truth import GroundTruth


class InjectionKind(str, Enum):
    """受控注入类型（§15.4）。"""

    MISSINGNESS = "missingness"
    SCHEMA_VIOLATION = "schema_violation"
    EXACT_DUPLICATE = "exact_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    LABEL_FLIP = "label_flip"
    COVARIATE_SHIFT = "covariate_shift"
    LABEL_SHIFT = "label_shift"
    METADATA_FALSE_CLAIM = "metadata_false_claim"
    COMMITTED_REPLACEMENT = "committed_dataset_replacement"


@dataclass(frozen=True)
class InjectionSpec:
    """注入规格（§15.4：参数显式，来自实验设计）。"""

    kind: InjectionKind
    fraction: float  # 受影响样本比例 [0,1]
    seed: int  # 随机种子（显式，无默认值，保证可复现）
    columns: tuple[str, ...] = ()  # 受影响列（空表示全部/自动）
    params: dict = field(default_factory=dict)

    def to_plain(self) -> dict:
        return {
            "kind": self.kind.value,
            "fraction": self.fraction,
            "columns": list(self.columns),
            "seed": self.seed,
            "params": self.params,
        }


def _choose(rng: np.random.Generator, n: int, frac: float) -> np.ndarray:
    """按比例选受影响行索引。"""
    k = min(n, int(round(frac * n)))
    return np.sort(rng.choice(n, size=k, replace=False))


def _apply(kind: InjectionKind, X: pd.DataFrame, y: pd.Series,
           idx: np.ndarray, cols: tuple[str, ...], params: dict):
    """就地执行一种注入，返回 (X, y, error_type)。"""
    et = np.full(len(X), None, dtype=object)
    if kind == InjectionKind.MISSINGNESS:
        for c in (cols or list(X.columns)):
            X.iloc[idx, X.columns.get_loc(c)] = np.nan
        et[idx] = "missingness"
    elif kind == InjectionKind.SCHEMA_VIOLATION:
        # 在列中写入域外值（远超正常范围），模拟 schema 违规
        for c in (cols or list(X.columns)):
            X.iloc[idx, X.columns.get_loc(c)] = params.get("bad_value", -999.0)
        et[idx] = "schema_violation"
    elif kind == InjectionKind.EXACT_DUPLICATE:
        dup = X.iloc[idx]
        X = pd.concat([X, dup], ignore_index=True)
        y = pd.concat([y, y.iloc[idx]], ignore_index=True)
        et = np.full(len(X), None, dtype=object)
        et[len(X) - len(dup):] = "exact_duplicate"
    elif kind == InjectionKind.NEAR_DUPLICATE:
        noise = params.get("noise", 1e-3)
        dup = X.iloc[idx].copy()
        for c in dup.select_dtypes(include=[np.number]).columns:
            dup[c] = dup[c] + rng.normal(0, noise, size=len(dup))
        X = pd.concat([X, dup], ignore_index=True)
        y = pd.concat([y, y.iloc[idx]], ignore_index=True)
        et = np.full(len(X), None, dtype=object)
        et[len(X) - len(dup):] = "near_duplicate"
    elif kind == InjectionKind.LABEL_FLIP:
        y = y.copy()
        y.iloc[idx] = 1 - y.iloc[idx]
        et[idx] = "label_flip"
    elif kind == InjectionKind.COVARIATE_SHIFT:
        shift = params.get("shift", 2.0)
        for c in (cols or list(X.select_dtypes(include=[np.number]).columns)):
            X.iloc[idx, X.columns.get_loc(c)] = X.iloc[idx, X.columns.get_loc(c)] + shift
        et[idx] = "covariate_shift"
    elif kind == InjectionKind.LABEL_SHIFT:
        y = y.copy()
        # 翻转 idx 中部分样本标签，模拟标签分布偏移（与 label_flip 类似但按分布）
        flip = _choose(rng, len(idx), params.get("flip_frac", 0.5))
        y.iloc[idx[flip]] = 1 - y.iloc[idx[flip]]
        et[idx] = "label_shift"
    elif kind in (InjectionKind.METADATA_FALSE_CLAIM,
                  InjectionKind.COMMITTED_REPLACEMENT):
        # 这两类不改变行内容；由调用方在 metadata/commitment 层面记录
        pass
    return X, y, et


class Injector:
    """注入器：按 InjectionSpec 产生损坏数据 + GroundTruth。"""

    def __init__(self, spec: InjectionSpec) -> None:
        self.spec = spec
        self._rng = np.random.default_rng(spec.seed)

    def apply(self, X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series, GroundTruth]:
        """执行注入，返回 (X_corrupted, y_corrupted, GroundTruth)。"""
        X = X.copy()
        y = y.copy()
        idx = _choose(self._rng, len(X), self.spec.fraction)
        cols = self.spec.columns
        X, y, et = _apply(self.spec.kind, X, y, idx, cols, self.spec.params)
        is_error = np.array([e is not None for e in et], dtype=bool)
        gt = GroundTruth(
            true_label=y.reset_index(drop=True),
            is_error=is_error,
            error_type=np.asarray(et, dtype=object),
        )
        return X, y, gt


def inject_errors(
    X: pd.DataFrame,
    y: pd.Series,
    spec: InjectionSpec,
) -> tuple[pd.DataFrame, pd.Series, GroundTruth]:
    """便捷函数：按 spec 注入。"""
    return Injector(spec).apply(X, y)
