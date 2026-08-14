"""Data Flow 事件与图（规范 §33）。

事件 e_t = (eventID, txID, actor, action, inputRefs, outputRefs, rightsRef,
purpose, time, env, evidence)。节点类型与边类型见 §33。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class DataFlowEvent:
    """一个数据流向事件（§33）。"""

    event_id: str
    tx_id: str
    actor: str
    action: str  # READ|WRITE|DERIVE|TRANSFER|COMPUTE_ON|AUDIT|EXPORT|DELETE|REVOKE
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    rights_ref: str
    purpose: str
    time: str
    env: str
    evidence: str

    def event_hash(self) -> str:
        return content_hash(self.to_plain())

    def to_plain(self) -> dict:
        return {
            "event_id": self.event_id,
            "tx_id": self.tx_id,
            "actor": self.actor,
            "action": self.action,
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
            "rights_ref": self.rights_ref,
            "purpose": self.purpose,
            "time": self.time,
            "env": self.env,
            "evidence": self.evidence,
        }
