"""三状态先验（规范 §23）。

卖方 breach posterior：θ_S ~ Beta(a_S, b_S)，π_B = E[θ_S]。
利用交易前可见 metadata/context 建立 suitability prior q_L = P(L | X≠B, C_b, PreTrade)。
    π_L = (1-π_B) q_L，π_G = (1-π_B)(1-q_L)。
禁止使用 realised utility 生成当前 q_L（§23）。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StateBelief:
    """三状态信念 π = (π_G, π_L, π_B)，归一化。"""

    prob_g: float
    prob_l: float
    prob_b: float

    def __post_init__(self) -> None:
        total = self.prob_g + self.prob_l + self.prob_b
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"StateBelief 未归一化: sum={total}")
        for name, v in (("prob_g", self.prob_g), ("prob_l", self.prob_l),
                        ("prob_b", self.prob_b)):
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"{name} 越界: {v}")

    @classmethod
    def from_prior(cls, pi_b: float, q_l: float) -> "StateBelief":
        """由 §23 公式构造：π_G、π_L、π_B。"""
        if not (0 <= pi_b <= 1) or not (0 <= q_l <= 1):
            raise ValueError("π_B、q_L 须在 [0,1]")
        return cls(
            prob_g=(1 - pi_b) * (1 - q_l),
            prob_l=(1 - pi_b) * q_l,
            prob_b=pi_b,
        )

    def to_plain(self) -> dict:
        return {"prob_g": self.prob_g, "prob_l": self.prob_l, "prob_b": self.prob_b}
