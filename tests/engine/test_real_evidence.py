"""真实证据源测试：干净 vs 污染候选数据产生不同 audit outcome。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valor.engine.real_evidence import RealQualityEvidence


def test_clean_vs_covariate_shift():
    """covariate shift 应被 KS 分布漂移检测 → QUALITY_FAIL；干净 → PASS。"""
    rng = np.random.default_rng(1)
    n = 800
    ref = pd.DataFrame({"a": rng.normal(0, 1, n), "b": rng.normal(5, 2, n)})
    clean = pd.DataFrame({"a": rng.normal(0, 1, n), "b": rng.normal(5, 2, n)})
    shifted = pd.DataFrame({"a": rng.normal(3, 1, n), "b": rng.normal(8, 2, n)})
    y = pd.Series(rng.integers(0, 2, n))

    det_clean = RealQualityEvidence(
        reference_df=ref, candidate_df=clean, y_candidate=y,
        row_sample=400, compress_dim=16).detect_primitive("ks_shift")
    det_shift = RealQualityEvidence(
        reference_df=ref, candidate_df=shifted, y_candidate=y,
        row_sample=400, compress_dim=16).detect_primitive("ks_shift")

    assert det_clean.outcome == "PASS"
    assert det_shift.outcome == "QUALITY_FAIL"
    assert det_shift.n_significant_drift > det_clean.n_significant_drift


def test_label_poison_detected_mnist():
    """真实 MNIST label 污染 → CL label_error 显著升高 → QUALITY_FAIL。"""
    from valor.data.download import load_dataset

    h = load_dataset("mnist")
    X, y = h.X, h.y
    rng = np.random.default_rng(0)
    idx = rng.choice(len(X), 1500, replace=False)
    cand_X = X.iloc[idx].reset_index(drop=True)
    cand_y = y.iloc[idx].reset_index(drop=True).astype(int)
    y_poison = cand_y.copy()
    pi = rng.choice(len(y_poison), int(0.3 * len(y_poison)), replace=False)
    for i in pi:
        y_poison.iloc[i] = rng.choice(
            [c for c in range(10) if c != int(y_poison.iloc[i])])

    det_clean = RealQualityEvidence(
        reference_df=X.iloc[:1000], candidate_df=cand_X, y_candidate=cand_y,
        row_sample=800, compress_dim=64, label_error_threshold=0.28).detect()
    det_poison = RealQualityEvidence(
        reference_df=X.iloc[:1000], candidate_df=cand_X, y_candidate=y_poison,
        row_sample=800, compress_dim=64, label_error_threshold=0.28).detect()

    assert det_clean.outcome == "PASS"
    assert det_poison.outcome == "QUALITY_FAIL"
    assert det_poison.label_error_rate > det_clean.label_error_rate
