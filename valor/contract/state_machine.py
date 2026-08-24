"""交易状态机（规范 §43 / Phase 7）。

终态 S_T ∈ {TRADE, NO_TRADE, SELLER_BREACH, BUYER_BREACH}。TRADE 并不表示权利
生命周期结束；持续 RightsState 独立维护（ACTIVE/SUSPENDED/EXPIRED/REVOKED/
CONSUMED/DELETION_PENDING/DELETED_ATTESTED）。
"""

from __future__ import annotations

from dataclasses import dataclass

from valor.core.enums import RightsState, TerminalState


@dataclass(frozen=True)
class StateMachineInput:
    """状态机输入（各阶段判定结果）。"""

    entitled: bool
    compliant: bool
    breach_during_audit: bool
    price_decision: str  # TRADE | NO_TRADE
    buyer_breach: bool
    audit_ok: bool = True


class TransactionStateMachine:
    """交易状态机：根据判定结果确定终态与权利状态。"""

    def resolve(self, inp: StateMachineInput) -> TerminalState:
        """确定交易终态（§43 判定优先级）。"""
        if not inp.entitled or not inp.compliant:
            return TerminalState.NO_TRADE  # 硬门槛失败 → 不进入交易
        if not inp.audit_ok:
            return TerminalState.NO_TRADE  # 强制审计未成功 → fail closed
        if inp.buyer_breach:
            return TerminalState.BUYER_BREACH
        if inp.breach_during_audit:
            return TerminalState.SELLER_BREACH
        if inp.price_decision == "NO_TRADE":
            return TerminalState.NO_TRADE
        return TerminalState.TRADE

    def rights_transition(self, terminal: TerminalState) -> RightsState:
        """终态对应的权利状态（§43/§63）。"""
        if terminal == TerminalState.TRADE:
            return RightsState.ACTIVE
        if terminal == TerminalState.BUYER_BREACH:
            return RightsState.REVOKED
        if terminal in (TerminalState.NO_TRADE, TerminalState.SELLER_BREACH):
            return RightsState.SUSPENDED
        return RightsState.SUSPENDED
