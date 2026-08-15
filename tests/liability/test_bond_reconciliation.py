"""P7 Seller Bond 激励约束对账测试。"""

from __future__ import annotations

import pytest

from valor.liability.seller_bond import reconcile_seller_bond, seller_bond_required


def test_reconciliation_passes_for_computed_bond():
    """用 seller_bond_required 算出的 bond 应满足 IC（slack≈0，浮点容差内）。"""
    params = dict(p_breach_lower_sys=0.8, g_dev=60.0, eps_s=1.0,
                  p_e_bond=1.0, p_e_f=0.3, lambda_s=0.5, f_s=10.0)
    bond = seller_bond_required(**params)
    recon = reconcile_seller_bond(bond=bond, **params)
    assert recon["pass"] is True
    assert recon["constraint_slack"] > -1e-6


def test_insufficient_bond_fails():
    params = dict(p_breach_lower_sys=0.8, g_dev=60.0, eps_s=1.0,
                  p_e_bond=1.0, p_e_f=0.3, lambda_s=0.5, f_s=10.0)
    recon = reconcile_seller_bond(bond=0.0, **params)  # bond=0 应不满足
    assert recon["pass"] is False
    assert recon["constraint_slack"] < 0


def test_lhs_rhs_formula():
    params = dict(p_breach_lower_sys=0.8, g_dev=60.0, eps_s=1.0,
                  p_e_bond=1.0, p_e_f=0.3, lambda_s=0.5, f_s=10.0)
    bond = 152.5
    recon = reconcile_seller_bond(bond=bond, **params)
    # LHS = 0.8*(1.0*0.5*152.5 + 0.3*10) = 0.8*(76.25+3) = 63.4
    assert recon["constraint_lhs"] == pytest.approx(0.8 * (0.5 * 152.5 + 3.0))
    assert recon["constraint_rhs"] == pytest.approx(61.0)
