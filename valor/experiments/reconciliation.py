"""Level 1 数学对账 —— 验证每个公式（code result == 独立重算）。

统一统计规范（交接文档第二十二节）：公式对账用独立重算比较，tolerance 内视为
PASS。本模块只做数学对账，不做交易执行；任何完整交易仍经过 orchestrator。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ReconciliationCase:
    """一个公式对账用例：code 计算 vs 独立重算。"""

    name: str
    compute: Callable[[], float]
    recompute: Callable[[], float]
    tolerance: float = 1e-9

    def run(self) -> dict:
        code = self.compute()
        indep = self.recompute()
        return {
            "name": self.name,
            "code": code, "independent": indep,
            "abs_diff": abs(code - indep),
            "passed": abs(code - indep) <= self.tolerance,
        }


def level1_reconciliation() -> list[dict]:
    """Level 1：核心公式独立重算对账。"""
    from valor.liability.seller_bond import reconcile_seller_bond, seller_bond_required
    from valor.pricing.buyer_max import buyer_max_price
    from valor.pricing.seller_min import seller_min_price

    cases = [
        ReconciliationCase(
            "seller_bond_B_star",
            lambda: seller_bond_required(p_breach_lower_sys=0.8, g_dev=60, eps_s=1,
                                         p_e_bond=1, p_e_f=0.3, lambda_s=0.5, f_s=10),
            lambda: max(0.0, ((60 + 1) / 0.8 - 0.3 * 10) / (1.0 * 0.5)),
        ),
        ReconciliationCase(
            "buyer_max_price",
            lambda: buyer_max_price(w_b_rem=500, v_gross_lower=300, c_i=20,
                                    c_a_b_pay=10, c_r_pay=5, c_b_use_cap=2, r_b_post=5),
            lambda: max(0.0, min(500, 300 - 20 - 10 - 5 - 2 - 5)),
        ),
        ReconciliationCase(
            "seller_min_price",
            lambda: seller_min_price(c_marg=5, c_a_s_pay=10, c_b_cap=15,
                                     c_r_s_pay=3, r_s_post=4, oc_s=6, pi_s0=10),
            lambda: 5 + 10 + 15 + 3 + 4 + 6 + 10,
        ),
        ReconciliationCase(
            "bond_IC_slack",
            lambda: reconcile_seller_bond(
                bond=seller_bond_required(p_breach_lower_sys=0.8, g_dev=60, eps_s=1,
                                          p_e_bond=1, p_e_f=0.3, lambda_s=0.5, f_s=10),
                p_breach_lower_sys=0.8, g_dev=60, eps_s=1, p_e_bond=1,
                p_e_f=0.3, lambda_s=0.5, f_s=10)["constraint_slack"],
            lambda: 0.8 * (1.0 * 0.5 * max(0.0, ((61) / 0.8 - 3) / 0.5) + 0.3 * 10) - 61,
            tolerance=1e-6,
        ),
    ]
    return [c.run() for c in cases]


__all__ = ["ReconciliationCase", "level1_reconciliation"]
