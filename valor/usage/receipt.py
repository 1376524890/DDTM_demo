"""UsageReceipt（规范 §37）。

receipt 必须可 canonicalize、hash 和签名。decision=DENY 的请求也生成审计事件。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class UsageReceipt:
    """一次使用/拒绝的使用凭证（§37 字段子集）。"""

    receipt_id: str
    tx_id: str
    rights_hash: str
    asset_version_hash: str
    buyer_id: str
    requested_action: str
    declared_purpose: str
    usage_count_before: int
    usage_count_after: int
    decision: str  # ALLOW | DENY
    timestamp: str
    prev_event_hash: str

    def _plain_fields(self) -> dict:
        """不含 receipt_hash 的字段（供 hash 计算，避免递归）。"""
        return {
            "receipt_id": self.receipt_id,
            "tx_id": self.tx_id,
            "rights_hash": self.rights_hash,
            "asset_version_hash": self.asset_version_hash,
            "buyer_id": self.buyer_id,
            "requested_action": self.requested_action,
            "declared_purpose": self.declared_purpose,
            "usage_count_before": self.usage_count_before,
            "usage_count_after": self.usage_count_after,
            "decision": self.decision,
            "timestamp": self.timestamp,
            "prev_event_hash": self.prev_event_hash,
        }

    def receipt_hash(self) -> str:
        return content_hash(self._plain_fields())

    def to_plain(self) -> dict:
        d = self._plain_fields()
        d["receipt_hash"] = self.receipt_hash()
        return d
