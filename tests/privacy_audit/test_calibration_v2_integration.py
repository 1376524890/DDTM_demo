"""P0-2 真实三状态经验似然 V2 集成测试。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.privacy_audit.calibration import calibrate_empirical_likelihood_v2


def _mnist(n=500, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.integers(0, 256, size=(n, 784), dtype=np.uint8),
            rng.integers(0, 10, size=n))


def test_v2_normalized_and_L_ne_B():
    """三状态经验似然归一化，且 L≠B 语义成立。"""
    X, y = _mnist(500)
    art = calibrate_empirical_likelihood_v2(
        X=X, y=y, challenge_sizes=[64], n_runs=3,
        label_latent_frac=0.05, label_breach_frac=0.3, seed=0)
    assert art["kind"] == "audit_likelihood_v2"
    assert len(art["artifact_hash"]) == 64
    lik = art["likelihoods"]["64"]
    rows = lik["rows"]
    # 每状态归一化
    for state in ("G", "L", "B"):
        total = sum(rows[y][state] for y in
                    ("PASS", "CLAIM_NOT_SUPPORTED", "BREACH_EVIDENCE", "INCONCLUSIVE"))
        assert total == pytest.approx(1.0, abs=1e-6), f"{state} 未归一化"
    # B（篡改）→ BREACH_EVIDENCE 概率高；L（轻度污染）≠ B
    assert rows["BREACH_EVIDENCE"]["B"] > 0.5
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["L"]


def test_v2_no_manual_05():
    """似然来自经验计数+Dirichlet（非人工固定 L=0.5）：G/L/B 对同结果区分。"""
    X, y = _mnist(300)
    art = calibrate_empirical_likelihood_v2(
        X=X, y=y, challenge_sizes=[32], n_runs=2, seed=1)
    for k, lik in art["likelihoods"].items():
        rows = lik["rows"]
        # 核心 L≠B 证据：真实 breach（B）应显著更可能 BREACH_EVIDENCE
        assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["G"]
        assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["L"]
        # 归一化
        for state in ("G", "L", "B"):
            total = sum(rows[y][state] for y in rows)
            assert total == pytest.approx(1.0, abs=1e-6)
