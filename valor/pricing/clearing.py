"""贸易边际与结算价（规范 §41）。

    M_T = P_τ^max - P_τ^min
    M_T < 0 → NO_TRADE
    P_τ^* = P_τ^min + β_bar M_T
β_bar 是显式 contract input 或实验扫描变量，不在代码中赋默认值（§41）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeClearance:
    """结算结果。"""

    p_max: float
    p_min: float
    margin: float
    clearing_price: float | None
    decision: str  # TRADE | NO_TRADE

    def to_plain(self) -> dict:
        return {
            "p_max": self.p_max,
            "p_min": self.p_min,
            "margin": self.margin,
            "clearing_price": self.clearing_price,
            "decision": self.decision,
        }


def clear_trade(
    *,
    p_max: float,
    p_min: float,
    beta_bar: float,
) -> TradeClearance:
    """结算：NO_TRADE 或 P_τ^* = P_min + β_bar M_T（§41）。"""
    margin = p_max - p_min
    if margin < 0:
        return TradeClearance(p_max, p_min, margin, None, "NO_TRADE")
    if not (0.0 <= beta_bar <= 1.0):
        raise ValueError("β_bar 须在 [0,1]")
    price = p_min + beta_bar * margin
    return TradeClearance(p_max, p_min, margin, price, "TRADE")
