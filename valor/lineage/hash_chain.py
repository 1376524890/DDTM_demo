"""Lineage hash chain（规范 §33）。

    h_t = H(h_{t-1} ∥ Canonical(e_t))
检测日志删除、重排和篡改。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.hashing import stable_hash

from .models import DataFlowEvent


@dataclass
class HashChain:
    """事件哈希链。"""

    genesis: str = "genesis"
    _chain: list[str] = field(default_factory=list)

    def append(self, event: DataFlowEvent) -> str:
        prev = self._chain[-1] if self._chain else self.genesis
        h = stable_hash(prev, event.to_plain())
        self._chain.append(h)
        return h

    def last(self) -> str:
        return self._chain[-1] if self._chain else self.genesis

    def verify(self, events: list[DataFlowEvent]) -> bool:
        """重放事件序列，验证链一致（检测删除/重排/篡改）。"""
        prev = self.genesis
        for ev in events:
            h = stable_hash(prev, ev.to_plain())
            prev = h
        return prev == self.last()

    def to_plain(self) -> dict:
        return {"genesis": self.genesis, "chain": self._chain}
