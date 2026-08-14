"""资金账户与 double-entry ledger（规范 §42）。

账户至少包括：E_S^A, E_B^A, E_B^P, B_S^pre, B_S^*, B_B^use, {B_{A,i}}。
每个资金动作记 double-entry：from_account, to_account, amount, currency_unit,
reason, state_before, state_after。
每个 transaction 必须满足 ΣInflow - ΣOutflow = 0（除非显式 burn/deadweight）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.errors import VALORError
from valor.core.money import CURRENCY_UNIT


class LedgerError(VALORError):
    code = "LEDGER"


@dataclass(frozen=True)
class Transfer:
    """一笔资金转移。"""

    from_account: str
    to_account: str
    amount: float
    reason: str
    currency_unit: str = CURRENCY_UNIT

    def to_plain(self) -> dict:
        return {
            "from_account": self.from_account,
            "to_account": self.to_account,
            "amount": self.amount,
            "reason": self.reason,
            "currency_unit": self.currency_unit,
        }


class Ledger:
    """double-entry ledger（资金守恒强制）。"""

    def __init__(self, accounts: dict[str, float] | None = None) -> None:
        self._accounts: dict[str, float] = dict(accounts or {})
        self._transfers: list[Transfer] = []
        self._initial_total: float = sum(self._accounts.values())

    def create_account(self, name: str, initial: float = 0.0) -> None:
        if name not in self._accounts:
            self._accounts[name] = initial
            self._initial_total += initial

    def transfer(self, t: Transfer) -> None:
        if t.amount < 0:
            raise LedgerError("转账金额不能为负")
        if t.from_account not in self._accounts:
            self._accounts[t.from_account] = 0.0
        if t.to_account not in self._accounts:
            self._accounts[t.to_account] = 0.0
        if self._accounts[t.from_account] < t.amount:
            raise LedgerError(
                f"{t.from_account} 余额不足: 需 {t.amount}，有 "
                f"{self._accounts[t.from_account]}"
            )
        self._accounts[t.from_account] -= t.amount
        self._accounts[t.to_account] += t.amount
        self._transfers.append(t)

    def balance(self, name: str) -> float:
        return self._accounts.get(name, 0.0)

    def conservation_check(self) -> bool:
        """Σ 各账户余额守恒：当前总余额 = 初始注入总和（无价值创造/泄漏）。

        对应 §42「ΣInflow - ΣOutflow = 0」（除非显式 burn/deadweight 账户）。
        """
        total = sum(self._accounts.values())
        return abs(total - self._initial_total) < 1e-9

    def to_plain(self) -> dict:
        return {
            "accounts": self._accounts,
            "transfers": [t.to_plain() for t in self._transfers],
        }
