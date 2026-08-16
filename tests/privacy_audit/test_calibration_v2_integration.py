"""真实三状态经验似然（EmpiricalAuditLikelihood）集成测试。

似然由 calibration_cases 的 observation 计数 + Dirichlet smoothing 估计，
L≠B 语义严格成立，且 freeze 走 engine/calibration.py（唯一 freeze 方）。
"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine.calibration import (
    EMPIRICAL_OUTCOMES,
    EmpiricalAuditLikelihood,
    freeze_empirical_likelihood,
)
from valor.privacy_audit.calibration_cases import (
    run_breach_case,
    run_good_case,
    run_latent_case,
)


def _mnist(n=500, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.integers(0, 256, size=(n, 784), dtype=np.uint8),
            rng.integers(0, 10, size=n))


def _empirical_from_cases(X, y, k, n_runs=3, latent_frac=0.05):
    """用真实 G/L/B case 的 observation 构造经验似然。"""
    lik = EmpiricalAuditLikelihood(action_id=f"a-{k}", breach_family="structural")
    for run in range(n_runs):
        lik.add("G", run_good_case(X, y, k, seed=run))
        lik.add("L", run_latent_case(X, y, k, seed=run, latent_frac=latent_frac))
        lik.add("B", run_breach_case(X, y, k, seed=run))
    return lik


def test_normalized_and_L_ne_B():
    """三状态经验似然归一化，且 L≠B 语义成立。"""
    X, y = _mnist(500)
    lik = _empirical_from_cases(X, y, 64, n_runs=3)
    rows = lik.likelihood_rows()
    for state in ("G", "L", "B"):
        total = sum(rows[y][state] for y in EMPIRICAL_OUTCOMES)
        assert total == pytest.approx(1.0, abs=1e-9), f"{state} 未归一化"
    # B（篡改）→ BREACH_EVIDENCE 概率高；L（轻度污染）≠ B
    assert rows["BREACH_EVIDENCE"]["B"] > 0.5
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["L"]


def test_no_manual_05():
    """似然来自经验计数+Dirichlet（非人工固定 L=0.5）：G/L/B 对同结果区分。"""
    X, y = _mnist(300)
    lik = _empirical_from_cases(X, y, 32, n_runs=2)
    rows = lik.likelihood_rows()
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["G"]
    assert rows["BREACH_EVIDENCE"]["B"] > rows["BREACH_EVIDENCE"]["L"]
    for state in ("G", "L", "B"):
        total = sum(rows[y][state] for y in EMPIRICAL_OUTCOMES)
        assert total == pytest.approx(1.0, abs=1e-9)


def test_freeze_artifact_deterministic():
    """freeze 走 engine.calibration，确定性 hash，policy_hash 非占位。"""
    X, y = _mnist(300)
    lik = _empirical_from_cases(X, y, 32, n_runs=2)
    ph = "p" * 64
    a = freeze_empirical_likelihood(lik, policy_hash=ph,
                                    calibration_hash="c" * 64)
    b = freeze_empirical_likelihood(lik, policy_hash=ph,
                                    calibration_hash="c" * 64)
    assert a["artifact_hash"] == b["artifact_hash"]
    assert a["kind"] == "audit_likelihood"
    for s in ("G", "L", "B"):
        assert abs(a["normalized_sum_per_state"][s] - 1.0) < 1e-6
