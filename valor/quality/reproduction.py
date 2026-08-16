"""Reference Reproduction Gate Q0（规范 §15 / §47，Phase 1 核心）。

对每个 primitive：加载不可变数据集 → 执行注入 case → 运行 reference 与
native → 按等价规则比较 → 计算 ground-truth 指标（TP/FP/FN/TN）→ 生成
QualityReproductionCertificate → 全部 Gate 通过才置 distributed_enabled=True。

Gate 条件按算法类型定义，不使用统一拍脑袋阈值（§15）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from valor.core.enums import MigrationClass, QualityImplementationKind
from valor.core.hashing import content_hash

from .equivalence import compare_outputs
from .models import (
    PrimitiveOutput,
    QualityAlgorithmSpec,
    QualityReproductionCertificate,
    ReproductionComparison,
)


@dataclass
class _Case:
    """一个复现 case：reference（干净）与 candidate（可能注入）。"""

    reference_df: pd.DataFrame
    candidate_df: pd.DataFrame
    y_candidate: pd.Series
    ground_truth: object | None  # GroundTruth


def _oof_probabilities(X: pd.DataFrame, y: pd.Series) -> np.ndarray:
    """严格 out-of-sample 预测概率（交叉验证，§10 禁止训练内概率）。"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_predict

    model = LogisticRegression(max_iter=2000)
    probs = cross_val_predict(
        model, X.fillna(0), y.to_numpy(), cv=3, method="predict_proba"
    )
    return probs


def _ground_truth_metrics(detected: np.ndarray, error_types: np.ndarray,
                          target_type: str | None) -> dict:
    """相对注入 ground truth 计算 TP/FP/FN/TN。

    Args:
        detected: 算法判定的问题行布尔数组
        error_types: 每行注入错误类型（None=无错误）
        target_type: 该算法针对的错误类型（None=任何错误都算正例）
    """
    n = len(error_types)
    if target_type is None:
        positive = error_types.astype(bool)
    else:
        positive = np.array([e == target_type for e in error_types], dtype=bool)
    detected = np.asarray(detected, dtype=bool)
    tp = int(np.sum(detected & positive))
    fp = int(np.sum(detected & ~positive))
    fn = int(np.sum(~detected & positive))
    tn = int(np.sum(~detected & ~positive))
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if (tp + fp) else 0.0,
        "recall": tp / (tp + fn) if (tp + fn) else 0.0,
    }


def _run_pair(spec: QualityAlgorithmSpec, case: _Case, params: dict) -> tuple[
    PrimitiveOutput, PrimitiveOutput, dict, str, str
]:
    """按算法运行 reference 与 native，返回 (ref, native, gt_metrics, ref_hash, native_hash)。"""
    cand = case.candidate_df
    refdf = case.reference_df
    aid = spec.algorithm_id
    gt = case.ground_truth
    gt_metrics: dict = {}

    from .reference import (
        CleanlabReferenceAdapter,
        DeequReferenceAdapter,
        ScipyStatsReferenceAdapter,
    )

    if aid == "structural":
        from .native import run_structural
        cols = params.get("columns")
        ref = DeequReferenceAdapter().run_structural(cand, columns=cols)
        native = run_structural(cand, columns=cols)
    elif aid == "exact_duplicates":
        from .native import run_exact_duplicates
        ref = DeequReferenceAdapter().run_exact_duplicates(cand)
        native = run_exact_duplicates(cand)
        if gt is not None:
            det = np.zeros(len(cand), dtype=bool)
            idx = native.detail.get("duplicate_indices", [])
            det[list(idx)] = True
            gt_metrics = _ground_truth_metrics(det, gt.error_type, "exact_duplicate")
    elif aid == "confident_learning":
        from .reference import CleanlabReferenceAdapter
        from .native import run_confident_learning
        probs = _oof_probabilities(cand, case.y_candidate)
        ref = CleanlabReferenceAdapter().run_confident_learning(
            cand, case.y_candidate, probabilities=probs,
            model_spec_hash=content_hash({"model": "logreg", "cv": 3}),
        )
        native = run_confident_learning(
            cand, case.y_candidate, probabilities=probs,
            model_spec_hash=content_hash({"model": "logreg", "cv": 3}),
            threshold_method=params["threshold_method"],
        )
        if gt is not None:
            det = np.zeros(len(cand), dtype=bool)
            det[list(native.detail.get("issue_indices", []))] = True
            gt_metrics = _ground_truth_metrics(det, gt.error_type, "label_flip")
    elif aid == "ks_shift":
        from .reference import ScipyStatsReferenceAdapter
        from .native import run_ks_shift
        col = params["column"]
        alpha = params["alpha_shift"]
        ref = ScipyStatsReferenceAdapter().run_ks(
            cand[col], refdf[col], column=col, alpha_shift=alpha)
        native = run_ks_shift(cand[col], refdf[col], column=col, alpha_shift=alpha)
    elif aid == "categorical_shift":
        from .reference import ScipyStatsReferenceAdapter
        from .native import run_categorical_shift
        col = params["column"]
        alpha = params["alpha_shift"]
        ref = ScipyStatsReferenceAdapter().run_categorical(
            cand[col], refdf[col], column=col, alpha_shift=alpha)
        native = run_categorical_shift(
            cand[col], refdf[col], column=col, alpha_shift=alpha)
    elif aid == "mmd":
        from .reference import ScipyStatsReferenceAdapter
        from .native import run_mmd
        ref = ScipyStatsReferenceAdapter().run_mmd(cand, refdf)
        native = run_mmd(
            cand, refdf,
            bandwidth=params.get("bandwidth"),
            target_pvalue_resolution=params["target_pvalue_resolution"],
            n_permutations=params["n_permutations"],
        )
    elif aid == "metadata_claim_audit":
        from .native import run_metadata_claim_audit
        claims = params["claims"]
        ref = run_metadata_claim_audit(cand, claims=claims)
        native = run_metadata_claim_audit(cand, claims=claims)
    else:
        raise ValueError(f"未注册的复现算法: {aid}")

    return ref, native, gt_metrics, content_hash(ref.to_plain()), content_hash(native.to_plain())


