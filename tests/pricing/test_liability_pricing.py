"""责任与定价测试（规范 §30/§31/§38–§42）。"""

from __future__ import annotations

import pytest

from valor.core.errors import InfeasibleSecurityError
from valor.contract.accounts import Ledger, LedgerError, Transfer
from valor.contract.escrow import EscrowAccounts
from valor.liability.buyer_usage_bond import buyer_usage_bond_required
from valor.liability.capital_cost import capital_cost
from valor.liability.seller_bond import seller_bond_required
from valor.liability.seller_prelock import seller_prelock
from valor.pricing.buyer_max import buyer_max_price
from valor.pricing.clearing import clear_trade
from valor.pricing.seller_min import seller_min_price


def test_seller_bond():
    b = seller_bond_required(
        p_breach_lower_sys=0.9, g_dev=100.0, eps_s=1.0,
        p_e_bond=1.0, p_e_f=0.5, lambda_s=0.5, f_s=10.0,
    )
    # (101/0.9 - 5)/0.5 ≈ 202.2
    assert b > 0
    with pytest.raises(InfeasibleSecurityError):
        seller_bond_required(
            p_breach_lower_sys=0.0, g_dev=100.0, eps_s=1.0,
            p_e_bond=1.0, p_e_f=0.5, lambda_s=0.5, f_s=10.0,
        )


def test_seller_prelock_max():
    pre = seller_prelock(
        cells=[{"p_breach_lower_sys": 0.9}, {"p_breach_lower_sys": 0.5}],
        g_dev=100.0, eps_s=1.0, p_e_bond=1.0, p_e_f=0.5, lambda_s=0.5, f_s=10.0,
    )
    lo = seller_bond_required(
        p_breach_lower_sys=0.5, g_dev=100.0, eps_s=1.0,
        p_e_bond=1.0, p_e_f=0.5, lambda_s=0.5, f_s=10.0)
    assert pre >= lo


def test_buyer_usage_bond():
    b = buyer_usage_bond_required(
        p_misuse_lower_sys=0.8, g_misuse=50.0, eps_b=1.0,
        p_e_ubond=1.0, p_e_uf=0.0, lambda_b=0.5, f_b=0.0,
    )
    assert b > 0


def test_capital_cost():
    c = capital_cost(kappa_s=0.1, bond_pre=100.0, bond_required=80.0,
                     t_pre=2.0, t_post=3.0)
    assert c == pytest.approx(0.1 * (100 * 2 + 80 * 3))


def test_buyer_max():
    pmax = buyer_max_price(
        w_b_rem=1000.0, v_gross_lower=800.0, c_i=50.0, c_a_b_pay=20.0,
        c_r_pay=10.0, c_b_use_cap=5.0, r_b_post=30.0,
    )
    # 800-50-20-10-5-30 = 685
    assert pmax == pytest.approx(685.0)


def test_seller_min():
    pmin = seller_min_price(
        c_marg=10.0, c_a_s_pay=20.0, c_b_cap=15.0, c_r_s_pay=5.0,
        r_s_post=8.0, oc_s=12.0, pi_s0=30.0,
    )
    assert pmin == pytest.approx(100.0)


def test_clear_trade():
    ok = clear_trade(p_max=200.0, p_min=100.0, beta_bar=0.5)
    assert ok.decision == "TRADE" and ok.clearing_price == pytest.approx(150.0)
    notrade = clear_trade(p_max=80.0, p_min=100.0, beta_bar=0.5)
    assert notrade.decision == "NO_TRADE" and notrade.clearing_price is None


def test_ledger_conservation():
    ledger = Ledger()
    ledger.create_account("buyer", 500.0)
    ledger.create_account("seller", 0.0)
    ledger.create_account("escrow", 0.0)
    ledger.transfer(Transfer("buyer", "escrow", 200.0, "purchase escrow"))
    ledger.transfer(Transfer("escrow", "seller", 200.0, "settle"))
    assert ledger.balance("buyer") == 300.0
    assert ledger.balance("seller") == 200.0
    assert ledger.conservation_check()
    # 余额不足必须失败
    with pytest.raises(LedgerError):
        ledger.transfer(Transfer("buyer", "escrow", 99999.0, "overdraft"))


def test_escrow_accounts():
    e = EscrowAccounts(b_s_pre=100.0, b_s_star=80.0)
    assert e.to_plain()["B_S^pre"] == 100.0
