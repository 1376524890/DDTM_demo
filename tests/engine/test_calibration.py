"""P6 离线校准 artifact 测试。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine.calibration import (
    EMPIRICAL_OUTCOMES,
    EMPIRICAL_STATES,
    AuditPolicyCertifier,
    DetectionStats,
    EmpiricalAuditLikelihood,
    FrozenArtifact,
    ValuationCalibrator,
    freeze_empirical_likelihood,
)


def test_valuation_calibrator_requires_samples():
    vc = ValuationCalibrator(alpha_v=0.05)
    with pytest.raises(ValueError, match="无样本"):
        vc.lower_bound_adjustment()
    with pytest.raises(ValueError, match="无样本"):
        vc.freeze(dataset_hash="d" * 64, trainer_hash="t" * 64,
                  buyer_context_family="digit", seed=0)


def test_valuation_calibrator_quantile():
    vc = ValuationCalibrator(alpha_v=0.1)
    for realized, pred in [(100, 90), (120, 100), (80, 85), (90, 95), (110, 105)]:
        vc.add(realized, pred)
    art = vc.freeze(dataset_hash="d" * 64, trainer_hash="t" * 64,
                    buyer_context_family="digit", seed=0)
    assert art.kind == "valuation_calibration"
    assert len(art.artifact_hash) == 64
    assert 0.0 <= art.data["coverage"] <= 1.0


def test_likelihood_empirical_from_detection():
    """唯一正式似然校准 = EmpiricalAuditLikelihood（无人工 L=0.5）。"""
    lik = EmpiricalAuditLikelihood(action_id="a1", breach_family="structural")
    # B：真实 breach → BREACH_EVIDENCE 主导
    for _ in range(8):
        lik.add("B", "BREACH_EVIDENCE")
    for _ in range(2):
        lik.add("B", "PASS")
    # G：干净 → PASS 主导（少量误报）
    lik.add("G", "PASS")
    lik.add("G", "PASS")
    lik.add("G", "BREACH_EVIDENCE")
    # L：轻度污染 → CLAIM_NOT_SUPPORTED，与 B 区分
    lik.add("L", "CLAIM_NOT_SUPPORTED")
    lik.add("L", "PASS")
    rows = lik.likelihood_rows()
    # 高敏感度 → BREACH_EVIDENCE 下 B 的概率高
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["G"]
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["L"]
    # L ≠ B：L 不产生 BREACH_EVIDENCE 主导
    assert rows["BREACH_EVIDENCE"]["L"] < rows["BREACH_EVIDENCE"]["B"]
    # 归一化
    for s in EMPIRICAL_STATES:
        assert abs(sum(rows[y][s] for y in EMPIRICAL_OUTCOMES) - 1.0) < 1e-9
    # freeze 确定性
    art = freeze_empirical_likelihood(
        lik, policy_hash="p" * 64, calibration_hash="c" * 64)
    assert art["kind"] == "audit_likelihood"
    assert art["artifact_hash"] == freeze_empirical_likelihood(
        lik, policy_hash="p" * 64, calibration_hash="c" * 64)["artifact_hash"]


def test_certificate_frozen_p_breach():
    certifier = AuditPolicyCertifier(a_D=1.0, b_D=1.0, alpha_D=0.05)
    art = certifier.certify(cell_id="c1", breach_family="structural",
                            tp=20, fn=2, policy_hash="p" * 64,
                            action_catalog_hash="a" * 64)
    assert art.kind == "audit_policy_certificate"
    assert 0.0 < art.data["p_breach_lower_sys"] < 1.0
    assert len(art.artifact_hash) == 64


def test_frozen_artifact_deterministic_hash():
    a1 = FrozenArtifact("x", {"v": 1})
    a2 = FrozenArtifact("x", {"v": 1})
    a3 = FrozenArtifact("x", {"v": 2})
    assert a1.artifact_hash == a2.artifact_hash
    assert a1.artifact_hash != a3.artifact_hash
