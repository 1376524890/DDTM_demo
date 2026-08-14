"""Audit-VOI 单元测试（规范 §23–§25 / §50）。"""

from __future__ import annotations

import pytest

from valor.audit.action_catalog import ActionCatalog, CertifiedAction
from valor.audit.bayes_update import bayes_update
from valor.audit.likelihood import ActionLikelihood
from valor.audit.loss import LossMatrix, bayes_risk
from valor.audit.policy import run_policy
from valor.audit.state_model import StateBelief
from valor.audit.voi import choose_best_action, marginal_value_of_audit


def _loss():
    return LossMatrix(loss={
        "ACCEPT": {"G": 0.0, "L": 5.0, "B": 50.0},
        "REJECT": {"G": 10.0, "L": 1.0, "B": 0.0},
        "TERMINATE": {"G": 10.0, "L": 1.0, "B": 1.0},
    })


def _belief():
    return StateBelief.from_prior(pi_b=0.3, q_l=0.3)


def test_three_state_prior():
    b = StateBelief.from_prior(0.2, 0.25)
    assert b.prob_b == pytest.approx(0.2)
    assert b.prob_l == pytest.approx(0.8 * 0.25)
    assert b.prob_g == pytest.approx(0.8 * 0.75)


def test_bayes_risk():
    b = _belief()
    risk, dec = bayes_risk(b, _loss())
    assert risk >= 0
    assert dec in ("ACCEPT", "REJECT", "TERMINATE")


def test_bayes_update():
    lik = {"G": 0.9, "L": 0.1, "B": 0.0}
    b = _belief()
    b2 = bayes_update(b, lik)
    assert b2.prob_g + b2.prob_l + b2.prob_b == pytest.approx(1.0)


def test_mv_positive_for_informative_action():
    b = _belief()
    # 高信息量动作：对 B 能区分
    lik = ActionLikelihood(action_id="a", rows={
        "PASS": {"G": 0.9, "L": 0.8, "B": 0.1},
        "QUALITY_FAIL": {"G": 0.1, "L": 0.2, "B": 0.4},
        "BREACH_EVIDENCE": {"G": 0.0, "L": 0.0, "B": 0.5},
    })
    mv, _ = marginal_value_of_audit(b, lik, _loss())
    assert mv >= 0


def test_choose_best_action_and_stop():
    b = _belief()
    catalog = ActionCatalog()
    lik = ActionLikelihood(action_id="a1", rows={
        "PASS": {"G": 0.9, "L": 0.8, "B": 0.1},
        "QUALITY_FAIL": {"G": 0.1, "L": 0.2, "B": 0.4},
        "BREACH_EVIDENCE": {"G": 0.0, "L": 0.0, "B": 0.5},
    })
    catalog.register(CertifiedAction("a1", lik, expected_cash_cost=0.5))
    aid, voi, details = choose_best_action(
        b, catalog.likelihoods(), _loss(), catalog.costs()
    )
    assert aid == "a1"
    assert voi > 0
    # 高成本 → STOP
    catalog2 = ActionCatalog()
    catalog2.register(CertifiedAction("a1", lik, expected_cash_cost=100.0))
    aid2, voi2, _ = choose_best_action(
        b, catalog2.likelihoods(), _loss(), catalog2.costs()
    )
    assert aid2 is None or voi2 <= 0


def test_run_policy():
    b = _belief()
    catalog = ActionCatalog()
    lik = ActionLikelihood(action_id="a1", rows={
        "PASS": {"G": 0.9, "L": 0.8, "B": 0.1},
        "QUALITY_FAIL": {"G": 0.1, "L": 0.2, "B": 0.4},
        "BREACH_EVIDENCE": {"G": 0.0, "L": 0.0, "B": 0.5},
    })
    catalog.register(CertifiedAction("a1", lik, expected_cash_cost=0.5))
    trace = run_policy(
        tx_id="tx-audit",
        initial_belief=b,
        catalog=catalog,
        loss=_loss(),
        observer=lambda aid: "PASS",
    )
    assert len(trace.steps) >= 1
    assert all(s.posterior for s in trace.steps)
