"""两阶段结算（规范 §43 / P0-O）。

废除"一次 settle() 解决整笔生命周期"的语义，保留 canonical
valor/contract/settlement.py，内部明确两个正式函数：

    settle_clearing(decision, ...)  —— Settlement Phase I
    settle_terminal(terminal, ...)  —— Settlement Phase II

Phase I（Clearing=TRADE 后、Delivery 前）：
    1. 支付已发生且有效的 audit payments
    2. 支付成交价 / 锁定 buyer usage bond / purchase escrow 保持锁定
    3. B_S^pre 调整到 B_S^*，prelock surplus 返还 seller
    4. 进入 Delivery

Delivery verified 后 Phase II（终态）：
    Normal completion：释放剩余 purchase 支付、seller bond 到期返还、
        buyer usage bond 到期返还
    SELLER_BREACH：buyer 退款、seller bond slash、补偿
    BUYER_BREACH：revoke rights、buyer usage bond slash、seller 补偿
    NO_TRADE：返还 escrow、返还 prelock

所有资金动作 double-entry MoneyLedger（§42 守恒）。
"""

from __future__ import annotations

from dataclasses import dataclass

from valor.core.enums import TerminalState

from .accounts import Ledger, Transfer
from .escrow import EscrowAccounts
from .money_event import MoneyLedger


@dataclass
class SettlementResult:
    """结算结果（含资金流）。"""

    terminal_state: TerminalState
    transfers: list[Transfer]
    bond_slashed: float
    money: "MoneyLedger | None" = None

    def to_plain(self) -> dict:
        d: dict = {
            "terminal_state": self.terminal_state.value,
            "transfers": [t.to_plain() for t in self.transfers],
            "bond_slashed": self.bond_slashed,
        }
        if self.money is not None:
            d["money"] = self.money.to_plain()
        return d


def _pay_audit(money, accounts, audit_pay_s, audit_pay_b) -> None:
    """支付已发生且有效的审计（seller 基础 / buyer 增量）。"""
    if accounts.e_s_a > 0 and audit_pay_s > 0:
        money.transfer(Transfer("E_S^A", "auditor", audit_pay_s,
                                "基础审计支付给审计员"))
    if accounts.e_b_a > 0 and audit_pay_b > 0:
        money.transfer(Transfer("E_B^A", "auditor", audit_pay_b,
                                "增量审计支付给审计员"))


def _refund_audit_escrow_remainder(money) -> None:
    e_s_bal = money.ledger.balance("E_S^A")
    if e_s_bal > 1e-9:
        money.transfer(Transfer("E_S^A", "seller", e_s_bal, "审计托管余量返还"))
    e_b_bal = money.ledger.balance("E_B^A")
    if e_b_bal > 1e-9:
        money.transfer(Transfer("E_B^A", "buyer", e_b_bal, "审计托管余量返还B"))


def settle_clearing(
    *,
    decision: str,  # TRADE | NO_TRADE
    ledger: Ledger,
    accounts: EscrowAccounts,
    audit_pay_s: float,
    audit_pay_b: float,
    money: "MoneyLedger | None" = None,
    tx_id: str = "",
) -> dict:
    """P0-O Settlement Phase I（Clearing 后、Delivery 前）。

    支付有效审计；TRADE 时把 B_S^pre 调整为 B_S^*（surplus 返还 seller），
    purchase escrow 保持锁定，buyer usage bond 锁定，进入 Delivery。
    """
    money = money or MoneyLedger(ledger, tx_id=tx_id)
    transfers: list[Transfer] = []

    def _t(frm, to, amt, reason):
        transfers.append(money.transfer(Transfer(frm, to, amt, reason)))

    _pay_audit(money, accounts, audit_pay_s, audit_pay_b)
    transfers = list(money.ledger._transfers)
    if decision == "TRADE":
        if accounts.b_s_star > 0:
            _t("B_S^pre", "B_S^*", accounts.b_s_star, "预锁转入责任保证金")
        release = accounts.b_s_pre - accounts.b_s_star
        if release > 0:
            _t("B_S^pre", "seller", release, "释放预锁差额")
    return {"phase": "CLEARING", "decision": decision,
            "transfers": [t.to_plain() for t in transfers]}


