"""权利注册表与活跃许可集合（规范 §32）。

活跃许可集合 L_D(t) = {R_k : Active(R_k, t) = 1}。
新权利授予前执行 Compatible(R_τ, L_D(t)) = 1（见 compatibility.py）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from valor.core.enums import RightsState
from valor.core.hashing import content_hash

from .models import RightsBundle, RightsStateRecord


@dataclass
class RightsRegistry:
    """权利注册表：登记某资产所有已授予/已存在的权利及状态。"""

    asset_id: str
    _records: dict[str, RightsStateRecord] = field(default_factory=dict)

    def register(self, rb: RightsBundle, state: RightsState = RightsState.ACTIVE) -> None:
        """登记一条权利束及其初始状态。"""
        rec = RightsStateRecord(
            rights_hash=rb.rights_hash,
            state=state,
        )
        self._records[rb.rights_hash] = rec

    def active(self) -> list[RightsBundle]:
        """返回当前活跃（ACTIVE 且未撤销）的权利束哈希集合。"""
        return [
            h for h, r in self._records.items()
            if r.state == RightsState.ACTIVE and not r.revoked
        ]

    def state_of(self, rights_hash: str) -> RightsStateRecord | None:
        return self._records.get(rights_hash)

    def to_plain(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "records": [r.to_plain() for r in self._records.values()],
        }
