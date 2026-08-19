"""认证动作目录（规范 §21.2 / §54.3）。

每个可执行审计动作 a_j 带其 action 似然 Λ_j 与预期现金成本 MĈ_A^pay。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import Any

from .likelihood import ActionLikelihood
from .action_profile import AuditActionProfile
from valor.core.hashing import content_hash


@dataclass
class CertifiedAction:
    """一个认证的审计动作。"""

    action_id: str
    likelihood: ActionLikelihood
    expected_cash_cost: float  # MĈ_A^pay [CU]
    payer: str = "SELLER"  # SELLER | BUYER
    trigger: str = "BASE_LISTING"  # BASE_LISTING | BUYER_INCREMENTAL
    action_profile_hash: str = ""


class ActionProfileCatalog:
    """Canonical profile registry keyed by action_profile_hash (Round 4 P0-C)."""

    def __init__(self) -> None:
        self._profiles: dict[str, AuditActionProfile] = {}

    def register(self, profile: AuditActionProfile) -> None:
        self._profiles[profile.action_profile_hash] = profile

    def resolve(self, action_profile_hash: str) -> AuditActionProfile:
        if action_profile_hash not in self._profiles:
            raise KeyError(
                f"ACTION_NOT_CERTIFIED: no action profile for {action_profile_hash}"
            )
        return self._profiles[action_profile_hash]

    def catalog_hash(self) -> str:
        return content_hash({
            k: v.action_profile_hash
            for k, v in sorted(self._profiles.items())
        })

    def to_plain(self) -> dict:
        return {
            "catalog_hash": self.catalog_hash(),
            "profiles": {k: v.to_plain() for k, v in self._profiles.items()},
        }


class ActionCatalog:
    """认证审计动作目录。"""

    def __init__(self) -> None:
        self._actions: dict[str, CertifiedAction] = {}

    def register(self, action: CertifiedAction) -> None:
        self._actions[action.action_id] = action

    def get(self, action_id: str) -> CertifiedAction:
        return self._actions[action_id]

    def all(self) -> dict[str, CertifiedAction]:
        return self._actions

    def likelihoods(self) -> dict[str, ActionLikelihood]:
        return {aid: a.likelihood for aid, a in self._actions.items()}

    def costs(self) -> dict[str, float]:
        return {aid: a.expected_cash_cost for aid, a in self._actions.items()}

    @property
    def catalog_hash(self) -> str:
        from valor.core.hashing import content_hash

        return content_hash({
            aid: {"action_id": action.action_id, "payer": action.payer}
            for aid, action in self._actions.items()
        })
