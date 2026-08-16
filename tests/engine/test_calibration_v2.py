"""EmpiricalAuditLikelihood（真实三状态经验似然）测试。"""

from __future__ import annotations

import pytest

from valor.engine.calibration import (
    DEFAULT_DIRICHLET_ALPHA,
    EMPIRICAL_OUTCOMES,
    EmpiricalAuditLikelihood,
    freeze_empirical_likelihood,
)


def test_likelihood_normalized_per_state():
    """Σ_y Λ(y|x) = 1 对每个 x∈{G,L,B} 恒成立（Dirichlet 保证）。"""
    lik = EmpiricalAuditLikelihood(action_id="a1", breach_family="structural")
    lik.add("G", "PASS"); lik.add("G", "PASS"); lik.add("G", "CLAIM_NOT_SUPPORTED")
    lik.add("L", "CLAIM_NOT_SUPPORTED"); lik.add("L", "CLAIM_NOT_SUPPORTED")
    lik.add("L", "INCONCLUSIVE")
    lik.add("B", "BREACH_EVIDENCE"); lik.add("B", "BREACH_EVIDENCE")
    lik.add("B", "BREACH_EVIDENCE"); lik.add("B", "PASS")
    rows = lik.likelihood_rows()
    for state in ("G", "L", "B"):
        total = sum(rows[y][state] for y in EMPIRICAL_OUTCOMES)
        assert total == pytest.approx(1.0, abs=1e-9), f"{state} 未归一化"


def test_L_vs_B_distinguished():
    """L（诚实但不适合）与 B（真实 breach）产生不同似然。"""
    lik = EmpiricalAuditLikelihood(action_id="a1", breach_family="structural")
    for _ in range(50): lik.add("G", "PASS")
    for _ in range(50): lik.add("L", "CLAIM_NOT_SUPPORTED")
    for _ in range(50): lik.add("B", "BREACH_EVIDENCE")
    rows = lik.likelihood_rows()
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["G"]
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["L"]
    assert rows["CLAIM_NOT_SUPPORTED"]["L"] > rows["CLAIM_NOT_SUPPORTED"]["B"]


def test_dirichlet_smoothing_no_zero_columns():
    """即使某 (x,y) 无观测，smoothing 保证非零（避免 bayes_update 除零）。"""
    lik = EmpiricalAuditLikelihood(action_id="a1", breach_family="structural")
    lik.add("G", "PASS")
    rows = lik.likelihood_rows()
    for state in ("G", "L", "B"):
        for y in EMPIRICAL_OUTCOMES:
            assert rows[y][state] > 0.0, f"({state},{y}) 为 0"


def test_freeze_artifact_deterministic():
    lik = EmpiricalAuditLikelihood(action_id="a1", breach_family="structural")
    lik.add("G", "PASS"); lik.add("B", "BREACH_EVIDENCE")
    a = freeze_empirical_likelihood(lik, policy_hash="p" * 64,
                                    calibration_hash="c" * 64)
    b = freeze_empirical_likelihood(lik, policy_hash="p" * 64,
                                    calibration_hash="c" * 64)
    assert a["artifact_hash"] == b["artifact_hash"]
    for s in ("G", "L", "B"):
        assert abs(a["normalized_sum_per_state"][s] - 1.0) < 1e-6
