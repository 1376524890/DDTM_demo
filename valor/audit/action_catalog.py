"""认证动作目录（规范 §21.2 / §54.3）。

每个可执行审计动作 a_j 带其 action 似然 Λ_j 与预期现金成本 MĈ_A^pay。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .likelihood import ActionLikelihood


@dataclass
class CertifiedAction:
    """一个认证的审计动作。"""

    action_id: str
    likelihood: ActionLikelihood
    expected_cash_cost: float  # MĈ_A^pay [CU]
    payer: str = "SELLER"  # SELLER | BUYER
    trigger: str = "BASE_LISTING"  # BASE_LISTING | BUYER_INCREMENTAL


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

        return content_hash({aid: a.action_id for aid in self._actions})
