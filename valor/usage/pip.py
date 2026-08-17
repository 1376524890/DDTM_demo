"""PIP —— Policy Information Point（规范 §35）。

为 PDP 提供当前时间、身份、权利状态、使用次数、环境、隐私预算、保留状态、
撤销与执行 attestation 等信息。PIP 只收集状态，不做授权决策。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import UsageState


@dataclass
class PolicyInformation:
    """PDP 判定所需的全部策略信息（P0-N）。"""

    current_time: str
    actor: str
    purpose: str
    environment: str
    rights_hash: str
    valid_from: str
    valid_until: str
    max_uses: int
    usage_state: UsageState
    authorized_actors: set
    allowed_environments: set
    purposes: frozenset
    privacy_budget_max: float | None = None
    revoked: bool = False
    retention_state: str = ""
    execution_attestation: str = ""
    dp_accountant_id: str = ""

    def to_plain(self) -> dict:
        return {
            "current_time": self.current_time, "actor": self.actor,
            "purpose": self.purpose, "environment": self.environment,
            "rights_hash": self.rights_hash, "valid_from": self.valid_from,
            "valid_until": self.valid_until, "max_uses": self.max_uses,
            "usage_count": self.usage_state.usage_count,
            "privacy_budget_used": self.usage_state.privacy_budget_used,
            "authorized_actors": sorted(self.authorized_actors),
            "allowed_environments": sorted(self.allowed_environments),
            "purposes": sorted(self.purposes),
            "privacy_budget_max": self.privacy_budget_max,
            "revoked": self.revoked, "retention_state": self.retention_state,
            "execution_attestation": self.execution_attestation,
            "dp_accountant_id": self.dp_accountant_id,
        }


__all__ = ["PolicyInformation"]
