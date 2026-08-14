"""Policy Decision Point：Authorize（规范 §34）。

Authorize(R_τ, U_τ, Request)=1 当且仅当所有适用约束满足：
    t0 ≤ t ≤ t1；n_t < q；purpose_t ∈ Ψ；ActorAuthorized；EnvironmentAllowed；
    revoked_t = 0；有隐私预算时 ε_t + ε_request ≤ ε_max。
"""

from __future__ import annotations

from .models import UsageRequest, UsageState


def authorize(
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
) -> tuple[bool, list[str]]:
    """执行授权判定，返回 (是否允许, 违反约束列表)。"""
    violations: list[str] = []
    if request.timestamp < valid_from or request.timestamp > valid_until:
        violations.append("时间超出有效期")
    if usage_state.usage_count >= max_uses:
        violations.append("使用次数达上限")
    if request.purpose not in purposes:
        violations.append("用途不在授权集合")
    if request.actor not in authorized_actors:
        violations.append("主体未授权")
    if request.environment not in allowed_environments:
        violations.append("环境未授权")
    if usage_state.revoked:
        violations.append("权利已撤销")
    if privacy_budget_max is not None and (
        usage_state.privacy_budget_used + request.privacy_cost > privacy_budget_max
    ):
        violations.append("隐私预算超限")
    return (len(violations) == 0), violations
