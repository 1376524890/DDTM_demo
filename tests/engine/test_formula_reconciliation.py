"""FormulaReconciliationEngine 测试：独立复算核心公式。"""

from __future__ import annotations

import numpy as np

from valor.engine.formula_reconciliation import build_valor_engine


def _data_voi_stage():
    # 2 类，N_b=1000，confusion 与 payoff
    confusion = [[40, 10], [5, 45]]  # N_eval=100
    payoff = [[1.0, -2.0], [-5.0, 3.0]]
    joint = np.asarray(confusion) / 100.0
    u_plus = 1000.0 * float(np.sum(joint * np.asarray(payoff)))
    return {
        "u_plus": u_plus,
        "recompute_inputs": {
            "confusion_matrix": confusion, "payoff_matrix": payoff,
            "deployment_scale": 1000,
        },
    }


def test_data_voi_recompute():
    eng = build_valor_engine()
    res = eng.reconcile(_data_voi_stage())
    dv = [r for r in res if r["formula_id"] == "DATA_VOI_UTILITY"][0]
    assert dv["passed"] is True
    # 独立复算
    joint = np.asarray([[40, 10], [5, 45]]) / 100.0
    assert dv["recomputed"] == 1000.0 * np.sum(joint * np.asarray([[1, -2], [-5, 3]]))


def test_pricing_recompute():
    eng = build_valor_engine()
    # 一致的数据：P_max=310（320-10），P_min=58（5+10+20+3+4+6+10）
    p_min = 5 + 10 + 20 + 3 + 4 + 6 + 10  # 58
    p_max = max(0.0, min(500, 320 - 10 - 0 - 0 - 0 - 0))  # 310
    clearing = p_min + 0.5 * (p_max - p_min)  # 184
    stage = {
        "p_max": p_max, "p_min": p_min, "clearing_price": clearing,
        "recompute_inputs": {
            "v_gross_lower": 320.0, "c_i": 10.0, "c_a_b_pay": 0.0,
            "c_r_pay": 0.0, "c_b_use_cap": 0.0, "r_b_post": 0.0, "w_b_rem": 500.0,
            "c_marg": 5.0, "c_a_s_pay": 10.0, "c_b_cap": 20.0,
            "c_r_s_pay": 3.0, "r_s_post": 4.0, "oc_s": 6.0, "pi_s0": 10.0,
            "p_max": p_max, "p_min": p_min, "beta_bar": 0.5,
        },
    }
    res = {r["formula_id"]: r for r in eng.reconcile(stage)}
    assert res["PMAX"]["passed"] is True
    assert res["PMIN"]["passed"] is True
    assert res["PMIN"]["recomputed"] == p_min
    assert res["CLEAR_TRADE"]["recomputed"] == clearing


def test_p_breach_recompute():
    eng = build_valor_engine()
    from scipy.stats import beta

    a_D, b_D, alpha_D, tp, fn = 1.0, 1.0, 0.05, 20, 2
    p = beta.ppf(alpha_D, a_D + tp, b_D + fn)
    stage = {
        "p_breach_lower_sys": p,
        "recompute_inputs": {"a_D": a_D, "b_D": b_D, "alpha_D": alpha_D,
                             "tp": tp, "fn": fn},
    }
    res = [r for r in eng.reconcile(stage)
           if r["formula_id"] == "P_BREACH_LOWER_SYS"][0]
    assert res["passed"] is True


def test_vcg_total_recompute():
    eng = build_valor_engine()
    stage = {
        "mc_a_pay": 119.0,
        "recompute_inputs": {"vcg_payments": {"node-0": 17, "node-1": 17,
                                              "node-2": 17, "node-3": 17,
                                              "node-4": 17, "node-5": 17,
                                              "node-6": 17}},
    }
    res = [r for r in eng.reconcile(stage) if r["formula_id"] == "MC_A_PAY"][0]
    assert res["passed"] is True
    assert res["recomputed"] == 119.0
