"""经济机制单调性属性测试（任务书 §43）。

只验证理论必然的单调关系，不强迫非理论必然关系：
    p̲_B^sys ↑ → B_S^* 非增
    买方 audit/enforcement/risk cost ↑ → P_max 非增
    卖方 audit/bond/opportunity/risk cost ↑ → P_min 非减
    beta=0 → P*=P_min；beta=1 → P*=P_max；对 beta 单调
    更强 misuse detection → usage bond 非增
"""

from __future__ import annotations

import pytest

from valor.liability.buyer_usage_bond import buyer_usage_bond_required
from valor.liability.seller_bond import seller_bond_required
from valor.pricing.buyer_max import buyer_max_price
from valor.pricing.clearing import clear_trade
from valor.pricing.seller_min import seller_min_price


def test_seller_bond_decreasing_in_detection():
    """p̲_B^sys ↑ → B_S^* 非增（检测越强，保证金越低）。"""
    kwargs = dict(g_dev=60.0, eps_s=1.0, p_e_bond=1.0, p_e_f=0.3,
                  lambda_s=0.5, f_s=10.0)
    bonds = [seller_bond_required(p_breach_lower_sys=p, **kwargs)
             for p in [0.2, 0.4, 0.6, 0.8]]
    assert all(bonds[i] >= bonds[i + 1] for i in range(len(bonds) - 1))


def test_pmax_non_increasing_in_costs():
    """买方 audit/enforcement/risk cost ↑ → P_max 非增。"""
    base = dict(w_b_rem=500.0, v_gross_lower=300.0, c_i=20.0,
                c_a_b_pay=10.0, c_r_pay=5.0, c_b_use_cap=2.0, r_b_post=5.0)
    pmax = [buyer_max_price(**{**base, "c_a_b_pay": c}) for c in [5, 10, 15, 20]]
    assert all(pmax[i] >= pmax[i + 1] for i in range(len(pmax) - 1))
    pmax2 = [buyer_max_price(**{**base, "r_b_post": r}) for r in [1, 5, 10]]
    assert all(pmax2[i] >= pmax2[i + 1] for i in range(len(pmax2) - 1))


def test_pmin_non_decreasing_in_costs():
    """卖方 audit/bond/opportunity/risk cost ↑ → P_min 非减。"""
    base = dict(c_marg=5.0, c_a_s_pay=10.0, c_b_cap=8.0, c_r_s_pay=3.0,
                r_s_post=4.0, oc_s=6.0, pi_s0=10.0)
    pmin = [seller_min_price(**{**base, "oc_s": o}) for o in [2, 6, 10]]
    assert all(pmin[i] <= pmin[i + 1] for i in range(len(pmin) - 1))
    pmin2 = [seller_min_price(**{**base, "c_b_cap": c}) for c in [4, 8, 12]]
    assert all(pmin2[i] <= pmin2[i + 1] for i in range(len(pmin2) - 1))


def test_beta_bounds():
    """beta=0 → P*=P_min；beta=1 → P*=P_max；对 beta 单调。"""
    r = clear_trade(p_max=200.0, p_min=100.0, beta_bar=0.0)
    assert r.clearing_price == pytest.approx(100.0)
    r2 = clear_trade(p_max=200.0, p_min=100.0, beta_bar=1.0)
    assert r2.clearing_price == pytest.approx(200.0)
    prices = [clear_trade(p_max=200.0, p_min=100.0, beta_bar=b).clearing_price
              for b in [0.0, 0.3, 0.5, 0.8, 1.0]]
    assert all(prices[i] <= prices[i + 1] for i in range(len(prices) - 1))


def test_usage_bond_decreasing_in_detection():
    """更强 misuse detection → usage bond 非增。"""
    kwargs = dict(g_misuse=50.0, eps_b=1.0, p_e_ubond=1.0, p_e_uf=0.0,
                  lambda_b=1.0, f_b=0.0)
    bonds = [buyer_usage_bond_required(p_misuse_lower_sys=p, **kwargs)
             for p in [0.3, 0.5, 0.7, 0.9]]
    assert all(bonds[i] >= bonds[i + 1] for i in range(len(bonds) - 1))


def test_clearing_negative_margin_no_trade():
    """P_max < P_min → NO_TRADE。"""
    r = clear_trade(p_max=80.0, p_min=100.0, beta_bar=0.5)
    assert r.decision == "NO_TRADE"
    assert r.clearing_price is None
