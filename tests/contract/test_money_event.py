"""P8 MoneyLedger 语义化资金事件测试。"""

from __future__ import annotations

import pytest

from valor.contract.accounts import Ledger, Transfer
from valor.contract.escrow import EscrowAccounts
from valor.contract.money_event import MoneyLedger
from valor.contract.settlement import settle
from valor.core.enums import TerminalState


def test_no_trade_refunds_actual_escrow_not_price():
    """关键修复：NO_TRADE 退款用实际锁定 escrow，而非 price=0。"""
    ledger = Ledger({"buyer": 0.0, "seller": 0.0, "E_B^P": 300.0,
                     "E_S^A": 50.0, "E_B^A": 50.0, "B_S^pre": 100.0})
    accounts = EscrowAccounts(e_b_p=300.0, e_s_a=50.0, e_b_a=50.0,
                              b_s_pre=100.0, b_s_star=100.0)
    money = MoneyLedger(ledger, tx_id="tx-1")
    settle(terminal=TerminalState.NO_TRADE, ledger=ledger, accounts=accounts,
           price=0.0, audit_pay_s=10.0, audit_pay_b=5.0, money=money)
    # 买方收到全部 escrow 300（不是 0）
    assert ledger.balance("buyer") == pytest.approx(300.0 + 5.0)  # escrow + audit refund
    assert ledger.conservation_check()
    assert money.validate_semantics() == []


def test_money_event_semantics_valid():
    ledger = Ledger({"E_B^P": 300.0, "seller": 0.0, "B_S^pre": 100.0})
    accounts = EscrowAccounts(e_b_p=300.0, b_s_pre=100.0, b_s_star=80.0)
    money = MoneyLedger(ledger, tx_id="tx-1")
    settle(terminal=TerminalState.TRADE, ledger=ledger, accounts=accounts,
           price=200.0, audit_pay_s=0.0, audit_pay_b=0.0, money=money)
    assert money.validate_semantics() == []


def test_money_event_recipient_violation_detected():
    ledger = Ledger({"E_B^P": 300.0, "seller": 0.0})
    money = MoneyLedger(ledger, tx_id="tx-1")
    # 错误 recipient：应给 seller，却给 buyer
    money.transfer(Transfer("E_B^P", "buyer", 200.0, "数据成交价"))
    violations = money.validate_semantics()
    assert any("recipient 错误" in v for v in violations)


def test_money_ledger_serializable():
    ledger = Ledger({"E_B^P": 300.0, "seller": 0.0})
    money = MoneyLedger(ledger, tx_id="tx-1")
    money.transfer(Transfer("E_B^P", "seller", 200.0, "数据成交价"))
    p = money.to_plain()
    assert p["conservation"] is True
    assert p["events"][0]["from_account"] == "E_B^P"
    assert p["events"][0]["reason"] == "数据成交价"
