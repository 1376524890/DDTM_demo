"""Reference Reproduction Gate（Gate B）测试（规范 §15/§47）。

验证：未过 Gate 前 distributed_enabled=False；全部 primitive 在真实公开
数据 + 受控注入上 reference 与 native 复现等价后，distributed_enabled=True。
"""

from __future__ import annotations

import pytest

from valor.quality.catalog import default_catalog
from valor.quality.reproduction import run_reproduction_gate
from valor.data.download import load_dataset
from valor.data.preprocess import preprocess
from valor.data.split_roles import split_roles_four_way
from valor.data.transaction_batches import make_candidate_batches
from valor.data.injection import InjectionKind, InjectionSpec, inject_errors


@pytest.fixture(scope="module")
def reproduction_case():
    """构造复现 case：真实公开数据 + 四角色划分 + label_flip 注入。"""
    handle = load_dataset("breast_cancer")
    X = preprocess(handle.X, fill_strategy="none")
    split = split_roles_four_way(
        X, handle.y, seed=0,
        base_train_frac=0.5, seller_pool_frac=0.3, valuation_validation_frac=0.1,
    )
    batches = make_candidate_batches(
        X, handle.y, seller_pool_idx=split.seller_pool_idx,
        n_batches=2, rows_per_batch=40, seed=0,
    )
    cand = batches[0]
    ref = X.iloc[split.valuation_validation_idx].reset_index(drop=True)
    X_cand, y_cand, gt = inject_errors(
        cand.X, cand.y,
        InjectionSpec(kind=InjectionKind.LABEL_FLIP, fraction=0.3, seed=1),
    )
    return ref, X_cand, y_cand, gt


def test_gate_disabled_before_reproduction():
    """Gate B 通过前 distributed_enabled 必须为 False（§14）。"""
    catalog = default_catalog()
    for aid in catalog.list_ids():
        assert catalog.get(aid).distributed_enabled is False, aid


def test_all_primitives_pass_gate(reproduction_case):
    """全部 primitive 通过复现 Gate → distributed_enabled=True。"""
    ref, X_cand, y_cand, gt = reproduction_case
    catalog = default_catalog()
    certs = run_reproduction_gate(
        catalog, reference_df=ref, candidate_df=X_cand,
        y_candidate=y_cand, ground_truth=gt,
        params_by_algorithm={
            "ks_shift": {"column": "mean radius", "alpha_shift": 0.05},
            "categorical_shift": {"column": "mean radius", "alpha_shift": 0.05},
            "mmd": {"target_pvalue_resolution": 0.05, "n_permutations": 20},
            "confident_learning": {"threshold_method": "mean", "floating_tolerance": 0.1, "min_gt_recall": 0.2},
            "metadata_claim_audit": {
                "claims": {"c1": {"predicate": "max_missing_rate",
                                  "column": "mean radius", "declared": 0.0}},
            },
        },
        created_at="2026-01-01T00:00:00Z",
    )
    for aid, cert in certs.items():
        assert cert.passed, f"{aid} 复现 Gate 失败"
        assert catalog.get(aid).distributed_enabled is True, aid
    # 全部 7 个 primitive 已注册且通过
    assert len(certs) == 7


def test_structural_deterministic_match(reproduction_case):
    """确定性 primitive：native 与 reference canonical 输出完全一致（§15.1）。"""
    from valor.quality.native.structural import run_structural
    from valor.quality.reference.deequ_adapter import DeequReferenceAdapter

    ref, X_cand, *_ = reproduction_case
    native = run_structural(X_cand)
    reference = DeequReferenceAdapter().run_structural(X_cand)
    assert native.output_hash() == reference.output_hash()


def test_ground_truth_metrics_label_flip(reproduction_case):
    """注入 label_flip 后，CL 的检出相对 ground truth 计算 TP/FP/FN/TN（§15.4）。"""
    from valor.quality.catalog import default_catalog
    from valor.quality.reproduction import run_reproduction_gate

    ref, X_cand, y_cand, gt = reproduction_case
    catalog = default_catalog()
    certs = run_reproduction_gate(
        catalog, reference_df=ref, candidate_df=X_cand,
        y_candidate=y_cand, ground_truth=gt,
        params_by_algorithm={
            "ks_shift": {"column": "mean radius", "alpha_shift": 0.05},
            "categorical_shift": {"column": "mean radius", "alpha_shift": 0.05},
            "mmd": {"target_pvalue_resolution": 0.05, "n_permutations": 20},
            "confident_learning": {"threshold_method": "mean", "floating_tolerance": 0.1, "min_gt_recall": 0.2},
            "metadata_claim_audit": {
                "claims": {"c1": {"predicate": "max_missing_rate",
                                  "column": "mean radius", "declared": 0.0}},
            },
        },
        created_at="2026-01-01T00:00:00Z",
    )
    gt_res = certs["confident_learning"].statistical_equivalence_result["ground_truth"]
    assert gt_res  # 非空，说明确实计算了 TP/FP/FN/TN
    assert gt_res["tp"] + gt_res["fn"] > 0  # label_flip 正例存在
