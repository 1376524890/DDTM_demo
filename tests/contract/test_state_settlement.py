"""状态机 + 结算 + 效用/福利测试（规范 §43/§44）。"""

from __future__ import annotations

import pytest

from valor.contract.accounts import Ledger, Transfer
from valor.contract.escrow import EscrowAccounts
from valor.contract.settlement import settle
from valor.contract.state_machine import StateMachineInput, TransactionStateMachine
from valor.core.enums import RightsState, TerminalState
from valor.evaluation.utilities import (
    auditor_utility,
    buyer_utility,
    seller_profit,
)
from valor.evaluation.welfare import social_welfare_full


def test_state_machine_transitions():
    sm = TransactionStateMachine()
    # 正常 → TRADE
    assert sm.resolve(StateMachineInput(True, True, False, "TRADE", False)) == TerminalState.TRADE
    # 审计发现违约 → SELLER_BREACH
    assert sm.resolve(StateMachineInput(True, True, True, "TRADE", False)) == TerminalState.SELLER_BREACH
    # 价格不可行 → NO_TRADE
    assert sm.resolve(StateMachineInput(True, True, False, "NO_TRADE", False)) == TerminalState.NO_TRADE
    # 硬门槛失败 → NO_TRADE
    assert sm.resolve(StateMachineInput(False, True, False, "TRADE", False)) == TerminalState.NO_TRADE
    # 买方违约 → BUYER_BREACH
    assert sm.resolve(StateMachineInput(True, True, False, "TRADE", True)) == TerminalState.BUYER_BREACH


def test_rights_transition():
    sm = TransactionStateMachine()
    assert sm.rights_transition(TerminalState.TRADE) == RightsState.ACTIVE
    assert sm.rights_transition(TerminalState.BUYER_BREACH) == RightsState.REVOKED


def test_settlement_trade():
    ledger = Ledger({"buyer": 1000.0, "seller": 0.0, "E_B^P": 300.0,
                     "E_S^A": 0.0, "E_B^A": 0.0, "B_S^pre": 100.0, "B_S^*": 80.0})
    accounts = EscrowAccounts(e_b_p=300.0, b_s_pre=100.0, b_s_star=80.0)
    res = settle(terminal=TerminalState.TRADE, ledger=ledger, accounts=accounts,
                 price=200.0, audit_pay_s=10.0, audit_pay_b=0.0)
    assert res.terminal_state == TerminalState.TRADE
    assert ledger.balance("seller") == pytest.approx(200.0 + 20.0)  # price + released prelock diff


def test_settlement_no_trade():
    ledger = Ledger({"buyer": 0.0, "seller": 0.0, "E_B^P": 300.0,
                     "E_S^A": 50.0, "E_B^A": 50.0, "B_S^pre": 100.0, "B_S^*": 100.0})
    accounts = EscrowAccounts(e_b_p=300.0, b_s_pre=100.0, b_s_star=100.0)
    settle(terminal=TerminalState.NO_TRADE, ledger=ledger, accounts=accounts,
           price=300.0, audit_pay_s=10.0, audit_pay_b=5.0)
    assert ledger.conservation_check()


def test_settlement_seller_breach_slashes_bond():
    ledger = Ledger({"buyer": 0.0, "seller": 0.0, "E_B^P": 300.0,
                     "E_S^A": 50.0, "B_S^pre": 100.0, "B_S^*": 100.0, "E_B^A": 0.0})
    accounts = EscrowAccounts(e_b_p=300.0, b_s_pre=100.0, b_s_star=100.0)
    res = settle(terminal=TerminalState.SELLER_BREACH, ledger=ledger,
                 accounts=accounts, price=300.0, audit_pay_s=10.0, audit_pay_b=0.0,
                 bond_slash_fraction=1.0)
    assert res.bond_slashed == pytest.approx(100.0)
    assert ledger.balance("buyer") == pytest.approx(300.0 + 100.0)  # escrow refund + slashed bond


def test_utilities():
    assert buyer_utility(v_real=300.0, price=200.0, c_i=10.0, c_a_b_pay=5.0,
                         c_r_pay=5.0, c_b_use_cap=2.0, l_b_real=3.0) == pytest.approx(75.0)
    assert seller_profit(price=200.0, c_marg=40.0, c_a_s_pay=10.0, c_b_cap=15.0,
                         c_r_s_pay=5.0, oc_s_real=8.0, penalty_s_real=2.0) == pytest.approx(120.0)
    assert auditor_utility(p_i_a=30.0, k_i=10.0, kappa_a=0.1, bond_a_i=50.0,
                           t_a=2.0, slash_i_real=0.0) == pytest.approx(10.0)


def test_social_welfare():
    sw = social_welfare_full(
        v_real=300.0, c_d_marg=40.0, c_i=10.0, c_audit_service_res=20.0,
        c_protocol_res=15.0, c_b_cap=10.0, c_a_cap=5.0, c_b_use_cap=2.0,
        expected_residual_loss=8.0,
    )
    assert sw == pytest.approx(300 - 40 - 10 - 20 - 15 - 10 - 5 - 2 - 8)
