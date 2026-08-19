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
from valor.audit.action_profile import AuditActionProfile
from valor.audit.bayes_update import bayes_update
from valor.audit.likelihood import ActionLikelihood
from valor.audit.loss import LossMatrix
from valor.audit.state_model import StateBelief
from valor.audit.voi import choose_best_action, marginal_value_of_audit
from valor.core.enums import ExecutionMode
from valor.core.hashing import content_hash
from valor.core.ids import AuditorID
from valor.distributed.node_state import AuditorNode, NodeRegistry

from .claims import AggregateClaim, claim_from_data
from .commitment import CommittedDatasetStore, DatasetCommitment
from .disclosure import DisclosureState
from .models import AuditExecutionMode, ClaimType, PrivacyAuditAction
from .scheduler import PrivacyAuditActionResult, PrivacyAuditScheduler
from .primitives import CLAIM_TO_PRIMITIVE
from .process_isolated import AuditorIdentityRegistry


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
        seller_committed=None,  # P0-A：上游 SellerCommittedDataset（优先，禁止再 commit）
        dataset_commitment=None,  # P0-A：上游 canonical DatasetCommitment
        node_client_factory: Callable[[str], Any] | None = None,
        certificate_artifact=None,
        execution_mode: ExecutionMode = ExecutionMode.TEST_FIXTURE,
        auditor_identity_registry: AuditorIdentityRegistry | None = None,
        public_keys: dict[str, str] | None = None,
        allow_independent_commit: bool = False,  # TEST_ONLY: 独立运行无上游时允许本地 commit
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
        self.execution_mode = execution_mode
        self.auditor_identity_registry = auditor_identity_registry
        self.public_keys = public_keys
        self.allow_independent_commit = allow_independent_commit
        self._store = seller_store or CommittedDatasetStore("seller_private")
        self._seller = seller_committed
        self._upstream_commitment = dataset_commitment
        self._commitment: DatasetCommitment | None = None
        self._claim: AggregateClaim | None = None

    def _ensure_committed(self, tx_id: str) -> tuple[DatasetCommitment, AggregateClaim]:
        """卖方承诺候选数据 + 生成声明（交易绑定后、挑战前）。

        P0-A：若上游已提供 canonical SellerCommittedDataset / DatasetCommitment，
        直接消费，禁止再次 SellerCommittedDataset.create() 生成第二个 commitment。
        仅当独立运行（无上游）时才在本地创建唯一实例。
        """
        if self._seller is not None:
            self._commitment = self._seller.commitment
            self._claim = claim_from_data(
                claim_type=self.claim_type, X=np.asarray(self.candidate_X),
                y=np.asarray(self.candidate_y),
                dataset_commitment_hash=self._seller.commitment.commitment_hash,
            )
            return self._seller.commitment, self._claim
        if self._upstream_commitment is not None:
            self._commitment = self._upstream_commitment
            self._claim = claim_from_data(
                claim_type=self.claim_type, X=np.asarray(self.candidate_X),
                y=np.asarray(self.candidate_y),
                dataset_commitment_hash=self._upstream_commitment.commitment_hash,
            )
            return self._upstream_commitment, self._claim
        # 无上游：本地唯一创建（独立 privacy audit 运行路径）
        # 仅允许 TEST_ONLY 独立运行；production mainline 必须消费上游 canonical
        # DatasetCommitment，禁止第二条构造路径。
        if not self.allow_independent_commit:
            raise ValueError(
                "P0-A: 缺少上游 DatasetCommitment；production 不允许本地再生成 commitment。"
                "独立测试请显式 allow_independent_commit=True"
            )
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

    def _market_snapshot(self, sc, ctx):
        """AuditMarketSnapshot must come from upstream (ExperimentWorld/ctx/scenario.audit.market).

        PrivacyAuditVOIExecutor never generates bids/stake/qualified nodes itself.
        """
        from valor.audit.market_quote import AuditMarketSnapshot

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
                "AuditMarketSnapshot must be injected via ctx['market_snapshot'] "
                "or scenario.audit['market']; hardcoded bids are forbidden"
            )
        return AuditMarketSnapshot(
            snapshot_id=mkt.get("snapshot_id", "scenario-market"),
            family=mkt.get("family", "quality"),
            qualified_nodes=[str(x) for x in mkt["qualified_nodes"]],
            bids={str(k): float(v) for k, v in mkt["bids"].items()},
            min_stake=float(mkt.get("min_stake", 0.0)),
            source_kind=mkt.get("source_kind", "THREAT_SCENARIO"),
            source_ref=mkt.get("source_ref", "scenario.audit.market"),
            version=mkt.get("version", "1"),
            capability=mkt.get("capability", {}),
            stake={str(k): float(v) for k, v in mkt.get("stake", {}).items()},
            availability={str(k): float(v) for k, v in mkt.get("availability", {}).items()},
            reliability={str(k): float(v) for k, v in mkt.get("reliability", {}).items()},
            public_key_fingerprint=mkt.get("public_key_fingerprint", {}),
        )

    def _action(self, k: int) -> PrivacyAuditAction:
        primitive_id = CLAIM_TO_PRIMITIVE[self.claim_type]
        a = self.scenario.audit
        profile = AuditActionProfile(
            action_id=f"{self.claim_type.value}_CC_{k}",
            primitive_id=primitive_id,
            execution_mode=AuditExecutionMode.COMMIT_CHALLENGE.value,
            breach_family="quality",
            claim_type=self.claim_type.value,
            challenge_k=k,
            sampling_method="uniform_random",
            committee_m=self.m,
            quorum_q=self.q,
            byzantine_f=self.f,
            rho=float(a["rho"]),
            eta_b=float(a["eta_b"]),
            eta_o=float(a["eta_o"]),
            min_stake=float(a["min_stake"]),
            aggregation_rule="quorum-by-result",
            signature_requirement="REQUIRED",
            challenge_policy="rho-sampled",
            disclosure_policy="rows-fraction-bytes",
            timeout_replacement_policy="offline-replacement",
            payer="SELLER",
            trigger="BASE_LISTING",
            security_profile="COMMIT_CHALLENGE",
            decision_thresholds={
                "alpha_shift": float(a["alpha_shift"]),
                "label_error_threshold": float(a["label_error_threshold"]),
            },
            execution_version_hash=a["execution_version_hash"],
        )
        return PrivacyAuditAction(
            action_id=f"{self.claim_type.value}_CC_{k}",
            primitive_id=primitive_id,
            execution_mode=AuditExecutionMode.COMMIT_CHALLENGE,
            claim_type=self.claim_type, challenge_size=k,
            sampling_method="uniform_random",
            decision_rule_id="MULTINOMIAL_GOF",
            action_profile_hash=profile.action_profile_hash,
        )

    def run(self, sc, ctx) -> PrivacyAuditVOIResult:
        tx_id = str(ctx["binding"].tx_id)
        commitment, claim = self._ensure_committed(tx_id)

        # 披露预算（P0-H）：必须来自 AuditDisclosureBudget / 显式 audit consent。
        # 禁止从 DP privacy_budget（ε）映射行数，禁止 max_fraction=0.5 /
        # max_bytes=rows*784 隐式默认。
        budget_cfg = sc.audit.get("privacy_budget", {})
        n_rows = commitment.n_rows
        max_rows = budget_cfg.get("max_unique_rows",
                                  sc.rights.get("audit_reveal_max_rows"))
        if max_rows is None:
            raise ValueError(
                "需显式 audit_reveal_max_rows（AuditDisclosureBudget），"
                "禁止默认/DP 映射")
        max_frac = budget_cfg.get("max_fraction",
                                  sc.rights.get("audit_reveal_max_fraction"))
        if max_frac is None:
            raise ValueError("需显式 audit_reveal_max_fraction（禁止默认 0.5）")
        max_bytes = budget_cfg.get("max_bytes",
                                   sc.rights.get("audit_reveal_max_bytes"))
        if max_bytes is None:
            raise ValueError("需显式 audit_reveal_max_bytes（禁止 rows*784 默认）")
        disclosure = DisclosureState(
            dataset_commitment_hash=commitment.commitment_hash,
            max_unique_rows=int(max_rows),
            max_fraction=float(max_frac),
            max_bytes=int(max_bytes),
            _n_rows=n_rows)

        snapshot = self._market_snapshot(sc, ctx)
        registry = NodeRegistry()
        for nid in snapshot.qualified_nodes:
            registry.register(AuditorNode(
                AuditorID(nid), (snapshot.family,), 1.0, snapshot.min_stake))
        bids = {AuditorID(nid): float(b) for nid, b in snapshot.bids.items()}

        from valor.seller.audit_service import SellerAuditService
        seller_svc = SellerAuditService(dataset=self._seller, disclosure=disclosure)
        seller_svc.add_claim(claim)

        # P0-K/P0-L：真实 corruption 由 ExperimentWorld 构造。TEST_FIXTURE 仍可
        # 显式注入 tamper_openings；FORMAL/PRODUCTION 禁止读取故障 flag。
        tamper_openings = False
        if self.execution_mode == ExecutionMode.TEST_FIXTURE:
            tamper_openings = bool(sc.audit.get("tamper_openings", False))

        def _seller_open(challenge):
            opens = seller_svc.process_challenge(challenge)
            if tamper_openings and opens:
                from .canonicalize import canonical_mnist_row, canonical_row_from_payload
                from .opening import make_opening

                o = opens[0]
                idx, img, label = canonical_row_from_payload(
                    o.row_payload, index=o.index)
                img = img.copy()
                img[0] = (int(img[0]) + 1) % 256
                opens[0] = make_opening(
                    index=o.index,
                    row_payload=canonical_mnist_row(o.index, img, label),
                    salt=bytes.fromhex(o.salt), proof=o.proof)
            return opens

        # P0-F：scheduler 需要 auditor 公钥注册表。私钥只在 auditor 子进程内。
        if self.auditor_identity_registry is not None:
            public_keys = self.auditor_identity_registry.public_keys()
        elif self.public_keys is not None:
            public_keys = dict(self.public_keys)
        else:
            # fail closed: without public keys no signed evidence can be accepted
            public_keys = {}
        base_factory = self.node_client_factory
        offline_set = set()
        invalid_sig_set = set()
        if self.execution_mode == ExecutionMode.TEST_FIXTURE:
            offline_set = set(str(x) for x in sc.audit.get("offline_nodes", []))
            invalid_sig_set = set(str(x) for x in sc.audit.get("invalid_signature_nodes", []))

        # P0-F: the mechanism never signs on behalf of a node. If the transport
        # already returned signed evidence we keep it; if it is unsigned the
        # scheduler will reject it. TEST_FIXTURE may corrupt signatures to
        # exercise fail-closed paths, but only when explicitly requested.
        def _signed_client_factory(nid):
            if str(nid) in offline_set:
                raise ConnectionError(f"offline node {nid} (test scenario)")
            client = base_factory(nid) if base_factory else None
            if client is None:
                return None
            orig_submit = client.submit_task
            def _submit(task):
                ev = orig_submit(task)
                if str(nid) in invalid_sig_set:
                    ev["signature"] = "0" * 128
                return ev
            client.submit_task = _submit  # type: ignore
            return client
        self._node_clients = _signed_client_factory

        scheduler = PrivacyAuditScheduler(
            registry=registry, f=self.f, bids=bids, seller_service=seller_svc,
            node_clients=_signed_client_factory, public_keys=public_keys)

        # ---- Audit-VOI 策略循环 ----
        prior = sc.audit_prior
        belief = StateBelief.from_prior(prior["pi_b"], prior["q_l"])
        loss = LossMatrix(loss=sc.loss_matrix)

        # action catalog：k 作为不同 action（似然用校准 artifact 或默认）
        # expected_cash_cost 由市场报价产生，禁止 0.0 占位（P0-B/P0-C）。
        catalog = ActionCatalog()
        for k in self.challenge_sizes:
            lik_rows = self._likelihood_rows()
            lik = ActionLikelihood(action_id=f"a-{k}", rows=lik_rows)
            catalog.register(CertifiedAction(
                f"a-{k}", lik,
                expected_cash_cost=self._quote_cost(k, registry, bids, snapshot),
                payer="SELLER"))

        steps = []
        posterior = belief.to_plain()
        executed_any = False
        seq = 0
        for _ in range(10):
            quote_seq = seq + 1
            voi_decision_seq = seq + 2
            execution_seq = seq + 3
            seq += 3
            aid, best_voi, _ = choose_best_action(
                belief, catalog.likelihoods(), loss, catalog.costs())
            if aid is None or best_voi <= 0:
                if executed_any:
                    break
                # BASE_LISTING 基础审计至少执行一次（定价前验证承诺，Alg2）
                aid = f"a-{self.challenge_sizes[0]}"
                best_voi = 0.0
            executed_any = True
            k = int(aid.split("-")[-1])  # aid="a-64" → 64
            action = self._action(k)
            res = scheduler.run(
                action, tx_id=tx_id, commitment=commitment, claim=claim,
                disclosure=disclosure, seller_open_fn=_seller_open)
            if res.status == "ACTION_INFEASIBLE_PRIVACY_BUDGET":
                break
            if res.status != "CERTIFIED":
                break
            outcome = res.cert_result
            if outcome == "INCONCLUSIVE":
                outcome = "QUALITY_FAIL"
            if outcome not in ("PASS", "QUALITY_FAIL", "BREACH_EVIDENCE", "INCONCLUSIVE"):
                outcome = "QUALITY_FAIL"
            belief = bayes_update(belief, catalog.get(aid).likelihood.row(outcome))
            posterior = belief.to_plain()
            steps.append({
                "audit_step": len(steps) + 1, "action_id": aid, "k": k,
                "quote_seq": quote_seq, "voi_decision_seq": voi_decision_seq,
                "execution_seq": execution_seq,
                "mc_a_pay": res.mc_a_pay, "voi": best_voi,
                "outcome": outcome, "posterior_after": posterior,
                "challenge_hash": res.challenge.challenge_hash,
                "rows_revealed": len(res.challenge.indices),
                "unique_disclosure_after": disclosure.unique_disclosure,
                "cost": res.cost.to_plain(),
                "action_profile_hash": action.action_profile_hash,
                "result_counts": res.result_counts,
                "payer": "SELLER",
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

        # 逐 action 按 payer 归属（P0-B / MFC-G08）：本策略全 SELLER → 全记 seller
        audit_pay_s = sum(s["mc_a_pay"] for s in steps if s.get("payer", "SELLER") == "SELLER")
        audit_pay_b = sum(s["mc_a_pay"] for s in steps if s.get("payer", "SELLER") == "BUYER")

        return PrivacyAuditVOIResult(
            posterior=posterior, p_breach_lower_sys=p_b_lower,
            audit_pay_s=audit_pay_s, audit_pay_b=audit_pay_b,
            n_steps=len(steps), action_results=steps,
            disclosure=disclosure.to_plain(),
            action_catalog_hash=catalog.catalog_hash,
            audit_policy_hash=content_hash({"policy_id": "cc-audit"}),
        )

    def _quote_cost(self, k: int, registry, bids, snapshot) -> float:
        """对 action k 生成市场报价（Reverse VCG expected cash cost）。

        用真实 registry+bids（由上游注入），禁止 0.0 / config cost 占位（P0-B）。
        """
        m = self.m
        try:
            from valor.audit.market_quote import build_quote
            a = self.scenario.audit
            quote = build_quote(
                action_id=f"a-{k}",
                action_profile_hash=content_hash({"action": f"a-{k}", "family": "quality"}),
                snapshot=snapshot, m=m, min_stake=snapshot.min_stake,
                expected_chain_fee=float(a["chain_fee"]),
                expected_challenge_cost=float(a["challenge_cost"]),
                expected_dispute_cost=float(a["dispute_cost"]),
                quote_time="2026-01-01T00:00:00+00:00",
                quote_seq=0,
                source_kind=snapshot.source_kind,
                source_ref=snapshot.source_ref,
                version=snapshot.version,
            )
            return quote.expected_cash_cost
        except Exception:
            return float("inf")

    def _likelihood_rows(self) -> dict:
        """似然行（P6 校准后应来自 artifact；此处默认结构）。"""
        if self.certificate_artifact is not None and hasattr(
                self.certificate_artifact.data, "get"):
            return self.certificate_artifact.data.get("likelihood_rows") or self.scenario.likelihood
        return self.scenario.likelihood


__all__ = ["PrivacyAuditVOIExecutor", "PrivacyAuditVOIResult",
           "DEFAULT_CHALLENGE_SIZES"]
