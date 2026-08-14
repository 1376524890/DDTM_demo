"""primitive 似然估计（规范 §21.1 λ_p^prim / §58 RQ2 detection curve）。

用独立 calibration data 与受控注入估计单节点 primitive 的检出率（sensitivity）
与误报率（FPR），并生成不同污染强度下的检测曲线。
"""

from __future__ import annotations

import numpy as np

from ..models import PrimitiveOutput


def _confusion(detected: np.ndarray, positive: np.ndarray) -> dict:
    tp = int(np.sum(detected & positive))
    fp = int(np.sum(detected & ~positive))
    fn = int(np.sum(~detected & positive))
    tn = int(np.sum(~detected & ~positive))
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "sensitivity": tp / (tp + fn) if (tp + fn) else 0.0,
        "false_positive_rate": fp / (fp + tn) if (fp + tn) else 0.0,
        "precision": tp / (tp + fp) if (tp + fp) else 0.0,
    }


def estimate_primitive_likelihood(
    output: PrimitiveOutput,
    *,
    ground_truth_error_types: np.ndarray,
    target_type: str,
) -> dict:
    """从一次注入 case 估计 λ_p^prim（sensitivity / FPR）。

    Args:
        output: primitive 输出（detail 需含 issue/detected 索引）
        ground_truth_error_types: 每行注入错误类型（None=无错误）
        target_type: 该 primitive 针对的错误类型
    """
    detected = _extract_detected(output)
    positive = np.array(
        [e == target_type for e in ground_truth_error_types], dtype=bool
    )
    # 若注入改变了行数（如重复注入），对齐到检测向量长度
    if len(detected) != len(positive):
        positive = np.resize(positive, len(detected))
    return _confusion(detected, positive)


def detection_curve(
    primitive_fn,
    *,
    base_X,
    base_y,
    fractions: list[float],
    target_type: str,
    seed: int = 0,
) -> list[dict]:
    """不同污染强度下的检测曲线（§58 RQ2）。

    Args:
        primitive_fn: 接受 (X, y) 返回 PrimitiveOutput 的函数
        base_X/base_y: 干净数据
        fractions: 污染比例扫描
    """
    from valor.data.injection import InjectionKind, InjectionSpec, inject_errors

    curve: list[dict] = []
    for frac in fractions:
        spec = InjectionSpec(
            kind=InjectionKind.LABEL_FLIP, fraction=frac, seed=seed
        )
        Xc, yc, gt = inject_errors(base_X, base_y, spec)
        out = primitive_fn(Xc, yc)
        det = _extract_detected(out)
        positive = np.array([e == target_type for e in gt.error_type], dtype=bool)
        if len(det) != len(positive):
            positive = np.resize(positive, len(det))
        cm = _confusion(det, positive)
        curve.append({"fraction": frac, **cm})
    return curve


def _extract_detected(output: PrimitiveOutput) -> np.ndarray:
    """从 primitive 输出提取检测布尔向量（detail 中 issue/duplicate 索引）。"""
    detail = output.detail
    if "issue_indices" in detail:
        idx = detail["issue_indices"]
        n = output.metrics.get("n_samples", max(idx, default=0) + 1)
        det = np.zeros(int(n), dtype=bool)
        det[list(idx)] = True
        return det
    if "duplicate_indices" in detail:
        idx = detail["duplicate_indices"]
        n = output.metrics.get("n_rows", max(idx, default=0) + 1)
        det = np.zeros(int(n), dtype=bool)
        det[list(idx)] = True
        return det
    raise ValueError("primitive 输出缺少可检测索引（issue_indices/duplicate_indices）")
