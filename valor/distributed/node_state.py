"""审计节点状态（规范 §18/§19）。

capability、availability、stake 和历史 reliability 均由协议观测或认证得到，
不由节点自行声明（§18）。节点唯一允许战略报告的 private type 是 b_i。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.enums import ParamSource
from valor.core.hashing import content_hash
from valor.core.ids import AuditorID


@dataclass(frozen=True)
class AuditorNode:
    """一个审计节点 A_i（协议观测到的状态）。"""

    node_id: AuditorID
    capability: tuple[str, ...]  # 可执行的 primitive family
    availability: float  # 在线概率（协议观测）
    stake: float  # 质押 B_{A,i} [CU]
    reliability: float = 1.0  # 历史可靠度（协议认证）
    private_cost: float = 0.0  # 私人成本 k_i [CU]（节点私有，bid 时上报）

    def to_plain(self) -> dict:
        return {
            "node_id": str(self.node_id),
            "capability": list(self.capability),
            "availability": self.availability,
            "stake": self.stake,
            "reliability": self.reliability,
        }


class NodeRegistry:
    """节点注册表（协议观测状态）。"""

    def __init__(self) -> None:
        self._nodes: dict[AuditorID, AuditorNode] = {}

    def register(self, node: AuditorNode) -> None:
        self._nodes[node.node_id] = node

    def get(self, node_id: AuditorID) -> AuditorNode:
        return self._nodes[node_id]

    def capable(self, family: str) -> list[AuditorNode]:
        return [
            n for n in self._nodes.values()
            if family in n.capability and n.availability > 0
        ]

    def all(self) -> list[AuditorNode]:
        return list(self._nodes.values())

    def to_plain(self) -> dict:
        return {str(k): v.to_plain() for k, v in self._nodes.items()}
