"""PrivacyAuditVOI —— 隐私审计的 Audit-VOI 集成（PPA-6）。

让 k=32/64/128/256 成为真正不同的 PrivacyAuditAction（不同 challenge_size），
由 Audit-VOI 选择。每个 action 的 VCG cost 作为 MC_A^pay 进入 VOI 公式：
    MV_A = R(π) - ER(a_j)；VOI_A^private = MV_A - MC_A^pay
    若 max VOI ≤ 0 → STOP

审计执行用 PrivacyAuditScheduler（COMMIT_CHALLENGE）。后验由抽样 primitive 结果
Bayes 更新。披露预算不足 → ACTION_INFEASIBLE_PRIVACY_BUDGET（不执行、不计成本）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from valor.audit.action_catalog import ActionCatalog, CertifiedAction
from valor.audit.bayes_update import bayes_update
from valor.audit.likelihood import ActionLikelihood
from valor.audit.loss import LossMatrix
from valor.audit.state_model import StateBelief
from valor.audit.voi import choose_best_action, marginal_value_of_audit
from valor.core.hashing import content_hash
from valor.core.ids import AuditorID
from valor.distributed.node_state import AuditorNode, NodeRegistry

from .claims import AggregateClaim, claim_from_data
from .commitment import CommittedDatasetStore, DatasetCommitment
from .disclosure import DisclosureState
from .models import AuditExecutionMode, ClaimType, PrivacyAuditAction
from .scheduler import PrivacyAuditActionResult, PrivacyAuditScheduler
from .primitives import CLAIM_TO_PRIMITIVE


# k 候选（可配置；每个是一个 action）
DEFAULT_CHALLENGE_SIZES = [32, 64, 128, 256]


@dataclass
class PrivacyAuditVOIResult:
    posterior: dict
    p_breach_lower_sys: float
    audit_pay_s: float
    audit_pay_b: float
    n_steps: int
    action_results: list[dict] = field(default_factory=list)
    disclosure: dict = field(default_factory=dict)
    action_catalog_hash: str = ""
    audit_policy_hash: str = ""

    def to_plain(self) -> dict:
        return {
            "posterior": self.posterior,
            "p_breach_lower_sys": self.p_breach_lower_sys,
            "audit_pay_s": self.audit_pay_s,
            "audit_pay_b": self.audit_pay_b,
            "n_steps": self.n_steps,
            "action_results": self.action_results,
            "disclosure": self.disclosure,
            "action_catalog_hash": self.action_catalog_hash,
            "audit_policy_hash": self.audit_policy_hash,
        }


class PrivacyAuditVOIExecutor:
    """Audit-VOI + Commit-Challenge 隐私审计执行器。"""

    def __init__(
        self,
        *,
        scenario,
        candidate_X, candidate_y,
        claim_type: ClaimType = ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes: list[int] | None = None,
        n_nodes: int = 10,
        f: int = 2,
        seller_store: CommittedDatasetStore | None = None,
        node_client_factory: Callable[[str], Any] | None = None,
        certificate_artifact=None,
    ) -> None:
        self.scenario = scenario
        self.candidate_X = candidate_X
        self.candidate_y = candidate_y
        self.claim_type = claim_type
        self.challenge_sizes = challenge_sizes or DEFAULT_CHALLENGE_SIZES
        self.n_nodes = n_nodes
        self.f = f
        self.m, self.q = 3 * f + 1, 2 * f + 1
        self.node_client_factory = node_client_factory
        self.certificate_artifact = certificate_artifact
        self._store = seller_store or CommittedDatasetStore("seller_private")
        self._commitment: DatasetCommitment | None = None
        self._claim: AggregateClaim | None = None

    def _ensure_committed(self, tx_id: str) -> tuple[DatasetCommitment, AggregateClaim]:
        """卖方承诺候选数据 + 生成声明（交易绑定后、挑战前）。"""
        dataset_id = f"cand-{tx_id}"
        from valor.seller import SellerCommittedDataset

        seller = SellerCommittedDataset.create(
            self._store, dataset_id=dataset_id, version="v1",
            X=np.asarray(self.candidate_X, dtype=np.uint8),
            y=np.asarray(self.candidate_y, dtype=np.int64),
            schema_hash=content_hash({"schema": "MNIST-784"})[:64],
        )
        claim = claim_from_data(
            claim_type=self.claim_type, X=np.asarray(self.candidate_X),
            y=np.asarray(self.candidate_y),
            dataset_commitment_hash=seller.commitment.commitment_hash,
        )
        self._commitment = seller.commitment
        self._claim = claim
        self._seller = seller
        return seller.commitment, claim

    def _registry(self) -> NodeRegistry:
        reg = NodeRegistry()
        for i in range(self.n_nodes):
            reg.register(AuditorNode(AuditorID(f"node-{i}"), ("quality",), 1.0, 100.0 + i))
        return reg

    def _action(self, k: int) -> PrivacyAuditAction:
        primitive_id = CLAIM_TO_PRIMITIVE[self.claim_type]
        return PrivacyAuditAction(
            action_id=f"{self.claim_type.value}_CC_{k}",
            primitive_id=primitive_id,
            execution_mode=AuditExecutionMode.COMMIT_CHALLENGE,
            claim_type=self.claim_type, challenge_size=k,
            sampling_method="uniform_random",
            decision_rule_id="MULTINOMIAL_GOF",
        )

    def run(self, sc, ctx) -> PrivacyAuditVOIResult:
        tx_id = str(ctx["binding"].tx_id)
        commitment, claim = self._ensure_committed(tx_id)

        # 披露预算（来自 scenario 或 rights；显式）
        budget_cfg = sc.audit.get("privacy_budget", {})
        n_rows = commitment.n_rows
        max_rows = budget_cfg.get("max_unique_rows",
                                  sc.rights.get("audit_reveal_max_rows"))
        if max_rows is None:
            raise ValueError("需显式 audit_reveal_max_rows/privacy_budget（禁止默认）")
        disclosure = DisclosureState(
            dataset_commitment_hash=commitment.commitment_hash,
            max_unique_rows=int(max_rows),
            max_fraction=budget_cfg.get("max_fraction", 0.5),
            max_bytes=budget_cfg.get("max_bytes", int(max_rows) * 784),
            _n_rows=n_rows)

        registry = self._registry()
        bids = {AuditorID(str(n.node_id)): 10.0 + i
                for i, n in enumerate(registry.all())}

        from valor.seller.audit_service import SellerAuditService
        seller_svc = SellerAuditService(dataset=self._seller, disclosure=disclosure)
        seller_svc.add_claim(claim)

        scheduler = PrivacyAuditScheduler(
            registry=registry, f=self.f, bids=bids, seller_service=seller_svc,
            node_clients=self.node_client_factory)

        # ---- Audit-VOI 策略循环 ----
        prior = sc.audit_prior
        belief = StateBelief.from_prior(prior["pi_b"], prior["q_l"])
        loss = LossMatrix(loss=sc.loss_matrix)

        # action catalog：k 作为不同 action（似然用校准 artifact 或默认）
        catalog = ActionCatalog()
        for k in self.challenge_sizes:
            lik_rows = self._likelihood_rows()
            lik = ActionLikelihood(action_id=f"a-{k}", rows=lik_rows)
            catalog.register(CertifiedAction(
                f"a-{k}", lik, expected_cash_cost=0.0, payer="SELLER"))

        steps = []
        posterior = belief.to_plain()
        for _ in range(10):
            aid, best_voi, _ = choose_best_action(
                belief, catalog.likelihoods(), loss, catalog.costs())
            if aid is None or best_voi <= 0:
                break
            k = int(aid.split("-")[-1])  # aid="a-64" → 64
            action = self._action(k)
            res = scheduler.run(
                action, tx_id=tx_id, commitment=commitment, claim=claim,
                disclosure=disclosure)
            if res.status == "ACTION_INFEASIBLE_PRIVACY_BUDGET":
                break
            if res.status != "CERTIFIED":
                break
            outcome = "PASS" if res.cert_result == "PASS" else "QUALITY_FAIL"
            belief = bayes_update(belief, catalog.get(aid).likelihood.row(outcome))
            posterior = belief.to_plain()
            steps.append({
                "audit_step": len(steps) + 1, "action_id": aid, "k": k,
                "mc_a_pay": res.mc_a_pay, "voi": best_voi,
                "outcome": outcome, "posterior_after": posterior,
                "challenge_hash": res.challenge.challenge_hash,
                "rows_revealed": len(res.challenge.indices),
                "unique_disclosure_after": disclosure.unique_disclosure,
                "cost": res.cost.to_plain(),
                "result_counts": res.result_counts,
            })

        # 认证 p̲_B^sys（冻结证书或默认）
        if self.certificate_artifact is not None:
            p_b_lower = self.certificate_artifact.data["p_breach_lower_sys"]
        else:
            cert = sc.certificate
            from valor.security.certification import CertifiedCell, CertificationCatalog
            cat = CertificationCatalog()
            cat.register(CertifiedCell(
                "c1", cert["a_D"], cert["b_D"], cert["alpha_D"],
                {"breach": (cert["tp"], cert["fn"])}))
            p_b_lower = cat.p_breach_lower("c1", "breach")

        total_pay = sum(s["mc_a_pay"] for s in steps)
        audit_pay_s = total_pay * 0.5
        audit_pay_b = total_pay * 0.5

        return PrivacyAuditVOIResult(
            posterior=posterior, p_breach_lower_sys=p_b_lower,
            audit_pay_s=audit_pay_s, audit_pay_b=audit_pay_b,
            n_steps=len(steps), action_results=steps,
            disclosure=disclosure.to_plain(),
            action_catalog_hash=catalog.catalog_hash,
            audit_policy_hash=content_hash({"policy_id": "cc-audit"}),
        )

    def _likelihood_rows(self) -> dict:
        """似然行（P6 校准后应来自 artifact；此处默认结构）。"""
        if self.certificate_artifact is not None and hasattr(
                self.certificate_artifact.data, "get"):
            return self.certificate_artifact.data.get("likelihood_rows") or self.scenario.likelihood
        return self.scenario.likelihood


__all__ = ["PrivacyAuditVOIExecutor", "PrivacyAuditVOIResult",
           "DEFAULT_CHALLENGE_SIZES"]
