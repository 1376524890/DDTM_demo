"""QP-02 Confident Learning 原生复现（规范 §10）。

输入严格 out-of-sample 预测概率 p̂_i(k)。原生实现 confident threshold、
confident joint C_ab、label issue ranking 与 estimated label error rate。

阈值定义 T 必须与所复现 CL 版本绑定；此处实现论文定义的 mean-threshold 版本。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..models import PrimitiveOutput


def _confident_thresholds(probs: np.ndarray, labels: np.ndarray, classes: list[int],
                          method: str = "mean") -> dict[int, float]:
    """每类别 confident threshold（论文定义，method 显式）。"""
    t: dict[int, float] = {}
    for k in classes:
        p_k = probs[labels == k, k]
        if len(p_k) == 0:
            t[k] = 0.0
        elif method == "mean":
            t[k] = float(p_k.mean())
        elif method == "self_confident":
            t[k] = float(np.percentile(p_k, 100))
        else:
            raise ValueError(f"未知 threshold method: {method}")
    return t


def _confident_assignment(probs: np.ndarray, labels: np.ndarray,
                          classes: list[int], thresholds: dict[int, float]):
    """返回 (confident_joint C, issue_indices, conf_labels)。"""
    k = len(classes)
    C = np.zeros((k, k), dtype=int)
    issues: list[int] = []
    conf_labels: list[int | None] = []
    for i, (p, y) in enumerate(zip(probs, labels)):
        above = [(cls, float(p[cls])) for cls in classes if p[cls] >= thresholds[cls]]
        if above:
            conf = max(above, key=lambda x: x[1])[0]
            conf_labels.append(conf)
            C[y, conf] += 1
            if conf != y:
                issues.append(i)
        else:
            conf_labels.append(None)
    return C, issues, conf_labels


def run_confident_learning(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    probabilities: np.ndarray,  # OOF 预测概率矩阵 (n, n_classes)
    classes: tuple[int, ...] | None = None,
    threshold_method: str = "mean",
    model_spec_hash: str = "",
) -> PrimitiveOutput:
    """原生 Confident Learning 关键统计。

    probabilities 必须是严格 out-of-sample 预测概率（§10）。
    """
    if classes is None:
        classes = tuple(sorted(int(v) for v in y.unique()))
    labels = y.to_numpy().astype(int)
    probs = np.asarray(probabilities, dtype=float)
    thresholds = _confident_thresholds(probs, labels, list(classes), threshold_method)
    C, issues, conf_labels = _confident_assignment(probs, labels, list(classes), thresholds)

    total = int(C.sum())
    estimated_error_rate = (
        float((C.sum() - np.trace(C))) / total if total else 0.0
    )
    # label quality score：该样本对其观测标签的自信度 p̂_i(ỹ_i)
    quality_scores = [
        float(probs[i, labels[i]]) for i in range(len(labels))
    ]
    metrics = {
        "n_samples": int(len(labels)),
        "n_classes": len(classes),
        "estimated_label_error_rate": estimated_error_rate,
        "n_issues": int(len(issues)),
        "issue_rate": len(issues) / len(labels) if len(labels) else 0.0,
        "confident_joint_diag_ratio": (
            float(np.trace(C)) / total if total else 1.0
        ),
    }
    return PrimitiveOutput(
        algorithm_id="confident_learning",
        metrics=metrics,
        detail={
            "confident_joint": C.tolist(),
            "issue_indices": issues,
            "thresholds": thresholds,
            "model_spec_hash": model_spec_hash,
            "label_quality_scores": quality_scores,
            "threshold_method": threshold_method,
        },
    )
