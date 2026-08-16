"""P0-2 Audit Likelihood Calibration V2 测试。"""

from __future__ import annotations

import pytest

from valor.engine.calibration_v2 import (
    DEFAULT_ALPHA,
    EmpiricalLikelihood,
    freeze_empirical_likelihood,
)


def test_likelihood_normalized_per_state():
    """Σ_y Λ(y|x) = 1 对每个 x∈{G,L,B} 恒成立（Dirichlet 保证）。"""
    lik = EmpiricalLikelihood(action_id="a1", breach_family="structural")
    # 记录若干观测
    lik.add("G", "PASS"); lik.add("G", "PASS"); lik.add("G", "CLAIM_NOT_SUPPORTED")
    lik.add("L", "CLAIM_NOT_SUPPORTED"); lik.add("L", "CLAIM_NOT_SUPPORTED")
    lik.add("L", "INCONCLUSIVE")
    lik.add("B", "BREACH_EVIDENCE"); lik.add("B", "BREACH_EVIDENCE")
    lik.add("B", "BREACH_EVIDENCE"); lik.add("B", "PASS")
    rows = lik.likelihood_rows()
    for state in ("G", "L", "B"):
        total = sum(rows[y][state] for y in ("PASS", "CLAIM_NOT_SUPPORTED",
                                             "BREACH_EVIDENCE", "INCONCLUSIVE"))
        assert total == pytest.approx(1.0, abs=1e-9), f"{state} 未归一化"


def test_L_vs_B_distinguished():
    """L（诚实但不适合）与 B（真实 breach）产生不同似然。"""
    lik = EmpiricalLikelihood(action_id="a1", breach_family="structural")
    # G 多 PASS
    for _ in range(50): lik.add("G", "PASS")
    # L 多 CLAIM_NOT_SUPPORTED（不适合，非 breach）
    for _ in range(50): lik.add("L", "CLAIM_NOT_SUPPORTED")
    # B 多 BREACH_EVIDENCE（真实 breach）
    for _ in range(50): lik.add("B", "BREACH_EVIDENCE")
    rows = lik.likelihood_rows()
    # BREACH_EVIDENCE 对 B 概率最高
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["G"]
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["L"]
    # CLAIM_NOT_SUPPORTED 对 L 概率高（L≠B 语义）
    assert rows["CLAIM_NOT_SUPPORTED"]["L"] > rows["CLAIM_NOT_SUPPORTED"]["B"]


def test_dirichlet_smoothing_no_zero_columns():
    """即使某 (x,y) 无观测，smoothing 保证非零（避免 bayes_update 除零）。"""
    lik = EmpiricalLikelihood(action_id="a1", breach_family="structural")
    lik.add("G", "PASS")
    rows = lik.likelihood_rows()
    for state in ("G", "L", "B"):
        for y in ("PASS", "CLAIM_NOT_SUPPORTED", "BREACH_EVIDENCE", "INCONCLUSIVE"):
            assert rows[y][state] > 0.0, f"({state},{y}) 为 0"


def test_freeze_artifact_deterministic():
    lik = EmpiricalLikelihood(action_id="a1", breach_family="structural")
    lik.add("G", "PASS"); lik.add("B", "BREACH_EVIDENCE")
    a = freeze_empirical_likelihood(lik, policy_hash="p" * 64,
                                    calibration_hash="c" * 64)
    b = freeze_empirical_likelihood(lik, policy_hash="p" * 64,
                                    calibration_hash="c" * 64)
    assert a["artifact_hash"] == b["artifact_hash"]
    # 归一化记录
    for s in ("G", "L", "B"):
        assert abs(a["normalized_sum_per_state"][s] - 1.0) < 1e-6
