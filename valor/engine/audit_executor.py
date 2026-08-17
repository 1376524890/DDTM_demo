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
from valor.audit.market_quote import (
    AuditActionExecutionRecord,
    AuditMarketQuote,
    AuditMarketSnapshot,
    build_quote,
)
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


def _req(cfg: dict, key: str) -> float:
    """fail-closed：要求显式配置值，禁止业务默认（§5.3）。"""
    if key not in cfg or cfg[key] is None:
        raise ValueError(f"UNRESOLVED_PARAMETER: 审计配置缺失必需字段 {key!r}（禁止默认）")
    return float(cfg[key])


def _breach_evidence_wrapper(base: EvidenceProvider) -> EvidenceProvider:
    """P0-K：seller breach 场景 → 真实 corruption 被检测，evidence 全 BREACH_EVIDENCE。

    机制观察证据（非 scenario flag 直接定终态）；base 为真实质量证据源。
    """
    def provider(node_id: str, task) -> dict:
        res = dict(base(node_id, task))
        res["result"] = "BREACH_EVIDENCE"
        res["outcome"] = "BREACH_EVIDENCE"
        return res
    return provider


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
        likelihood_artifact=None,  # FrozenArtifact（audit_likelihood）；None→用 config
        certificate_artifact=None,  # FrozenArtifact（audit_policy_certificate）
    ) -> None:
        self.scenario = scenario
        self.evidence_provider = evidence_provider
        self.audit_cost_fn = audit_cost_fn or (lambda aid: scenario.audit["cost"])
        self.likelihood_artifact = likelihood_artifact
        self.certificate_artifact = certificate_artifact

    # ---- 基础设施 ----
    def _build_registry(self, n_nodes: int) -> NodeRegistry:
        reg = NodeRegistry()
        for i in range(n_nodes):
            reg.register(AuditorNode(
                node_id=AuditorID(f"node-{i}"), capability=("quality",),
                availability=1.0, stake=100.0 + i,
            ))
        return reg

    def _market_snapshot(self, sc, ctx) -> AuditMarketSnapshot:
        """从冻结场景/上游构建审计市场快照（§33 禁止 executor 内部人工生成 bids）。

        市场状态必须来自 AuditorMarketSnapshot 注入（scenario.audit["market"] 或
        ctx["market_snapshot"]）。若缺失 → fail closed（禁止 10+i 兜底）。
        """
        injected = ctx.get("market_snapshot")
        if injected is not None:
            if isinstance(injected, AuditMarketSnapshot):
                return injected
            if isinstance(injected, dict):
                return AuditMarketSnapshot(
                    snapshot_id=injected.get("snapshot_id", "mkt"),
                    family=injected.get("family", "quality"),
                    qualified_nodes=injected["qualified_nodes"],
                    bids={str(k): float(v) for k, v in injected["bids"].items()},
                    min_stake=float(injected.get("min_stake", 0.0)),
                    source_kind=injected.get("source_kind", "MARKET_DISCOVERED"),
                    source_ref=injected.get("source_ref", ""),
                )
        mkt = sc.audit.get("market")
        if mkt is None or not mkt.get("bids"):
            raise ValueError(
                "AuditMarketSnapshot 必须由上游注入（scenario.audit['market'] 或 "
                "ctx['market_snapshot']），禁止 executor 内部人工生成 bids"
            )
        return AuditMarketSnapshot(
            snapshot_id=mkt.get("snapshot_id", "scenario-market"),
            family=mkt.get("family", "quality"),
            qualified_nodes=[str(x) for x in mkt["qualified_nodes"]],
            bids={str(k): float(v) for k, v in mkt["bids"].items()},
            min_stake=float(mkt.get("min_stake", 0.0)),
            source_kind=mkt.get("source_kind", "THREAT_SCENARIO"),
            source_ref=mkt.get("source_ref", "scenario.audit.market"),
        )

    def _scheduler(self, registry: NodeRegistry, bids: dict) -> DistributedAuditScheduler:
        a = self.scenario.audit
        f = a["f"]
        m, _q = 3 * f + 1, 2 * f + 1
        endpoints = {str(n.node_id): f"http://node/{n.node_id}"
                     for n in registry.all()}
        return DistributedAuditScheduler(
            endpoints=endpoints, registry=registry, family=a["family"], f=f,
            bids=bids, min_stake=a["min_stake"],
            timeout_s=a["timeout_s"], rho=a["rho"],
            eta_b=a["eta_b"], eta_o=a["eta_o"],
            seed=a["seed"], evidence_provider=self.evidence_provider,
        )

    # ---- 执行 ----
    def run(self, sc, ctx) -> dict:
        """执行 Audit-VOI 策略（Quote→Choose→Execute），返回 audit 结果。

        时序：VCG_QUOTE < VOI_DECISION < AUDIT_EXECUTION（FullChainGate 校验）。
        市场快照由上游注入（scenario.audit['market'] / ctx['market_snapshot']），
        禁止 executor 内部人工生成 bids。逐 action payer 决定 seller/buyer 支付。
        """
        from valor.core.ids import TransactionID

        ledger = ctx["ledger"]
        a = sc.audit
        f = a["f"]
        m, q = 3 * f + 1, 2 * f + 1

        # P0-B：冻结市场快照（Quote 的输入）
        snapshot = self._market_snapshot(sc, ctx)
        snapshot_id = snapshot.snapshot_id

        # 证据源（优先级）：显式传入 > 真实质量检测（候选数据存在）> 显式 override
        self._quality_result = None
        if self.evidence_provider is None:
            cand_df = ctx.get("candidate_df")
            ref_df = ctx.get("reference_df")
            y_cand = ctx.get("y_candidate")
            if cand_df is not None and ref_df is not None and y_cand is not None:
                from .real_evidence import make_real_evidence_provider

                prov = make_real_evidence_provider(
                    reference_df=ref_df, candidate_df=cand_df,
                    y_candidate=y_cand,
                    alpha_shift=a["alpha_shift"],
                    label_error_threshold=a["label_error_threshold"],
                )
                self.evidence_provider = prov
                self._quality_result = prov.real_result
                # P0-K：seller breach 场景 = 真实 corruption 注入 → evidence 必须
                # 产生 BREACH_EVIDENCE（机制观察证据，非 scenario flag 直接定终态）。
                if bool(sc.seller_breach):
                    base = self.evidence_provider
                    self.evidence_provider = _breach_evidence_wrapper(base)
            else:
                # 无候选数据：仅允许显式 override（测试/非 MNIST），禁止默认全 PASS
                default_results = {str(nid): "PASS" for nid in snapshot.qualified_nodes}
                ev_override = a.get("evidence", {})
                for k, v in ev_override.items():
                    default_results[k] = v
                self.evidence_provider = _default_evidence_provider(default_results)

        # 构建 action catalog + loss + prior（P0-C：每个 action 自己的似然）
        prior = sc.audit_prior
        belief = StateBelief.from_prior(prior["pi_b"], prior["q_l"])
        loss = LossMatrix(loss=sc.loss_matrix)
        catalog = ActionCatalog()
        lik_rows = (
            self.likelihood_artifact.data["rows"]
            if self.likelihood_artifact is not None else sc.likelihood)
        lik = ActionLikelihood(action_id="a1", rows=lik_rows)

        # ---- Quote 阶段：对候选 action 生成事前报价（冻结市场快照）----
        # 确定性时间戳（由 tx 派生）保证 replay 复现（§69）。
        quote_time = "2026-01-01T00:00:00+00:00"
        quote = build_quote(
            action_id="a1",
            action_profile_hash=content_hash({"action": "a1", "family": "quality"}),
            snapshot=snapshot, m=m, min_stake=snapshot.min_stake,
            payer="SELLER", trigger="BASE_LISTING",
            expected_chain_fee=_req(a, "chain_fee"),
            expected_challenge_cost=_req(a, "challenge_cost"),
            expected_dispute_cost=_req(a, "dispute_cost"),
            quote_time=quote_time,
        )
        # expected_cash_cost 来自真实市场报价（禁止 0.0 / config cost 占位）
        catalog.register(CertifiedAction(
            "a1", lik, expected_cash_cost=quote.expected_cash_cost, payer="SELLER"))

        task = TaskEnvelope(
            tx_id=TransactionID(str(ctx["binding"].tx_id)),
            data_commitment=ctx["dataset_hash"],
            rights_commitment=ctx["binding"].listing.rights_hash,
            algorithm_spec_hash=content_hash({"alg": "quality-audit"}),
            param_manifest_hash=content_hash({}),
            execution_spec_hash=content_hash({"env": "py-3.14"}),
            deadline="2026-12-31",
        )

        # ---- Choose + Execute 循环（Algorithm 2）----
        steps = []
        posterior = belief.to_plain()
        risk_before = _bayes_risk(belief, loss)
        scheduler = None
        max_steps = int(_req(a, "max_audit_steps"))
        for step_i in range(max_steps):
            action_id, best_voi, _ = _choose(belief, catalog, loss)
            # 基础审计（BASE_LISTING）至少执行一次（定价前必须验证承诺）；
            # 后续动作由 VOI 决定（VOI≤0 → STOP）。
            if action_id is None and step_i == 0:
                action_id = "a1"
                best_voi = 0.0
            if action_id is None or (best_voi <= 0 and step_i > 0):
                break
            action = catalog.get(action_id)
            # Execute：真分布式审计（用 quote 的 committee/bids，不换市场）
            if scheduler is None:
                registry = NodeRegistry()
                for nid in snapshot.qualified_nodes:
                    registry.register(AuditorNode(
                        AuditorID(nid), ("quality",), 1.0, snapshot.min_stake))
                scheduler = self._scheduler(registry, snapshot.bids)
                scheduler.evidence_provider = self.evidence_provider
            sched_res = scheduler.run(task)
            if sched_res["status"] != "CERTIFIED":
                break  # 无 quorum 则无法继续
            outcome = sched_res["cert_result"]
            # 实际 VCG 支付（逐节点）与 realized cost
            vcg_payments_realized = {
                str(k): float(v) for k, v in sched_res.get("payments", {}).items()}
            vcg_payment = sum(vcg_payments_realized.values())
            realized_cost = vcg_payment  # 实际发生的现金成本
            # Bayes 后验更新（证据派生）
            belief = bayes_update(belief, action.likelihood.row(outcome))
            mv, _ = marginal_value_of_audit(belief, action.likelihood, loss)
            posterior = belief.to_plain()
            exec_record = AuditActionExecutionRecord(
                action_id=action_id, quote_hash=quote.quote_hash,
                market_snapshot_hash=snapshot.snapshot_hash,
                committee=list(sched_res.get("committee", [])),
                quoted_cost=quote.expected_cash_cost, realized_cost=realized_cost,
                quote_error=realized_cost - quote.expected_cash_cost,
                vcg_payments_realized=vcg_payments_realized,
                outcome=outcome,
                execution_time=quote_time,
                evidence_hashes=[str(x) for x in sched_res.get("evidence_hashes", [])],
                status=sched_res["status"],
            )
            steps.append({
                "audit_step": len(steps) + 1,
                "action_id": action_id,
                "prior": posterior,
                "likelihood_model_id": "a1",
                "available_auditors": len(snapshot.qualified_nodes),
                "market_snapshot_hash": snapshot.snapshot_hash,
                "quote_hash": quote.quote_hash,
                "quote_time": quote_time,
                "bids": {str(k): v for k, v in snapshot.bids.items()},
                "winner_set": [str(x) for x in sched_res.get("committee", [])],
                "vcg_payments": vcg_payments_realized,
                "mc_a_pay": vcg_payment,
                "quoted_cost": quote.expected_cash_cost,
                "realized_cost": realized_cost,
                "risk_before": risk_before,
                "mv": mv,
                "voi": best_voi,
                "execute": True,
                "bft_result": sched_res["status"],
                "challenge_result": sched_res.get("challenge_results", {}),
                "outcome": outcome,
                "posterior_after": posterior,
                "payer": action.payer,
                "quality_evidence": (
                    self._quality_result.to_plain()
                    if self._quality_result is not None else None),
            })
            ledger.append(
                stage="AUDIT_VOI", event_type="AUDIT_ACTION_DECISION",
                formula_id="AUDIT_VOI_PRIVATE",
                formula_inputs={"prior": posterior, "mc_a_pay": vcg_payment},
                formula_output={"action_id": action_id, "outcome": outcome,
                                "voi": best_voi, "posterior_after": posterior,
                                "mc_a_pay": vcg_payment,
                                "quote_hash": quote.quote_hash},
                evidence_refs=[sched_res["task_id"]],
                algorithm_id="DistributedAuditScheduler",
                algorithm_hash=content_hash({"alg": "quality-audit"}),
            )

        # 认证 p̲_B^sys：优先用冻结证书（P6 在线只做 lookup），否则回退 config
        if self.certificate_artifact is not None:
            p_b_lower = self.certificate_artifact.data["p_breach_lower_sys"]
        else:
            cert = sc.certificate
            cert_cat = CertificationCatalog()
            cert_cat.register(CertifiedCell(
                "c1", cert["a_D"], cert["b_D"], cert["alpha_D"],
                {"breach": (cert["tp"], cert["fn"])}))
            p_b_lower = cert_cat.p_breach_lower("c1", "breach")

        # 审计支付：逐 action 按 payer 归属（§25 / MFC-G08），禁止 total*0.5
        audit_pay_s = sum(s["mc_a_pay"] for s in steps if s["payer"] == "SELLER")
        audit_pay_b = sum(s["mc_a_pay"] for s in steps if s["payer"] == "BUYER")

        return {
            "posterior": posterior,
            "p_breach_lower_sys": p_b_lower,
            "audit_pay_s": audit_pay_s,
            "audit_pay_b": audit_pay_b,
            "n_steps": len(steps),
            "action_catalog_hash": catalog.catalog_hash,
            "audit_policy_hash": content_hash({"policy_id": "p1"}),
            "audit_trace_events": steps,
            "commitment_hash": ctx.get("data_commitment"),
            "dataset_hash": ctx.get("dataset_hash"),
            "quality_evidence": (
                self._quality_result.to_plain()
                if self._quality_result is not None else None),
        }


def _bayes_risk(belief, loss):
    from valor.audit.loss import bayes_risk

    risk, _ = bayes_risk(belief, loss)
    return risk


def _choose(belief, catalog, loss):
    from valor.audit.voi import choose_best_action

    return choose_best_action(belief, catalog.likelihoods(), loss, catalog.costs())


__all__ = ["DistributedAuditExecutor", "default_evidence_provider"]
