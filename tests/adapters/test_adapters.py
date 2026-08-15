"""P1 DatasetAdapter / TrainerAdapter / RoleSplit 测试。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valor.adapters.base import RoleSplit
from valor.valuation.economic_mapping import (
    BuyerContext,
    utility_delta_from_artifact,
    utility_from_artifact,
)


def _mk_split(n=1000):
    return RoleSplit(
        historical_idx=np.arange(0, 200),
        buyer_base_idx=np.arange(200, 400),
        seller_candidate_idx=np.arange(400, 600),
        transaction_eval_idx=np.arange(600, 800),
        final_evaluation_idx=np.arange(800, 1000),
    )


def test_role_split_disjoint():
    s = _mk_split()
    assert s.counts() == {"historical": 200, "buyer_base": 200,
                          "seller_candidate": 200, "transaction_eval": 200,
                          "final_evaluation": 200}


def test_role_split_overlap_rejected():
    import pytest

    with pytest.raises(ValueError, match="重叠"):
        RoleSplit(
            historical_idx=np.array([0, 1]),
            buyer_base_idx=np.array([1, 2]),
            seller_candidate_idx=np.array([3, 4]),
            transaction_eval_idx=np.array([5, 6]),
            final_evaluation_idx=np.array([7, 8]),
        )


def test_utility_uses_deployment_scale_not_eval_size():
    # eval 集 100 个样本，但 N_b = 10000 → 效用应按 N_b 放大
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 10, size=100)
    y_pred = y_true.copy()  # 完美预测
    payoff = np.eye(10)  # 对角线 +1
    u = utility_from_artifact(y_true, y_pred, payoff, deployment_scale=10000)
    assert u == 10000.0  # N_b * 1.0（完美预测，每样本收益 1）

    u_small = utility_from_artifact(y_true, y_pred, payoff, deployment_scale=10)
    assert u_small == 10.0


def test_utility_delta():
    class A:
        def __init__(self, yt, yp):
            self.y_true = yt
            self.y_pred = yp

    rng = np.random.default_rng(1)
    y_true = rng.integers(0, 10, size=50)
    base = A(y_true, rng.integers(0, 10, size=50))
    plus = A(y_true, y_true)  # 完美
    payoff = np.eye(10)
    u_b, u_p, d = utility_delta_from_artifact(base, plus, payoff, deployment_scale=500)
    assert u_b < u_p
    assert d == u_p - u_b


def test_buyer_context_plain():
    ctx = BuyerContext(task_id="digit-cls", deployment_scale=1000,
                       payoff_matrix=np.eye(10), application_context="banking")
    p = ctx.to_plain()
    assert p["deployment_scale"] == 1000
    assert p["task_id"] == "digit-cls"
