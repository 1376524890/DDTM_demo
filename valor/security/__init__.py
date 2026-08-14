"""节点安全（规范 §19–§20）。

- bft:       BFT Safety / Offline Liveness（m=3f+1, q=2f+1, P_safe/P_live）
- liveness:  离线重指派（offline reassignment）
- challenge: 强验证挑战采样（ρ）
- slashing:  ProvableMalice 罚没与最低 stake B_{A,i}^min
"""

from .bft import (
    bft_committee_size,
    p_live_binomial,
    p_live_hypergeometric,
    p_safe_binomial,
    p_safe_hypergeometric,
)
from .challenge import sample_challenge
from .slashing import minimum_auditor_stake

__all__ = [
    "bft_committee_size",
    "p_live_binomial",
    "p_live_hypergeometric",
    "p_safe_binomial",
    "p_safe_hypergeometric",
    "sample_challenge",
    "minimum_auditor_stake",
]
