"""分布式审计调度器（规范 §16/§17/§20，P4 修复版）。

流程（对齐交接文档 Priority 1）：
    action candidate
        → auditor bids
        → Reverse VCG 分配委员会
        → 派发 TaskEnvelope 到委员会节点(HTTP)
        → 离线重指派（replacement，从备用池补足）
        → evidence
        → quorum-by-result：同一结果取得至少 q 个一致 evidence，否则 NO_QUORUM
        → challenge（ρ 采样强验证）
        → evidence verification
        → malice determination（challenge 失败 → 可罚没）
        → slash / reward

关键修复（交接文档明确）：
- 旧逻辑 `evidence_count >= q` 是错的；正确要求是
    #{i : Y_i = y^*} ≥ q
  否则 NO_QUORUM，而非 CERTIFIED。
- 离线节点用 registry 中的备用节点替换，保证 liveness，而非直接失败。
- 记录完整 AuditTrace（bids / vcg_payments / MC_A^pay / evidence / quorum / challenge）。
"""

from __future__ import annotations

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
    """把一次质量审计任务派发到独立节点并形成证书（P4 quorum-by-result）。"""

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
        evidence_provider=None,  # (node_id, task) -> {"result": str} 进程内证据源
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
        self.evidence_provider = evidence_provider

    def _collect(self, committee, task) -> tuple[dict, list]:
        """派发任务到委员会节点；返回 (evidence, offline)。"""
        evidence: dict[str, dict] = {}
        offline: list[str] = []
        for node_id in committee:
            url = self.endpoints.get(str(node_id))
            if url is None:
                offline.append(str(node_id))
                continue
            try:
                if self.evidence_provider is not None:
                    res = self.evidence_provider(str(node_id), task)
                else:
                    client = AuditClient(url, timeout=self.timeout_s)
                    res = client.submit_task(task)
                evidence[str(node_id)] = res
            except Exception:
                offline.append(str(node_id))
        return evidence, offline

    def run(self, task: TaskEnvelope) -> dict[str, Any]:
        """执行分布式审计，返回证书与完整 trace（P4 quorum-by-result）。"""
        trace: dict[str, Any] = {"task_id": task.task_id}

        # 1. Reverse VCG 分配委员会
        try:
            payments, cfcosts = reverse_vcg_payments(
                self.registry, family=self.family, m=self.m, bids=self.bids,
                min_stake=self.min_stake,
            )
        except CounterfactualInfeasibleError as e:
            trace.update({"status": "NO_FEASIBLE_COMMITTEE", "reason": str(e)})
            return trace
        committee = list(payments)
        trace["committee"] = committee
        trace["payments"] = {k: round(v, 6) for k, v in payments.items()}
        trace["counterfactual_costs"] = {k: round(v, 6) for k, v in cfcosts.items()}

        # 2-3. 派发 + 离线重指派（replacement）
        evidence, offline = self._collect(committee, task)
        replacements = []
        spare_pool = [
            str(n.node_id) for n in self.registry.all()
            if str(n.node_id) not in committee and str(n.node_id) in self.endpoints
        ]
        rng = np.random.default_rng(self.seed_for(task))
        rng.shuffle(spare_pool)
        for off in list(offline):
            if not spare_pool:
                break
            repl = spare_pool.pop()
            replacements.append((off, repl))
            try:
                if self.evidence_provider is not None:
                    res = self.evidence_provider(str(repl), task)
                else:
                    client = AuditClient(self.endpoints[repl], timeout=self.timeout_s)
                    res = client.submit_task(task)
                evidence[str(repl)] = res
                offline.remove(off)
            except Exception:
                pass
        trace["offline"] = offline
        trace["replacements"] = replacements
        trace["evidence_count"] = len(evidence)

        # 4. 无足够 evidence → NO_QUORUM
        if len(evidence) < self.q:
            trace.update({
                "status": "NO_QUORUM",
                "reason": f"可用证据 {len(evidence)} < q={self.q}（含替换后）",
            })
            return trace

        # 5. quorum-by-result：同一结果 ≥ q 个一致 evidence（核心修复）
        results = [ev["result"] for ev in evidence.values()]
        counts: dict[str, int] = {}
        for r in results:
            counts[r] = counts.get(r, 0) + 1
        cert_result = max(counts, key=counts.get)
        if counts[cert_result] < self.q:
            trace.update({
                "status": "NO_QUORUM",
                "reason": f"结果 {cert_result} 仅 {counts[cert_result]} 个一致 "
                         f"evidence < q={self.q}（quorum-by-result 失败）",
                "result_counts": counts,
            })
            return trace
        trace["result_counts"] = counts

        # 6. challenge（ρ 采样强验证）
        challenged = sample_challenge(list(evidence), self.rho, rng=self.rng)
        challenge_results: dict[str, bool] = {}
        malice: list[str] = []
        for node_id in challenged:
            try:
                cr = AuditClient(self.endpoints[node_id], timeout=self.timeout_s) \
                    .challenge(evidence[node_id]["evidence_id"])
                passed = bool(cr.get("challenge_passed", False))
                challenge_results[node_id] = passed
                if not passed:
                    malice.append(node_id)
            except Exception:
                challenge_results[node_id] = False
                malice.append(node_id)
        trace["challenged_evidence"] = challenged
        trace["challenge_results"] = challenge_results
        trace["malice_determined"] = malice

        # 7. BFT 安全/在线概率
        p_safe = p_safe_binomial(self.m, self.f, self.eta_b)
        p_live = p_live_binomial(self.m, self.q, self.eta_b, self.eta_o)

        trace.update({
            "status": "CERTIFIED",
            "cert_result": cert_result,
            "q": self.q,
            "m": self.m,
            "p_safe": p_safe,
            "p_live": p_live,
        })
        return trace

    def seed_for(self, task: TaskEnvelope) -> int:
        """派生确定性 seed（供 replacement 随机化）。"""
        from valor.core.hashing import sha256_hex

        return int(sha256_hex(task.task_id.encode("utf-8"))[:8], 16)


__all__ = ["DistributedAuditScheduler"]