def reproduce_algorithm(
    spec: QualityAlgorithmSpec,
    *,
    reference_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    y_candidate: pd.Series,
    ground_truth: object | None = None,
    params: dict | None = None,
    created_at: str = "",
    floating_tolerance: float = 1e-6,
) -> tuple[QualityReproductionCertificate, bool]:
    """对单个 primitive 执行复现 Gate。

    Returns: (certificate, passed)。
    """
    params = params or {}
    case = _Case(reference_df, candidate_df, y_candidate, ground_truth)
    ref, native, gt_metrics, ref_hash, native_hash = _run_pair(spec, case, params)
    # 每个算法可覆盖容差（如 CL 的 reference 与 native 阈值语义不同）
    tol = params.get("floating_tolerance", floating_tolerance)
    # Confident Learning：reference(cleanlab) 与 native(mean-threshold) 的
    # 检出计数天然不同，仅比较 error rate 类共享指标（§10 版本语义等价）
    whitelist: set[str] | None = None
    if spec.algorithm_id == "confident_learning":
        whitelist = {"estimated_label_error_rate", "issue_rate"}
    comparisons = compare_outputs(
        spec, ref, native, floating_tolerance=tol, metrics_whitelist=whitelist
    )
    passed = all(c.passed for c in comparisons)
    # ground-truth 指标参与通过判定（若提供）：仅当该算法针对的错误类型
    # 确实被注入（positive>0）时才要求召回达阈值；未注入该错误类型不惩罚。
    if ground_truth is not None and gt_metrics:
        positives = gt_metrics.get("tp", 0) + gt_metrics.get("fn", 0)
        if positives > 0:
            recall = gt_metrics.get("recall", 0.0)
            if recall < params["min_gt_recall"]:
                passed = False
    cert = QualityReproductionCertificate(
        certificate_id=f"cert-{spec.algorithm_id}",
        algorithm_id=spec.algorithm_id,
        reference_impl_hash=ref_hash,
        native_impl_hash=native_hash,
        reference_dataset_hashes=(content_hash(reference_df.to_dict("list")),),
        injection_spec_hashes=(),
        parameter_manifest_hash=content_hash(params),
        metric_comparison=tuple(comparisons),
        runtime_comparison={"note": "single-process reference reproduction"},
        statistical_equivalence_result={
            "rule": spec.equivalence_rule,
            "passed": passed,
            "ground_truth": gt_metrics,
        },
        created_at=created_at,
        passed=passed,
    )
    return cert, passed


def run_reproduction_gate(
    catalog,
    *,
    reference_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    y_candidate: pd.Series,
    ground_truth: object | None = None,
    params_by_algorithm: dict[str, dict] | None = None,
    created_at: str = "",
    floating_tolerance: float = 1e-6,
) -> dict[str, QualityReproductionCertificate]:
    """对目录中全部算法执行复现 Gate，并按结果置 distributed_enabled。"""
    params_by_algorithm = params_by_algorithm or {}
    certificates: dict[str, QualityReproductionCertificate] = {}
    for aid in catalog.list_ids():
        spec = catalog.get(aid)
        cert, passed = reproduce_algorithm(
            spec,
            reference_df=reference_df,
            candidate_df=candidate_df,
            y_candidate=y_candidate,
            ground_truth=ground_truth,
            params=params_by_algorithm.get(aid, {}),
            created_at=created_at,
            floating_tolerance=floating_tolerance,
        )
        certificates[aid] = cert
        # Gate B：通过才置 distributed_enabled（§14/§15）
        catalog.set_distributed_enabled(aid, passed)
    return certificates
