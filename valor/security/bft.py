"""BFT Safety 与 Offline Liveness（规范 §20）。

certified profile 中给定 Byzantine tolerance f：
    m = 3f+1,  q = 2f+1
IID 大池近似：K_B ~ Binomial(m, η_B)，P_safe = P(K_B ≤ f)。
在线诚实概率 p_H = (1-η_B)(1-η_O)，P_live = P(K_H ≥ q)。
有限池使用 hypergeometric；correlated outage/collusion 单独 simulator 评价。
"""

from __future__ import annotations

import math
from scipy.stats import binom, hypergeom


def bft_committee_size(f: int) -> tuple[int, int]:
    """m=3f+1, q=2f+1（§20）。"""
    if f < 0:
        raise ValueError("f（Byzantine 容错）不能为负")
    return 3 * f + 1, 2 * f + 1


def p_safe_binomial(m: int, f: int, eta_b: float) -> float:
    """P_safe = P(K_B ≤ f)，K_B ~ Binomial(m, η_B)（IID 大池近似）。"""
    if not (0 <= eta_b <= 1):
        raise ValueError("η_B（Byzantine 比例）须在 [0,1]")
    return float(binom.cdf(f, m, eta_b))


def p_live_binomial(m: int, q: int, eta_b: float, eta_o: float) -> float:
    """P_live = P(K_H ≥ q)，K_H ~ Binomial(m, p_H)，p_H=(1-η_B)(1-η_O)。"""
    p_h = (1 - eta_b) * (1 - eta_o)
    if not (0 <= p_h <= 1):
        raise ValueError("p_H 越界")
    return float(1.0 - binom.cdf(q - 1, m, p_h))


def p_safe_hypergeometric(total: int, byzantine: int, m: int, f: int) -> float:
    """有限池 P_safe：从含 byzantine 个坏节点的池中抽 m，坏节点 ≤ f。"""
    return float(
        hypergeom.cdf(f, total, byzantine, m)
    )


def p_live_hypergeometric(total: int, honest: int, m: int, q: int) -> float:
    """有限池 P_live：抽 m 中诚实节点 ≥ q。"""
    return float(1.0 - hypergeom.cdf(q - 1, total, honest, m))
