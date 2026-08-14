"""托管账户状态（规范 §42）。

E_S^A：卖方审计托管；E_B^A：买方审计托管；E_B^P：买方 purchase escrow；
B_S^pre：卖方预锁保证金；B_S^*：卖方责任保证金；B_B^use：买方 usage bond。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EscrowAccounts:
    """交易托管账户集合。"""

    e_s_a: float = 0.0  # 卖方审计托管
    e_b_a: float = 0.0  # 买方审计托管
    e_b_p: float = 0.0  # 买方 purchase escrow
    b_s_pre: float = 0.0  # 卖方预锁
    b_s_star: float = 0.0  # 卖方责任保证金
    b_b_use: float = 0.0  # 买方 usage bond

    def to_plain(self) -> dict:
        return {
            "E_S^A": self.e_s_a,
            "E_B^A": self.e_b_a,
            "E_B^P": self.e_b_p,
            "B_S^pre": self.b_s_pre,
            "B_S^*": self.b_s_star,
            "B_B^use": self.b_b_use,
        }
