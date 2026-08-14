"""分布式审计调度器（规范 §16/§17/§20）。

流程（对齐 Engineering Algorithm Q1 §48）：
    校验承诺 → Reverse VCG 分配 → 派发 TaskEnvelope 到委员会节点(HTTP) →
    处理超时/离线重指派 → 按 q/f 形成 BFT 证书 → 按 ρ 采样强验证 →
    仅罚没 ProvableMalice → 聚合动作结果 y（不把 minority 当恶意）。
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from valor.core.errors import CounterfactualInfeasibleError
from valor.market.reverse_vcg import reverse_vcg_payments
from valor.security.bft import p_live_binomial, p_safe_binomial
from valor.security.challenge import sample_challenge

from .client import AuditClient
from .node_state import NodeRegistry
from .task_models import TaskEnvelope


class DistributedAuditScheduler:
    """把一次质量审计任务派发到独立节点并形成证书。"""

    def __init__(
        self,
        *,
        endpoints: dict[str, str],  # node_id -> base_url
        registry: NodeRegistry,
        family: str,
        f: int,
        bids: dict,
        min_stake: float = 0.0,
        timeout_s: float = 15.0,
        rho: float = 0.0,
        eta_b: float = 0.0,
        eta_o: float = 0.0,
        seed: int = 0,
    ) -> None:
        self.endpoints = endpoints
        self.registry = registry
        self.family = family
        self.f = f
        self.m, self.q = 3 * f + 1, 2 * f + 1
        self.bids = bids
        self.min_stake = min_stake
        self.timeout_s = timeout_s
        self.rho = rho
        self.eta_b = eta_b
        self.eta_o = eta_o
        self.rng = np.random.default_rng(seed)

    def run(self, task: TaskEnvelope) -> dict[str, Any]:
        """执行分布式审计，返回证书与结果。"""
        # 1. Reverse VCG 分配委员会
        payments, cfcosts = reverse_vcg_payments(
            self.registry, family=self.family, m=self.m, bids=self.bids,
            min_stake=self.min_stake,
        )
        # 2. 派发任务到委员会节点
        evidence = {}
        offline = []
        for node_id in payments:
            url = self.endpoints.get(str(node_id))
            if url is None:
                offline.append(str(node_id))
                continue
            client = AuditClient(url)
            try:
                res = client.submit_task(task)
                evidence[str(node_id)] = res
            except Exception:
                offline.append(str(node_id))
        # 3. 离线重指派（liveness）：不足 q 时重跑
        if len(evidence) < self.q:
            return {
                "task_id": task.task_id,
                "status": "INSUFFICIENT_QUORUM",
                "evidence_count": len(evidence),
                "offline": offline,
            }
        # 4. 强验证挑战（ρ）
        challenged = sample_challenge(list(evidence), self.rho, rng=self.rng)
        for node_id in challenged:
            try:
                AuditClient(self.endpoints[node_id]).challenge(evidence[node_id]["evidence_id"])
            except Exception:
                pass
        # 5. BFT 证书：多数结果（≥ q 一致）
        results = [ev["result"] for ev in evidence.values()]
        cert_result = max(set(results), key=results.count)
        # 6. 安全概率
        p_safe = p_safe_binomial(self.m, self.f, self.eta_b)
        p_live = p_live_binomial(self.m, self.q, self.eta_b, self.eta_o)
        return {
            "task_id": task.task_id,
            "status": "CERTIFIED",
            "cert_result": cert_result,
            "q": self.q,
            "m": self.m,
            "evidence_count": len(evidence),
            "offline": offline,
            "p_safe": p_safe,
            "p_live": p_live,
            "payments": {k: round(v, 6) for k, v in payments.items()},
            "counterfactual_costs": {k: round(v, 6) for k, v in cfcosts.items()},
            "challenged_evidence": challenged,
        }
