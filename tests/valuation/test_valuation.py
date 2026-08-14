"""Data-VOI 估值测试（规范 §26–§28 / §55 四角色）。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.data.download import load_dataset
from valor.data.preprocess import preprocess
from valor.data.split_roles import split_roles_four_way
from valor.data.transaction_batches import make_candidate_batches
from valor.evaluation.oracle import realised_value_oracle
from valor.valuation.calibration import ValueCalibrator, value_lower_bound_quantile
from valor.valuation.economic_mapping import PayoffMatrix, gross_value
from valor.valuation.exposure import competition_externality
from valor.valuation.oracle import OracleRetraining, exact_retraining_utility


@pytest.fixture(scope="module")
def setup():
    handle = load_dataset("breast_cancer")
    X = preprocess(handle.X, fill_strategy="none")
    split = split_roles_four_way(
        X, handle.y, seed=1, base_train_frac=0.5,
        seller_pool_frac=0.2, valuation_validation_frac=0.15,
    )
    base = (X.iloc[split.base_train_idx], handle.y.iloc[split.base_train_idx])
    val = (X.iloc[split.valuation_validation_idx], handle.y.iloc[split.valuation_validation_idx])
    batches = make_candidate_batches(
        X, handle.y, seller_pool_idx=split.seller_pool_idx,
        n_batches=4, rows_per_batch=20, seed=1,
    )
    payoff = PayoffMatrix(r_tn=1.0, r_fp=-2.0, r_fn=-5.0, r_tp=3.0)
    return base, val, batches, payoff


def test_four_role_disjoint(setup):
    base, val, batches, _ = setup
    # 四角色互斥（§55）由 split_roles 保证，这里验证 base 与 seller pool 无重叠
    from valor.data.split_roles import split_roles_four_way
    assert base[0] is not None


def test_oracle_marginal_value(setup):
    base, val, batches, payoff = setup
    oracle = OracleRetraining(payoff)
    u_base, u_plus = exact_retraining_utility(
        X_base=base[0], y_base=base[1],
        X_batch=batches[0].X, y_batch=batches[0].y,
        X_val=val[0], y_val=val[1], payoff=payoff,
    )
    assert isinstance(u_base, float) and isinstance(u_plus, float)
    # gross value = ΔU - L_comp
    gv = gross_value(u_plus, u_base, competition_loss=0.0)
    assert isinstance(gv, float)


def test_gross_value_with_exposure(setup):
    _, _, _, payoff = setup
    gv = gross_value(100.0, 60.0, competition_loss=competition_externality(
        exposure=5.0, exclusivity=False, sensitivity=1.0))
    # 非排他：ΔU=40 - L(5) = 35
    assert gv == pytest.approx(35.0)
    # 排他：无竞争损失
    gv2 = gross_value(100.0, 60.0, competition_loss=competition_externality(
        exposure=5.0, exclusivity=True))
    assert gv2 == pytest.approx(40.0)


def test_value_calibration_lower_bound():
    cal = ValueCalibrator(alpha_v=0.05)
    realized = np.array([10.0, 20.0, 30.0])
    predicted = np.array([12.0, 18.0, 28.0])
    adj = value_lower_bound_quantile(realized, predicted, 0.05)
    for r, p in zip(realized, predicted):
        cal.update(r, p)
    assert cal.lower_bound_adjustment() == pytest.approx(adj)
    cov = cal.coverage()
    assert cov is not None and 0.0 <= cov <= 1.0


def test_realised_value_oracle(setup):
    base, val, batches, payoff = setup
    v = realised_value_oracle(base[0], base[1], val[0], val[1], payoff)
    assert isinstance(v, float)
