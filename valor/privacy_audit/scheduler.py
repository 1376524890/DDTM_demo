"""PrivacyAuditScheduler —— COMMIT_CHALLENGE 隐私审计调度器（PPA-4/6）。

流程（方案 §23）：
    1. 接收 PrivacyAuditAction
    2. Reverse VCG → committee → VCG payments（MC_A^pay）
    3. 生成全局 DataOpeningChallenge（commitment 之后，不可预测）
    4. 检查 disclosure budget
    5. seller 选择性开启 rows
    6. 构造 PrivacyAuditTask，派发到 committee（auditor 只收 k 行）
    7. auditor 本地 Merkle 验证 + 抽样 primitive + 签名 evidence
    8. quorum-by-result（同一结果 ≥ q）
    9. 返回 AuditActionResult（含 cost breakdown）

复用现有 reverse_vcg / BFT 概率。auditor 不持全量数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from valor.core.hashing import content_hash
from valor.core.ids import AuditorID
from valor.market.reverse_vcg import reverse_vcg_payments
from valor.security.bft import p_live_binomial, p_safe_binomial

from .challenge import RowChallenge, generate_challenge
from .claims import AggregateClaim
from .commitment import DatasetCommitment
from .cost import AuditCostBreakdown, cost_breakdown
from .disclosure import DisclosureState
from .models import PrivacyAuditAction
from .primitives import PRIMITIVES
from .task import PrivacyAuditTask


@dataclass
class PrivacyAuditActionResult:
    action_id: str
    task_hash: str
    challenge: RowChallenge
    status: str  # CERTIFIED | NO_QUORUM | ...
    cert_result: str | None
    committee: list[str]
    payments: dict
    mc_a_pay: float
    evidence_hashes: list[str]
    result_counts: dict
    disclosure: dict
    cost: AuditCostBreakdown
    valid_signature_count: int = 0
    evidence_artifact_refs: list[str] = field(default_factory=list)

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "task_hash": self.task_hash,
            "challenge": self.challenge.to_plain(),
            "status": self.status,
            "cert_result": self.cert_result,
            "committee": self.committee,
            "payments": {str(k): v for k, v in self.payments.items()},
            "mc_a_pay": self.mc_a_pay,
            "evidence_hashes": self.evidence_hashes,
            "result_counts": self.result_counts,
            "disclosure": self.disclosure,
            "cost": self.cost.to_plain(),
            "valid_signature_count": self.valid_signature_count,
            "evidence_artifact_refs": self.evidence_artifact_refs,
        }


class PrivacyAuditScheduler:
    """COMMIT_CHALLENGE 隐私审计调度器。"""

    def __init__(
        self,
        *,
        registry,  # NodeRegistry
        f: int,
        bids: dict,
        seller_service,  # SellerAuditService
        node_clients: Callable[[str], Any] | None = None,  # node_id -> client
        min_stake: float = 0.0,
        eta_b: float = 0.0,
        eta_o: float = 0.0,
        timeout_s: float = 10.0,
        public_keys: dict[str, str] | None = None,  # node_id -> public_key_hex (P0-F)
        require_signature: bool = True,  # P0-F: production fail-closed
    ) -> None:
        self.registry = registry
        self.f = f
        self.m, self.q = 3 * f + 1, 2 * f + 1
        self.bids = bids
        self.seller = seller_service
        self.node_clients = node_clients
        self.min_stake = min_stake
        self.eta_b = eta_b
        self.eta_o = eta_o
        self.timeout_s = timeout_s
        self.public_keys = public_keys or {}
        self.require_signature = require_signature

    def _default_client(self, node_id: str):
        from .client import PrivacyAuditClient

        return PrivacyAuditClient(f"http://node/{node_id}", timeout=self.timeout_s)

    def run(
        self,
        action: PrivacyAuditAction,
        *,
        tx_id: str,
        commitment: DatasetCommitment,
        claim: AggregateClaim,
        disclosure: DisclosureState,
        task_id: str = "",
        seller_open_fn=None,  # (challenge) -> openings（测试注入；默认用 seller_service）
    ) -> PrivacyAuditActionResult:
        """执行一次 COMMIT_CHALLENGE 审计。"""
        family = "quality"
        # 1. Reverse VCG 选委员会
        payments, _cf = reverse_vcg_payments(
            self.registry, family=family, m=self.m, bids=self.bids,
            min_stake=self.min_stake)
        committee = list(payments)
        mc_a_pay = float(sum(payments.values()))

        # 2. 全局挑战（commitment 之后）
        task_binding_hash = content_hash({
            "tx_id": tx_id,
            "action_id": action.action_id,
            "commitment_hash": commitment.commitment_hash,
            "claim_hash": claim.claim_hash,
            "primitive_id": action.primitive_id,
            "execution_mode": action.execution_mode.value,
            "challenge_size": action.challenge_size,
            "sampling_method": action.sampling_method,
            "decision_rule_id": action.decision_rule_id,
            "payer": action.payer,
            "trigger": action.trigger,
            "execution_spec_hash": action.execution_spec_hash,
            "action_profile_hash": action.action_profile_hash,
        })
        challenge = generate_challenge(
            task_binding_hash=task_binding_hash, task_hash=task_binding_hash,
            action_id=action.action_id,
            n_rows=commitment.n_rows, k=action.challenge_size,
        )
        # 3. 检查披露预算
        indices = list(challenge.indices)
        if not disclosure.can_reveal(indices):
            return PrivacyAuditActionResult(
                action_id=action.action_id, task_hash=task_binding_hash,
                challenge=challenge, status="ACTION_INFEASIBLE_PRIVACY_BUDGET",
                cert_result=None, committee=committee, payments=payments,
                mc_a_pay=0.0, evidence_hashes=[], result_counts={},
                disclosure=disclosure.to_plain(), cost=cost_breakdown(
                    action_id=action.action_id, vcg_payment=0.0))

        # 4. seller 选择性开启
        openings = (
            seller_open_fn(challenge) if seller_open_fn
            else self.seller.process_challenge(challenge))

        # 5. 构造任务派发 committee
        task = PrivacyAuditTask(
            task_id=task_id or f"{task_binding_hash[:16]}-{challenge.challenge_id[:8]}",
            tx_id=tx_id, commitment=commitment, claim=claim,
            primitive_id=action.primitive_id,
            task_binding_hash=task_binding_hash,
            execution_mode=action.execution_mode, challenge=challenge,
            openings=openings)
        task_hash = task.task_hash

        evidence_plain = {}
        offline = []
        for node_id in committee:
            try:
                client = self.node_clients(node_id) if self.node_clients \
                    else self._default_client(node_id)
                evidence_plain[str(node_id)] = client.submit_task(task)
            except Exception:
                offline.append(str(node_id))

        # 6. 验签（P0-F / MFC-G05）：非法/缺失签名证据不计入 quorum。
        #    production 默认 require_signature=True：缺失公钥/签名一律 fail closed。
        #    TEST_ONLY 可显式 require_signature=False，但不得进入 paper closure。
        valid_evidence = {}
        for nid, ev in evidence_plain.items():
            pk = self.public_keys.get(str(nid))
            if self.require_signature:
                if pk is None or not ev.get("signature"):
                    continue  # INVALID_EVIDENCE_SIGNATURE → 不计入
                from valor.security.signing import verify_evidence_signature

                if not verify_evidence_signature(
                        public_key_hex=pk, evidence_plain=ev,
                        signature=ev.get("signature", "")):
                    continue  # INVALID_EVIDENCE_SIGNATURE → 不计入
            elif ev.get("signature", "") and pk is not None:
                from valor.security.signing import verify_evidence_signature

                if not verify_evidence_signature(
                        public_key_hex=pk, evidence_plain=ev,
                        signature=ev.get("signature", "")):
                    continue
            elif ev.get("signature", ""):
                continue
            valid_evidence[nid] = ev

        # 6b. quorum-by-result（只统计验签通过的证据）
        results = [e["result"] for e in valid_evidence.values()]
        counts: dict[str, int] = {}
        for r in results:
            counts[r] = counts.get(r, 0) + 1
        status, cert_result = "NO_QUORUM", None
        if evidence_plain and not valid_evidence and self.require_signature:
            status = "INVALID_EVIDENCE"
        if counts:
            cert_result = max(counts, key=counts.get)
            if counts[cert_result] >= self.q:
                status = "CERTIFIED"
        p_safe = p_safe_binomial(self.m, self.f, self.eta_b)
        p_live = p_live_binomial(self.m, self.q, self.eta_b, self.eta_o)

        # 7. 成本分解
        disclosed_bytes = sum(len(o.row_payload) for o in openings)
        cost = cost_breakdown(
            action_id=action.action_id, vcg_payment=mc_a_pay,
            bytes_seller_to_auditor=disclosed_bytes,
            rows_disclosed_unique=len(set(challenge.indices)),
        )

        return PrivacyAuditActionResult(
            action_id=action.action_id, task_hash=task_hash,
            challenge=challenge, status=status, cert_result=cert_result,
            committee=committee, payments=payments, mc_a_pay=mc_a_pay,
                evidence_hashes=[e["evidence_id"] for e in valid_evidence.values()],
                result_counts=counts, disclosure=disclosure.to_plain(), cost=cost,
                valid_signature_count=len(valid_evidence),
                evidence_artifact_refs=[e["evidence_id"] for e in valid_evidence.values()],
            )


__all__ = ["PrivacyAuditScheduler", "PrivacyAuditActionResult"]