def settle_terminal(
    *,
    terminal: TerminalState,
    ledger: Ledger,
    accounts: EscrowAccounts,
    price: float,
    audit_pay_s: float,
    audit_pay_b: float,
    bond_slash_fraction: float = 1.0,
    money: "MoneyLedger | None" = None,
    tx_id: str = "",
) -> SettlementResult:
    """P0-O Settlement Phase II（Delivery verified / 终态资金流）。"""
    money = money or MoneyLedger(ledger, tx_id=tx_id)
    transfers: list[Transfer] = []
    bond_slashed = 0.0

    def _t(frm, to, amt, reason):
        transfers.append(money.transfer(Transfer(frm, to, amt, reason)))

    if terminal == TerminalState.TRADE:
        _t("E_B^P", "seller", price, "数据成交价")
        if accounts.e_b_p - price > 1e-9:
            _t("E_B^P", "buyer", accounts.e_b_p - price, "purchase escrow 余量返还")
        # audit 已在 Phase I（settle_clearing）支付，此处不重复支付
        _refund_audit_escrow_remainder(money)
        if money.ledger.balance("B_S^*") > 1e-9:
            _t("B_S^*", "seller", money.ledger.balance("B_S^*"), "bond 到期返还")
        if accounts.b_b_use > 0 and money.ledger.balance("B_B^use") > 1e-9:
            _t("B_B^use", "buyer", money.ledger.balance("B_B^use"),
               "usage bond 到期返还")
    elif terminal == TerminalState.NO_TRADE:
        _t("E_B^P", "buyer", accounts.e_b_p, "NO_TRADE 返还 escrow")
        _pay_audit(money, accounts, audit_pay_s, audit_pay_b)
        _refund_audit_escrow_remainder(money)
        if accounts.b_s_pre > 0:
            _t("B_S^pre", "seller", accounts.b_s_pre, "返还预锁")
    elif terminal == TerminalState.SELLER_BREACH:
        _t("E_B^P", "buyer", accounts.e_b_p, "SELLER_BREACH 退款")
        bond_slashed = accounts.b_s_pre * bond_slash_fraction
        _t("B_S^pre", "buyer", bond_slashed, "罚没卖方 bond")
        if accounts.b_s_pre - bond_slashed > 1e-9:
            _t("B_S^pre", "seller", accounts.b_s_pre - bond_slashed, "预锁剩余返还")
        _pay_audit(money, accounts, audit_pay_s, audit_pay_b)
        _refund_audit_escrow_remainder(money)
        if money.ledger.balance("B_S^*") > 1e-9:
            _t("B_S^*", "buyer", money.ledger.balance("B_S^*"), "责任保证金罚没")
    elif terminal == TerminalState.BUYER_BREACH:
        _t("E_B^P", "seller", price, "数据成交价")
        if accounts.e_b_p - price > 1e-9:
            _t("E_B^P", "buyer", accounts.e_b_p - price, "purchase escrow 余量返还")
        _t("B_B^use", "seller", accounts.b_b_use, "买方 usage bond 罚没")
        _pay_audit(money, accounts, audit_pay_s, audit_pay_b)
        _refund_audit_escrow_remainder(money)
        if accounts.b_s_pre > 0:
            _t("B_S^pre", "seller", accounts.b_s_pre, "返还预锁")
        if money.ledger.balance("B_S^*") > 1e-9:
            _t("B_S^*", "seller", money.ledger.balance("B_S^*"), "bond 到期返还")
    else:
        raise ValueError(f"未知终态: {terminal}")

    return SettlementResult(terminal_state=terminal, transfers=transfers,
                            bond_slashed=bond_slashed, money=money)


def settle(
    *,
    terminal: TerminalState,
    ledger: Ledger,
    accounts: EscrowAccounts,
    price: float,
    audit_pay_s: float,
    audit_pay_b: float,
    bond_slash_fraction: float = 1.0,
    money: "MoneyLedger | None" = None,
    tx_id: str = "",
) -> SettlementResult:
    """执行终态结算（§43 资金流）。

    TRADE：先 settle_clearing（Phase I 预锁调整 + audit 支付），再 settle_terminal
    （Phase II 成交/返还）。其余终态直接 Phase II。
    """
    money = money or MoneyLedger(ledger, tx_id=tx_id)
    if terminal == TerminalState.TRADE:
        settle_clearing(
            decision="TRADE", ledger=ledger, accounts=accounts,
            audit_pay_s=audit_pay_s, audit_pay_b=audit_pay_b,
            money=money, tx_id=tx_id)
    return settle_terminal(
        terminal=terminal, ledger=ledger, accounts=accounts, price=price,
        audit_pay_s=audit_pay_s, audit_pay_b=audit_pay_b,
        bond_slash_fraction=bond_slash_fraction, money=money, tx_id=tx_id)


__all__ = [
    "SettlementResult", "settle", "settle_clearing", "settle_terminal",
]
