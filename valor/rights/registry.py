"""权利注册表与活跃许可集合（规范 §32）。

活跃许可集合 L_D(t) = {R_k : Active(R_k, t) = 1}。
新权利授予前执行 Compatible(R_τ, L_D(t)) = 1（见 compatibility.py）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from valor.core.enums import RightsState
from valor.core.hashing import content_hash

from .models import RightsBundle, RightsStateRecord


@dataclass
class RightsGrantRecord:
    """一条已登记权利束的完整授权记录（规范 §32 / P0-P）。

    保存完整 RightsBundle（供 compatibility check 使用），而非只存 hash。
    """

    rights: RightsBundle
    tx_id: str = ""
    buyer_id: str = ""
    asset_id: str = ""
    state: RightsState = RightsState.ACTIVE
    granted_at: str = ""
    expires_at: str = ""

    def __post_init__(self) -> None:
        if not self.granted_at:
            self.granted_at = datetime.now(timezone.utc).isoformat()
        if not self.expires_at:
            self.expires_at = self.rights.t1

    @property
    def rights_hash(self) -> str:
        return self.rights.rights_hash

    def is_active(self) -> bool:
        return self.state == RightsState.ACTIVE and not self.rights.revoked

    def to_plain(self) -> dict:
        return {
            "rights_hash": self.rights_hash,
            "rights": self.rights.to_plain(),
            "tx_id": self.tx_id, "buyer_id": self.buyer_id,
            "asset_id": self.asset_id, "state": self.state.value,
            "granted_at": self.granted_at, "expires_at": self.expires_at,
        }


@dataclass
class RightsRegistry:
    """权利注册表：登记某资产所有已授予/已存在的权利及状态（规范 §32）。

    active() 返回真实 RightsBundle 列表（供 compatibility check / opportunity
    cost / 重复出售约束使用），禁止只返回 hash 却标注为 RightsBundle。
    """

    asset_id: str
    _records: dict[str, RightsGrantRecord] = field(default_factory=dict)

    def register(
        self, rb: RightsBundle, state: RightsState = RightsState.ACTIVE,
        *, tx_id: str = "", buyer_id: str = "", granted_at: str = "",
    ) -> None:
        """登记一条权利束及其初始状态（保存完整 RightsBundle）。"""
        self._records[rb.rights_hash] = RightsGrantRecord(
            rights=rb, tx_id=tx_id, buyer_id=buyer_id, asset_id=self.asset_id,
            state=state, granted_at=granted_at,
        )

    def active(self) -> list[RightsBundle]:
        """返回当前活跃（ACTIVE 且未撤销）的权利束列表（真实 RightsBundle）。"""
        return [
            r.rights for r in self._records.values() if r.is_active()
        ]

    def active_records(self) -> list[RightsGrantRecord]:
        return [r for r in self._records.values() if r.is_active()]

    def state_of(self, rights_hash: str) -> RightsGrantRecord | None:
        return self._records.get(rights_hash)

    def update_state(self, rights_hash: str, state: RightsState) -> None:
        if rights_hash in self._records:
            self._records[rights_hash].state = state

    def revoke(self, rights_hash: str) -> None:
        if rights_hash in self._records:
            self._records[rights_hash].state = RightsState.REVOKED

    def to_plain(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "records": [r.to_plain() for r in self._records.values()],
        }
