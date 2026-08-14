"""竞争外部性（规范 §26）。

ν_{b,t} = Exposure(D, R_τ, b, t) 为当前 buyer-relevant market exposure；
L_b^comp = L^comp(ν_{b,t}, R_τ, C_b) 为竞争外部性损失。
允许 L_b^comp = 0（无竞争稀释时），不得强制"销售次数越多价值越低"（§26）。
"""

from __future__ import annotations


def competition_externality(
    *,
    exposure: float,  # ν_{b,t}，市场暴露程度（协议观测）
    exclusivity: bool,  # 该权利是否排他
    sensitivity: float = 1.0,  # 竞争敏感系数（校准/合同输入）
) -> float:
    """竞争外部性损失 L_b^comp [CU]。

    排他授权可视为消除竞争稀释 → 暴露损失为 0；非排他且暴露高时损失增大。
    """
    if not exclusivity:
        return sensitivity * max(exposure, 0.0)
    return 0.0
