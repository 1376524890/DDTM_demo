"""PrivacyAuditExecutorAdapter —— 把 PrivacyAuditVOIExecutor 接入 TransactionOrchestrator。

orchestrator 的 audit_executor 契约：(sc, ctx) -> dict，键为
    posterior / p_breach_lower_sys / audit_pay_s / audit_pay_b / n_steps /
    action_catalog_hash / audit_policy_hash / audit_trace_events
本适配器包装 PrivacyAuditVOIExecutor，并附加隐私审计特有字段
（disclosure / action_results / commitment_hash / challenge_hashes），
使 COMMIT_CHALLENGE 成为 capstone 交易的审计执行层。
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from .models import ClaimType
from .voi import PrivacyAuditVOIExecutor
from valor.core.enums import ExecutionMode
from .process_isolated import AuditRuntimeDescriptor


def make_privacy_audit_executor(
    *,
    claim_type: ClaimType = ClaimType.LABEL_DISTRIBUTION,
    challenge_sizes: list[int] | None = None,
    n_nodes: int = 10,
    f: int = 2,
    seller_store=None,
    node_client_factory: Callable[[str], Any] | None = None,
    certificate_artifact=None,
    likelihood_catalog=None,
    action_profile_catalog=None,
    execution_mode: ExecutionMode = ExecutionMode.TEST_FIXTURE,
    auditor_identity_registry=None,
    public_keys: dict[str, str] | None = None,
    audit_runtime: AuditRuntimeDescriptor | None = None,
    market_provider=None,
    audit_policy=None,
    role_registry=None,
) -> Callable:
    """构造 orchestrator 兼容的 audit_executor（COMMIT_CHALLENGE 模式）。"""

    def executor(sc, ctx):
        # ctx 提供 candidate_df / y_candidate / binding / dataset_hash
        cand_X = ctx.get("candidate_df")
        cand_y = ctx.get("y_candidate")
        if cand_X is None or cand_y is None:
            raise ValueError(
                "PrivacyAuditExecutor 需要 ctx.candidate_df/y_candidate"
                "（卖方候选数据，用于承诺）")
        # P0-A：优先消费上游 canonical commitment（orchestrator 已构建唯一实例）。
        # 禁止审计层重新 commit；seller_store 仅作为无上游独立运行的 fallback。
        upstream_seller = ctx.get("seller_committed")
        upstream_commitment = ctx.get("dataset_commitment")
        store = seller_store or ctx.get("seller_store")

        ex = PrivacyAuditVOIExecutor(
            scenario=sc, candidate_X=cand_X, candidate_y=cand_y,
            claim_type=claim_type, challenge_sizes=challenge_sizes,
            n_nodes=n_nodes, f=f, seller_store=store,
            seller_committed=upstream_seller,
            dataset_commitment=upstream_commitment,
            node_client_factory=node_client_factory,
            certificate_artifact=certificate_artifact,
            likelihood_catalog=likelihood_catalog,
            action_profile_catalog=action_profile_catalog,
            execution_mode=execution_mode,
            auditor_identity_registry=auditor_identity_registry,
            public_keys=public_keys,
            audit_runtime=audit_runtime,
            market_provider=market_provider,
            audit_policy=audit_policy,
            role_registry=role_registry,
        )
        res = ex.run(sc, ctx)
        # 映射为 orchestrator 兼容 dict
        action_results = [a for a in res.action_results]
        return {
            "posterior": res.posterior,
            "p_breach_lower_sys": res.p_breach_lower_sys,
            "audit_pay_s": res.audit_pay_s,
            "audit_pay_b": res.audit_pay_b,
            "n_steps": res.n_steps,
            "action_catalog_hash": res.action_catalog_hash,
            "audit_policy_hash": res.audit_policy_hash,
            "audit_policy_status": res.audit_policy_status,
            # 隐私审计特有
            "audit_trace_events": action_results,
            "disclosure": res.disclosure,
            "execution_mode": "COMMIT_CHALLENGE",
            "challenge_hashes": [a["challenge_hash"] for a in action_results],
            "unique_disclosure": res.disclosure.get("unique_disclosure", 0),
            "disclosure_fraction": res.disclosure.get("disclosure_fraction", 0.0),
        }

    return executor


__all__ = ["make_privacy_audit_executor"]
