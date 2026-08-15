"""结算（规范 §43）。

按终态执行结算资金流：
- TRADE：支付成交价，支付有效审计，调整/返还卖方 bond，激活 RightsBundle
- NO_TRADE：不支付数据价；返还 purchase escrow；已发生基础审计由卖方托管支付，
  买方增量审计由买方托管支付；无违约时 seller bond 返还
- SELLER_BREACH：停止数据价结算，买方 purchase escrow 退款，卖方 bond 罚没，
  正确完成的审计仍支付
- BUYER_BREACH：执行取消成本、usage bond、补偿、rights revocation
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
    """执行终态结算（§43 资金流，P8 语义正确）。

    关键修复：退款/返还必须用**实际锁定的 escrow 余额**（accounts.e_b_p 等），
    而不是 price（NO_TRADE 时 price=0，用 price 会少退）。所有资金动作用
    MoneyLedger 记录语义化事件（payer/recipient/trigger），供 G22/G23 校验。
    """
    money = money or MoneyLedger(ledger, tx_id=tx_id)

    def _t(frm, to, amt, reason):
        return money.transfer(Transfer(frm, to, amt, reason))

    transfers: list[Transfer] = list(money.ledger._transfers)
    bond_slashed = 0.0

    if terminal == TerminalState.TRADE:
        _t("E_B^P", "seller", price, "数据成交价")
        release = accounts.b_s_pre - accounts.b_s_star
        if release > 0:
            _t("B_S^pre", "seller", release, "释放预锁差额")
    elif terminal == TerminalState.NO_TRADE:
        # 返还实际锁定的 purchase escrow（非 price）；审计按 payer 语义支付
        _t("E_B^P", "buyer", accounts.e_b_p, "NO_TRADE 返还 escrow")
        if audit_pay_s > 0:
            _t("E_S^A", "seller", audit_pay_s, "基础审计支付")
        if audit_pay_b > 0:
            _t("E_B^A", "buyer", audit_pay_b, "买方增量审计支付")
        if accounts.b_s_pre > 0:
            _t("B_S^pre", "seller", accounts.b_s_pre, "返还预锁")
    elif terminal == TerminalState.SELLER_BREACH:
        _t("E_B^P", "buyer", accounts.e_b_p, "SELLER_BREACH 退款")
        bond_slashed = accounts.b_s_pre * bond_slash_fraction
        _t("B_S^pre", "buyer", bond_slashed, "罚没卖方 bond")
        if audit_pay_s > 0:
            _t("E_S^A", "seller", audit_pay_s, "完成审计仍支付")
    elif terminal == TerminalState.BUYER_BREACH:
        _t("B_B^use", "seller", accounts.b_b_use, "买方 usage bond 罚没")
    else:
        raise ValueError(f"未知终态: {terminal}")

    transfers = list(money.ledger._transfers)
    return SettlementResult(terminal_state=terminal, transfers=transfers,
                            bond_slashed=bond_slashed,
                            money=money)
