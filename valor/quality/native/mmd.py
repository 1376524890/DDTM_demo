"""QP-04 多变量 MMD（规范 §12）。

无偏 MMD 统计量：
    MMD_u^2 = 1/(n(n-1)) Σ_{i≠i'} k(x_i,x_i')
            + 1/(m(m-1)) Σ_{j≠j'} k(y_j,y_j')
            - 2/(nm) Σ_{i,j} k(x_i,y_j)
kernel 参数来自 KernelSpec；RBF median heuristic 带宽由 calibration data 计算
并记录为 OBSERVED/CALIBRATED，不写成固定常数。
置换次数由目标 p-value resolution ε_p 决定：B_perm >= ceil(1/ε_p) - 1。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..models import PrimitiveOutput


def _rbf_kernel(X: np.ndarray, Y: np.ndarray, bandwidth: float) -> np.ndarray:
    """RBF kernel 矩阵 k(x, y) = exp(-||x-y||^2 / (2 σ^2))。"""
    sq = (
        np.sum(X ** 2, axis=1)[:, None]
        + np.sum(Y ** 2, axis=1)[None, :]
        - 2 * (X @ Y.T)
    )
    sq = np.clip(sq, 0, None)
    return np.exp(-sq / (2.0 * bandwidth ** 2))


def median_heuristic(X: np.ndarray, Y: np.ndarray) -> float:
    """RBF median heuristic 带宽（由当前 calibration data 计算）。"""
    Z = np.vstack([X, Y])
    d = np.linalg.norm(Z[:, None, :] - Z[None, :, :], axis=2)
    # 取中位距离；0 时退化为 1
    med = float(np.median(d[d > 0])) if np.any(d > 0) else 1.0
    return med if med > 0 else 1.0


def unbiased_mmd2(X: np.ndarray, Y: np.ndarray, bandwidth: float) -> float:
    """无偏 MMD^2（§12）。"""
    n, m = len(X), len(Y)
    Kxx = _rbf_kernel(X, X, bandwidth)
    Kyy = _rbf_kernel(Y, Y, bandwidth)
    Kxy = _rbf_kernel(X, Y, bandwidth)
    np.fill_diagonal(Kxx, 0.0)
    np.fill_diagonal(Kyy, 0.0)
    term1 = np.sum(Kxx) / (n * (n - 1)) if n > 1 else 0.0
    term2 = np.sum(Kyy) / (m * (m - 1)) if m > 1 else 0.0
    term3 = -2.0 * np.sum(Kxy) / (n * m) if n and m else 0.0
    return float(term1 + term2 + term3)


def run_mmd(
    candidate: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    bandwidth: float | None = None,
    target_pvalue_resolution: float,
    n_permutations: int | None = None,
) -> PrimitiveOutput:
    """多变量 MMD 分布变化（§12）。"""
    X = candidate.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    Y = reference.select_dtypes(include=[np.number]).to_numpy(dtype=float)
    if bandwidth is None:
        bandwidth = median_heuristic(X, Y)
    mmd = unbiased_mmd2(X, Y, bandwidth)
    # 置换次数由 ε_p 决定（§12）：B_perm >= ceil(1/ε_p) - 1
    if n_permutations is None:
        n_permutations = max(1, int(np.ceil(1.0 / target_pvalue_resolution)) - 1)
    # permutation p-value
    Z = np.vstack([X, Y])
    n = len(X)
    rng = np.random.default_rng(0)
    count = 0
    for _ in range(n_permutations):
        perm = rng.permutation(len(Z))
        Xp, Yp = Z[perm[:n]], Z[perm[n:]]
        if unbiased_mmd2(Xp, Yp, bandwidth) >= mmd:
            count += 1
    p_value = (count + 1) / (n_permutations + 1)
    metrics = {
        "mmd_u2": mmd,
        "p_value": p_value,
        "bandwidth": float(bandwidth),
        "bandwidth_source": "median_heuristic_calibrated",
        "n_permutations": int(n_permutations),
        "target_pvalue_resolution": float(target_pvalue_resolution),
        "n_candidate": int(len(X)),
        "n_reference": int(len(Y)),
    }
    return PrimitiveOutput(
        algorithm_id="mmd", metrics=metrics,
        detail={"kernel": "rbf", "bandwidth_heuristic": "median"},
    )
