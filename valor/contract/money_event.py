"""MoneyEvent / MoneyLedger —— 资金事件账本（P8）。

对接交文档第十三节：不能只测 Σbalance 守恒，要保存每个资金事件的
    seq / from_account / to_account / amount / reason / tx_id /
    audit_action_id / evidence_hash
并强制语义正确：每个 debit 有合法触发、每个 recipient 正确、所有 escrow 关闭。

与 accounts.Ledger（double-entry 数值守恒）配合：
- Ledger 负责数值守恒
- MoneyEventLedger 记录语义化事件链，供 FullChainGate G22/G23 校验
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .accounts import Ledger, Transfer
from .escrow import EscrowAccounts


@dataclass
class MoneyEvent:
    """一笔语义化资金事件。"""

    seq: int
    from_account: str
    to_account: str
    amount: float
    reason: str
    tx_id: str = ""
    audit_action_id: str = ""
    evidence_hash: str = ""

    def to_plain(self) -> dict:
        return {
            "seq": self.seq,
            "from_account": self.from_account,
            "to_account": self.to_account,
            "amount": self.amount,
            "reason": self.reason,
            "tx_id": self.tx_id,
            "audit_action_id": self.audit_action_id,
            "evidence_hash": self.evidence_hash,
        }


# 合法资金流触发（payer→recipient 语义白名单）
#   reason 是唯一触发标识；每个 debit 必须命中白名单
_LEGAL_FLOWS = {
    "数据成交价": ("E_B^P", "seller"),
    "释放预锁差额": ("B_S^pre", "seller"),
    "NO_TRADE 返还 escrow": ("E_B^P", "buyer"),
    "基础审计支付": ("E_S^A", "seller"),
    "买方增量审计支付": ("E_B^A", "buyer"),
    "返还预锁": ("B_S^pre", "seller"),
    "SELLER_BREACH 退款": ("E_B^P", "buyer"),
    "罚没卖方 bond": ("B_S^pre", "buyer"),
    "完成审计仍支付": ("E_S^A", "seller"),
    "买方 usage bond 罚没": ("B_B^use", "seller"),
    "审计支付给审计员": ("E_B^A", "auditor"),
    "审计支付给审计员S": ("E_S^A", "auditor"),
    # V2：escrow 全关闭新增
    "基础审计支付给审计员": ("E_S^A", "auditor"),
    "增量审计支付给审计员": ("E_B^A", "auditor"),
    "审计托管余量返还": ("E_S^A", "seller"),
    "审计托管余量返还B": ("E_B^A", "buyer"),
    "bond 到期返还": ("B_S^*", "seller"),
    "返还责任保证金": ("B_S^*", "seller"),
    "预锁剩余返还": ("B_S^pre", "seller"),
    "责任保证金罚没": ("B_S^*", "buyer"),
    "purchase escrow 余量返还": ("E_B^P", "buyer"),
    "预锁转入责任保证金": ("B_S^pre", "B_S^*"),
}


class MoneyLedger:
    """语义化资金事件账本（与数值 Ledger 配合）。"""

    def __init__(self, ledger: Ledger | None = None, *, tx_id: str = "") -> None:
        self.ledger = ledger or Ledger()
        self.tx_id = tx_id
        self._events: list[MoneyEvent] = []

    def transfer(self, t: Transfer, *, audit_action_id: str = "",
                 evidence_hash: str = "") -> MoneyEvent:
        """执行数值转移 + 记录语义化事件。"""
        self.ledger.transfer(t)
        ev = MoneyEvent(
            seq=len(self._events) + 1, from_account=t.from_account,
            to_account=t.to_account, amount=t.amount, reason=t.reason,
            tx_id=self.tx_id, audit_action_id=audit_action_id,
            evidence_hash=evidence_hash,
        )
        self._events.append(ev)
        return ev

    @property
    def events(self) -> list[MoneyEvent]:
        return list(self._events)

    def validate_semantics(self) -> list[str]:
        """校验每个 debit 命中合法资金流白名单。返回违规列表（空=全部合法）。"""
        violations = []
        for ev in self._events:
            expected = _LEGAL_FLOWS.get(ev.reason)
            if expected is None:
                violations.append(f"seq{ev.seq}: 未知 reason {ev.reason!r}")
                continue
            from_acc, to_acc = expected
            if ev.from_account != from_acc:
                violations.append(
                    f"seq{ev.seq}: payer 错误 {ev.from_account}（应 {from_acc}）")
            if ev.to_account != to_acc:
                violations.append(
                    f"seq{ev.seq}: recipient 错误 {ev.to_account}（应 {to_acc}）")
        return violations

    def all_escrows_closed(self, accounts: EscrowAccounts) -> bool:
        """校验所有托管账户余额归零（全部关闭）。"""
        return all(abs(v) < 1e-9 for v in [
            accounts.e_s_a, accounts.e_b_a, accounts.e_b_p,
            accounts.b_s_pre, accounts.b_s_star, accounts.b_b_use,
        ])

    def to_plain(self) -> dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "conservation": self.ledger.conservation_check(),
            "events": [e.to_plain() for e in self._events],
        }


__all__ = ["MoneyEvent", "MoneyLedger", "_LEGAL_FLOWS"]
