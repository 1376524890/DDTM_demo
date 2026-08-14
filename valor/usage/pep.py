"""Policy Enforcement Point（规范 §35）。

拦截 API/compute/export 请求，调用 PDP 判定，允许则执行 PXP，拒绝则记录
DENY 事件（§37：denied 请求也生成审计事件）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import UsageRequest, UsageState
from .pdp import authorize


@dataclass
class EnforcementResult:
    """一次执行点判定结果。"""

    decision: str  # ALLOW | DENY
    violations: list = field(default_factory=list)
    usage_state: UsageState = None  # type: ignore
    receipt_id: str = ""

    def to_plain(self) -> dict:
        return {"decision": self.decision, "violations": self.violations}


def enforce(
    *,
    request: UsageRequest,
    usage_state: UsageState,
    valid_from: str,
    valid_until: str,
    max_uses: int,
    purposes: frozenset,
    authorized_actors: set,
    allowed_environments: set,
    privacy_budget_max: float | None = None,
) -> EnforcementResult:
    """执行点：判定 + 执行（扣次数/更新隐私预算）。"""
    allowed, violations = authorize(
        request=request, usage_state=usage_state,
        valid_from=valid_from, valid_until=valid_until, max_uses=max_uses,
        purposes=purposes, authorized_actors=authorized_actors,
        allowed_environments=allowed_environments,
        privacy_budget_max=privacy_budget_max,
    )
    if not allowed:
        return EnforcementResult(decision="DENY", violations=violations,
                                 usage_state=usage_state)
    # PXP：更新使用状态（§34 n_{t+1}=n_t+1）
    usage_state.usage_count += 1
    usage_state.privacy_budget_used += request.privacy_cost
    return EnforcementResult(decision="ALLOW", usage_state=usage_state)
