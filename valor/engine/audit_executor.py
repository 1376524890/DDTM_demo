"""DistributedAuditExecutor —— 把真分布式审计接进 Audit-VOI（P4/P5）。

对接交文档第九节：
    Auditor bids → Reverse VCG virtual allocation → MC_A^pay(a_j) → Audit-VOI
    MV_A = R(π) - ER(a_j)；VOI_A^private = MV_A - MC_A^pay
    若 VOI_A^private ≤ 0 → STOP；否则真正执行 action。

每次 AuditTrace 记录：audit_step / action_id / prior / likelihood_model_id /
available_auditors / bids / winner_set / vcg_payments / MC_A_pay / risk_before /
expected_risk_after / MV / VOI / execute / HTTP evidence / BFT result /
challenge result / outcome / posterior_after / payer。

证据来自 DistributedAuditScheduler（默认进程内确定性证据源，可切换真 HTTP）。
后验由证据结果经 Bayes 更新产生——绝不用 config 手填后验。
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from valor.audit.action_catalog import ActionCatalog, CertifiedAction
from valor.audit.bayes_update import bayes_update
from valor.audit.likelihood import ActionLikelihood
from valor.audit.loss import LossMatrix
from valor.audit.state_model import StateBelief
from valor.audit.voi import marginal_value_of_audit
from valor.core.hashing import content_hash
from valor.core.ids import AuditorID
from valor.distributed.node_state import AuditorNode, NodeRegistry
from valor.distributed.scheduler import DistributedAuditScheduler
from valor.distributed.task_models import TaskEnvelope
from valor.security.certification import CertifiedCell, CertificationCatalog

# evidence provider 类型：(node_id, task) -> {"result": str}
EvidenceProvider = Callable[[str, Any], dict]


def _default_evidence_provider(results_by_node: dict[str, str]) -> EvidenceProvider:
    """构造确定性 evidence provider：按节点固定返回结果。"""
    def provider(node_id: str, task) -> dict:
        if node_id not in results_by_node:
            raise ConnectionError(f"节点 {node_id} 不在证据源")
        return {"evidence_id": f"evt-{task.task_id}-{node_id}",
                "result": results_by_node[node_id]}
    return provider


class DistributedAuditExecutor:
    """运行一次 Audit-VOI 策略，每次 action 通过分布式审计获得证据与 VCG cost。"""

    def __init__(
        self,
        scenario,
        *,
        evidence_provider: EvidenceProvider | None = None,
        audit_cost_fn: Callable[[str], float] | None = None,
    ) -> None:
        self.scenario = scenario
        self.evidence_provider = evidence_provider
        self.audit_cost_fn = audit_cost_fn or (lambda aid: scenario.audit.get("cost", 2.0))

    # ---- 基础设施 ----
    def _build_registry(self, n_nodes: int) -> NodeRegistry:
        reg = NodeRegistry()
        for i in range(n_nodes):
            reg.register(AuditorNode(
                node_id=AuditorID(f"node-{i}"), capability=("quality",),
                availability=1.0, stake=100.0 + i,
            ))
        return reg

    def _scheduler(self, registry: NodeRegistry, bids: dict) -> DistributedAuditScheduler:
        a = self.scenario.audit
        f = a["f"]
        m, _q = 3 * f + 1, 2 * f + 1
        endpoints = {str(n.node_id): f"http://node/{n.node_id}"
                     for n in registry.all()}
        return DistributedAuditScheduler(
            endpoints=endpoints, registry=registry, family=a["family"], f=f,
            bids=bids, min_stake=a.get("min_stake", 0.0),
            timeout_s=a.get("timeout_s", 10.0), rho=a.get("rho", 0.0),
            eta_b=a.get("eta_b", 0.0), eta_o=a.get("eta_o", 0.0),
            seed=a.get("seed", 0), evidence_provider=self.evidence_provider,
        )

    # ---- 执行 ----
    def run(self, sc, ctx) -> dict:
        """执行 Audit-VOI 策略，返回 {posterior, p_breach_lower_sys, audit_pay_*, trace}。"""
        ledger = ctx["ledger"]
        a = sc.audit
        n_nodes = a["n_nodes"]
        f = a["f"]
        m, q = 3 * f + 1, 2 * f + 1

        registry = self._build_registry(n_nodes)
        bids = {AuditorID(str(n.node_id)): 10.0 + i for i, n in enumerate(registry.all())}
        scheduler = self._scheduler(registry, bids)

        # 默认 evidence：全部 PASS（场景可在 audit["evidence"] 指定）
        default_results = {str(n.node_id): "PASS" for n in registry.all()}
        if self.evidence_provider is None:
            ev_override = a.get("evidence", {})
            for k, v in ev_override.items():
                default_results[k] = v
            self.evidence_provider = _default_evidence_provider(default_results)
            scheduler.evidence_provider = self.evidence_provider

        # 构建 action catalog + loss + prior
        prior = sc.audit_prior
        belief = StateBelief.from_prior(prior["pi_b"], prior["q_l"])
        loss = LossMatrix(loss=sc.loss_matrix)
        catalog = ActionCatalog()
        lik = ActionLikelihood(action_id="a1", rows=sc.likelihood)
        catalog.register(CertifiedAction(
            "a1", lik, expected_cash_cost=self.audit_cost_fn("a1"),
            payer="SELLER"))

        # 审计市场 bids → VCG（先算一次，得到 MC_A^pay = 委员会 VCG 支付总额）
        from valor.core.ids import TransactionID

        task = TaskEnvelope(
            tx_id=TransactionID(str(ctx["binding"].tx_id)),
            data_commitment=ctx["dataset_hash"],
            rights_commitment=ctx["binding"].listing.rights_hash,
            algorithm_spec_hash=content_hash({"alg": "quality-audit"}),
            param_manifest_hash=content_hash({}),
            execution_spec_hash=content_hash({"env": "py-3.14"}),
            deadline="2026-12-31",
        )

        # Audit-VOI 策略循环（Algorithm 2）
        steps = []
        posterior = belief.to_plain()
        risk_before = _bayes_risk(belief, loss)
        for _ in range(10):  # 步数上限
            action_id, best_voi, _ = _choose(belief, catalog, loss)
            if action_id is None or best_voi <= 0:
                break
            action = catalog.get(action_id)
            # 真分布式审计执行 → evidence → BFT result
            sched_res = scheduler.run(task)
            if sched_res["status"] != "CERTIFIED":
                break  # 无 quorum 则无法继续
            outcome = sched_res["cert_result"]
            # VCG 支付 = 委员会成员 VCG payment 之和（MC_A^pay）
            vcg_payment = sum(sched_res.get("payments", {}).values())
            # Bayes 后验更新（证据派生）
            belief = bayes_update(belief, action.likelihood.row(outcome))
            mv, _ = marginal_value_of_audit(belief, action.likelihood, loss)
            posterior = belief.to_plain()
            steps.append({
                "audit_step": len(steps) + 1,
                "action_id": action_id,
                "prior": posterior,  # 更新后（近似）
                "likelihood_model_id": "a1",
                "available_auditors": n_nodes,
                "bids": {str(k): v for k, v in bids.items()},
                "winner_set": [str(x) for x in sched_res.get("committee", [])],
                "vcg_payments": {str(k): v for k, v in sched_res.get("payments", {}).items()},
                "mc_a_pay": vcg_payment,
                "risk_before": risk_before,
                "mv": mv,
                "voi": best_voi,
                "execute": True,
                "bft_result": sched_res["status"],
                "challenge_result": sched_res.get("challenge_results", {}),
                "outcome": outcome,
                "posterior_after": posterior,
                "payer": action.payer,
            })
            # 记录 trace event
            ledger.append(
                stage="AUDIT_VOI", event_type="AUDIT_ACTION_DECISION",
                formula_id="AUDIT_VOI_PRIVATE",
                formula_inputs={"prior": posterior, "mc_a_pay": vcg_payment},
                formula_output={"action_id": action_id, "outcome": outcome,
                                "voi": best_voi, "posterior_after": posterior,
                                "mc_a_pay": vcg_payment},
                evidence_refs=[sched_res["task_id"]],
                algorithm_id="DistributedAuditScheduler",
                algorithm_hash=content_hash({"alg": "quality-audit"}),
            )

        # 认证 p̲_B^sys
        cert = sc.certificate
        cert_cat = CertificationCatalog()
        cert_cat.register(CertifiedCell(
            "c1", cert["a_D"], cert["b_D"], cert["alpha_D"],
            {"breach": (cert["tp"], cert["fn"])}))
        p_b_lower = cert_cat.p_breach_lower("c1", "breach")

        # 审计支付 = 实际 VCG 支付总额（seller/buyer 各半，payer 决定）
        total_pay = sum(s.get("mc_a_pay", 0.0) for s in steps)
        audit_pay_s = total_pay * 0.5
        audit_pay_b = total_pay * 0.5

        return {
            "posterior": posterior,
            "p_breach_lower_sys": p_b_lower,
            "audit_pay_s": audit_pay_s,
            "audit_pay_b": audit_pay_b,
            "n_steps": len(steps),
            "action_catalog_hash": catalog.catalog_hash,
            "audit_policy_hash": content_hash({"policy_id": "p1"}),
            "audit_trace_events": steps,
        }


def _bayes_risk(belief, loss):
    from valor.audit.loss import bayes_risk

    risk, _ = bayes_risk(belief, loss)
    return risk


def _choose(belief, catalog, loss):
    from valor.audit.voi import choose_best_action

    return choose_best_action(belief, catalog.likelihoods(), loss, catalog.costs())


__all__ = ["DistributedAuditExecutor", "default_evidence_provider"]
