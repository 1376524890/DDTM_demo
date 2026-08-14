"""强验证挑战采样（规范 §19）。

以概率 ρ 对节点证据发起强验证（重新执行比对）。ρ 必须解析来源，不存在全局默认。
"""

from __future__ import annotations

import numpy as np


def sample_challenge(
    evidence_ids: list[str],
    rho: float,
    *,
    rng: np.random.Generator,
) -> list[str]:
    """以概率 ρ 独立决定每个证据是否被挑战。

    rho 必须为已解析的 ResolvedParameter（禁止隐式默认挑战率）。
    """
    if not (0 <= rho <= 1):
        raise ValueError("ρ（挑战率）须在 [0,1]")
    return [eid for eid in evidence_ids if rng.random() < rho]
