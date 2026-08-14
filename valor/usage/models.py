"""用途状态与请求（规范 §34）。

U_τ(t) = (n_t, t, purpose_t, actor_t, env_t, ε_t, revoked_t, retentionState)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UsageState:
    """已授予权利的当前用途状态（§34）。"""

    usage_count: int = 0
    privacy_budget_used: float = 0.0
    revoked: bool = False

    def to_plain(self) -> dict:
        return {
            "usage_count": self.usage_count,
            "privacy_budget_used": self.privacy_budget_used,
            "revoked": self.revoked,
        }


@dataclass(frozen=True)
class UsageRequest:
    """一次使用请求。"""

    actor: str
    purpose: str
    environment: str
    timestamp: str
    privacy_cost: float = 0.0
    action: str = "read"
