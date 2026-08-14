"""卖方未来许可机会成本（规范 §29 OC_S(R_τ)）。

OC_S(R_τ) = E[Rev^{future} | L_D] - E[Rev^{future} | L_D ∪ {R_τ}]

非排他授权可使 OC_S 很小；独占或 capped license 可因放弃未来出售机会
产生显著 OC_S。Phase 0 定义接口与基础实现；精确期望依赖 Phase 5 定价。
"""

from __future__ import annotations

from dataclasses import dataclass

from valor.core.money import CURRENCY_UNIT


@dataclass(frozen=True)
class OpportunityCost:
    """卖方机会成本评估结果（单位 [CU]）。

    oc_amount:  OC_S(R_τ) 金额
    unit:       货币单位（CU）
    note:       计算说明/来源
    """

    oc_amount: float
    unit: str = CURRENCY_UNIT
    note: str = ""

    def to_plain(self) -> dict:
        return {"oc_amount": self.oc_amount, "unit": self.unit, "note": self.note}


def compute_opportunity_cost(
    *,
    exclusivity: bool,
    rev_future_without: float,
    rev_future_with: float,
) -> OpportunityCost:
    """基础机会成本计算（规范 §29）。

    Args:
        exclusivity:       新授权是否排他
        rev_future_without: 不授予该权利时未来期望收益（[CU]）
        rev_future_with:    授予该权利后未来期望收益（[CU]）

    非排他授权通常使 OC_S 很小（此处由调用方给定 rev_future_with 接近 without）。
    """
    oc = rev_future_without - rev_future_with
    note = (
        "排他授权机会成本" if exclusivity else "非排他授权机会成本"
    )
    return OpportunityCost(oc_amount=max(0.0, oc), note=note)
