"""结果数据模型：类型化 dataclass + JSON 序列化。

设计原则：
- 所有结果对象实现 `to_plain()`，返回仅含 JSON 原生类型（dict/list/float/int/str/bool）
  的扁平结构，便于写入 `raw/*.json` 与日志。
- 与 config.py 中的参数 dataclass 区分：models.py 存"计算结果"，config.py 存"输入参数"。
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional


def to_plain(obj: Any) -> Any:
    """递归把 dataclass / dict / list / tuple 转换为 JSON 原生类型。

    支持：
    - dataclass（含 to_plain 方法或字段）
    - dict / list / tuple
    - 标量（int/float/str/bool/None）
    """
    if dataclasses.is_dataclass(obj):
        # 优先调用对象自身的 to_plain（可自定义字段裁剪），否则逐字段转换。
        if hasattr(obj, "to_plain") and callable(obj.to_plain):
            return obj.to_plain()
        return {
            f.name: to_plain(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
        }
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(x) for x in obj]
    if isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    # 兜底：转字符串（如 numpy 标量、enum 等）
    return str(obj)


@dataclasses.dataclass
class StateBelief:
    """三状态信念向量 π=(π_G, π_L, π_B)（机制文档 §5.1）。

    约束：π_G + π_L + π_B == 1（容差内）。
    """

    prob_g: float
    prob_l: float
    prob_b: float

    def __post_init__(self) -> None:
        total = self.prob_g + self.prob_l + self.prob_b
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"StateBelief 概率未归一化: sum={total}")
        for name, v in (
            ("prob_g", self.prob_g),
            ("prob_l", self.prob_l),
            ("prob_b", self.prob_b),
        ):
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"{name} 越界: {v}")

    def to_plain(self) -> Dict[str, float]:
        """返回 JSON 原生 dict。"""
        return {"prob_g": self.prob_g, "prob_l": self.prob_l, "prob_b": self.prob_b}


@dataclasses.dataclass
class AuditOutcome:
    """单次审计结果 Y_j ∈ {PASS, QUALITY_FAIL, BREACH_EVIDENCE}（机制文档 §5.2）。

    用字符串枚举表示，保持与机制文档一致。
    """

    outcome: str  # PASS | QUALITY_FAIL | BREACH_EVIDENCE
    # 审计动作标识（policy/m 等），用于回溯
    audit_action_id: Optional[str] = None

    def to_plain(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome,
            "audit_action_id": self.audit_action_id,
        }


@dataclasses.dataclass
class TerminalSettlement:
    """终态结算记录（机制文档 §12 资金流）。

    terminal_state ∈ {TRADE, NO_TRADE, SELLER_BREACH, BUYER_BREACH}
    """

    terminal_state: str
    # 资金流（单位 [CU]，D12）
    buyer_escrow_flow: float = 0.0
    seller_bond_flow: float = 0.0
    audit_escrow_flow: float = 0.0
    auditor_stake_flow: float = 0.0

    def to_plain(self) -> Dict[str, Any]:
        return {
            "terminal_state": self.terminal_state,
            "buyer_escrow_flow": self.buyer_escrow_flow,
            "seller_bond_flow": self.seller_bond_flow,
            "audit_escrow_flow": self.audit_escrow_flow,
            "auditor_stake_flow": self.auditor_stake_flow,
        }
