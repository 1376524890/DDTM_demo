"""P6 离线校准 artifact 测试。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine.calibration import (
    AuditLikelihoodCalibrator,
    AuditPolicyCertifier,
    DetectionStats,
    FrozenArtifact,
    ValuationCalibrator,
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


def test_likelihood_derived_from_detection():
    cal = AuditLikelihoodCalibrator(
        action_id="a1", breach_family="structural",
        prior_state_probs={"G": 0.6, "L": 0.2, "B": 0.2})
    det = DetectionStats(tp=8, fp=1, fn=2, tn=89)
    rows = cal.likelihood_rows(det)
    # 高敏感度 → BREACH_EVIDENCE 下 B 的概率高
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["G"]
    art = cal.freeze(det=det, policy_hash="p" * 64)
    assert art.data["sensitivity"] == pytest.approx(8 / 10)


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
