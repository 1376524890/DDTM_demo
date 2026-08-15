"""保密审计（Commit-then-Reveal）测试：节点不接触全量明文。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valor.core.hashing import content_hash
from valor.engine.private_audit import (
    CommitmentTree,
    DataSummary,
    PrivateAuditVerifier,
    private_audit_evidence_provider,
)


def _data(n=800, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"a": rng.normal(0, 1, n), "b": rng.normal(5, 2, n)})


def test_commitment_tree_root_and_proof():
    X = _data(100)
    y = pd.Series(np.random.default_rng(0).integers(0, 2, 100))
    tree = CommitmentTree(X, y)
    root = tree.root
    assert len(root) == 64
    # challenge 第 42 行：揭示行 → 验证 Merkle proof 匹配 root
    revealed = list(X.iloc[42].values)
    leaf = tree.leaf(42)
    proof = tree.merkle_proof(42)
    assert CommitmentTree.verify(root, 42, leaf, proof) is True
    # 篡改揭示行 → 验证失败
    bad_leaf = content_hash({"row": [0.0] * X.shape[1]})
    assert CommitmentTree.verify(root, 42, bad_leaf, proof) is False


def test_verifier_assesses_from_summary_only():
    """节点只凭摘要判定质量，不接触原始行。"""
    ref = _data(800, seed=0)
    clean = _data(800, seed=1)
    shifted = pd.DataFrame({
        "a": np.random.default_rng(2).normal(4, 1, 800),
        "b": np.random.default_rng(2).normal(9, 2, 800),
    })
    ref_sum = DataSummary.from_data(ref)
    clean_sum = DataSummary.from_data(clean)
    shift_sum = DataSummary.from_data(shifted)

    out_clean, _ = PrivateAuditVerifier(
        reference_summary=ref_sum, candidate_summary=clean_sum).assess_quality()
    out_shift, _ = PrivateAuditVerifier(
        reference_summary=ref_sum, candidate_summary=shift_sum).assess_quality()
    assert out_clean == "PASS"
    assert out_shift == "QUALITY_FAIL"


def test_provider_exposes_commitment_not_rows():
    """provider 给节点的只有摘要+承诺，不含原始行数据。"""
    ref = _data(300, seed=0)
    cand = _data(300, seed=1)
    y = pd.Series(np.random.default_rng(0).integers(0, 2, 300))
    prov = private_audit_evidence_provider(
        reference_X=ref, candidate_X=cand, candidate_y=y)
    r = prov("node-0", type("T", (), {"task_id": "t1"})())
    assert "commitment_root" in r["quality_metrics"]
    assert len(r["quality_metrics"]["commitment_root"]) == 64
    # 不包含任何原始特征值（保密性）
    assert not any("values" in k for k in r["quality_metrics"])
