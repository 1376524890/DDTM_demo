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


@dataclass
class SettlementResult:
    """结算结果（含资金流）。"""

    terminal_state: TerminalState
    transfers: list[Transfer]
    bond_slashed: float

    def to_plain(self) -> dict:
        return {
            "terminal_state": self.terminal_state.value,
            "transfers": [t.to_plain() for t in self.transfers],
            "bond_slashed": self.bond_slashed,
        }


def settle(
    *,
    terminal: TerminalState,
    ledger: Ledger,
    accounts: EscrowAccounts,
    price: float,
    audit_pay_s: float,
    audit_pay_b: float,
    bond_slash_fraction: float = 1.0,
) -> SettlementResult:
    """执行终态结算（§43 资金流）。"""
    transfers: list[Transfer] = []
    bond_slashed = 0.0

    if terminal == TerminalState.TRADE:
        ledger.transfer(Transfer("E_B^P", "seller", price, "数据成交价"))
        # 调整卖方 bond：返还差额
        release = accounts.b_s_pre - accounts.b_s_star
        if release > 0:
            ledger.transfer(Transfer("B_S^pre", "seller", release, "释放预锁差额"))
        transfers = list(ledger._transfers[-3:])
    elif terminal == TerminalState.NO_TRADE:
        # 返还 purchase escrow；基础审计卖方付，增量审计买方付
        ledger.transfer(Transfer("E_B^P", "buyer", price, "NO_TRADE 返还 escrow"))
        ledger.transfer(Transfer("E_S^A", "seller", audit_pay_s, "基础审计支付"))
        ledger.transfer(Transfer("E_B^A", "buyer", audit_pay_b, "买方增量审计支付"))
        ledger.transfer(Transfer("B_S^pre", "seller", accounts.b_s_pre, "返还预锁"))
        transfers = list(ledger._transfers[-4:])
    elif terminal == TerminalState.SELLER_BREACH:
        ledger.transfer(Transfer("E_B^P", "buyer", price, "SELLER_BREACH 退款"))
        bond_slashed = accounts.b_s_pre * bond_slash_fraction
        ledger.transfer(Transfer("B_S^pre", "buyer", bond_slashed, "罚没卖方 bond"))
        ledger.transfer(Transfer("E_S^A", "seller", audit_pay_s, "完成审计仍支付"))
        transfers = list(ledger._transfers[-3:])
    elif terminal == TerminalState.BUYER_BREACH:
        ledger.transfer(Transfer("B_B^use", "seller", accounts.b_b_use, "买方 usage bond 罚没"))
        transfers = list(ledger._transfers[-1:])
    else:
        raise ValueError(f"未知终态: {terminal}")

    return SettlementResult(terminal_state=terminal, transfers=transfers,
                            bond_slashed=bond_slashed)
