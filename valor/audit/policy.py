"""AuditPolicySpec 与顺序审计策略（规范 §54.3 / §50 Algorithm 2）。

认证对象必须是 rule（policy_id + action_catalog_hash + decision_rule_hash +
certified_cell_id）。策略运行：从初始信念出发，按 VOI 依次选择动作并观测
结果，直到无可行动作或 VOI≤0。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from valor.core.hashing import content_hash

from .action_catalog import ActionCatalog
from .loss import LossMatrix
from .state_model import StateBelief
from .trace import AuditStep, AuditTrace
from .voi import choose_best_action, marginal_value_of_audit


@dataclass(frozen=True)
class AuditPolicySpec:
    """认证策略 rule（§54.3）。"""

    policy_id: str
    action_catalog_hash: str
    decision_rule_hash: str
    certified_cell_id: str

    def to_plain(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "action_catalog_hash": self.action_catalog_hash,
            "decision_rule_hash": self.decision_rule_hash,
            "certified_cell_id": self.certified_cell_id,
        }


@dataclass(frozen=True)
class AuditPolicy:
    """Full semantic AuditPolicy (Round 4 §6)."""

    policy_version: str
    action_profile_hashes: tuple[str, ...]
    likelihood_artifact_hashes: tuple[str, ...]
    selection_algorithm_version: str
    prior_family_version: str
    loss_matrix_hash: str
    stop_rule: str
    mandatory_base_audit_policy: str
    disclosure_policy: str
    market_quote_policy: str
    payer_policy: str
    evidence_verification_policy: str
    quorum_policy: str
    replacement_policy: str
    certificate_requirements: str

    @property
    def policy_hash(self) -> str:
        return content_hash({
            "policy_version": self.policy_version,
            "action_profile_hashes": sorted(self.action_profile_hashes),
            "likelihood_artifact_hashes": sorted(self.likelihood_artifact_hashes),
            "selection_algorithm_version": self.selection_algorithm_version,
            "prior_family_version": self.prior_family_version,
            "loss_matrix_hash": self.loss_matrix_hash,
            "stop_rule": self.stop_rule,
            "mandatory_base_audit_policy": self.mandatory_base_audit_policy,
            "disclosure_policy": self.disclosure_policy,
            "market_quote_policy": self.market_quote_policy,
            "payer_policy": self.payer_policy,
            "evidence_verification_policy": self.evidence_verification_policy,
            "quorum_policy": self.quorum_policy,
            "replacement_policy": self.replacement_policy,
            "certificate_requirements": self.certificate_requirements,
        })

    def to_plain(self) -> dict:
        return {
            "policy_version": self.policy_version,
            "action_profile_hashes": list(self.action_profile_hashes),
            "likelihood_artifact_hashes": list(self.likelihood_artifact_hashes),
            "selection_algorithm_version": self.selection_algorithm_version,
            "prior_family_version": self.prior_family_version,
            "loss_matrix_hash": self.loss_matrix_hash,
            "stop_rule": self.stop_rule,
            "mandatory_base_audit_policy": self.mandatory_base_audit_policy,
            "disclosure_policy": self.disclosure_policy,
            "market_quote_policy": self.market_quote_policy,
            "payer_policy": self.payer_policy,
            "evidence_verification_policy": self.evidence_verification_policy,
            "quorum_policy": self.quorum_policy,
            "replacement_policy": self.replacement_policy,
            "certificate_requirements": self.certificate_requirements,
            "policy_hash": self.policy_hash,
        }


def run_policy(
    *,
    tx_id: str,
    initial_belief: StateBelief,
    catalog: ActionCatalog,
    loss: LossMatrix,
    observer,  # 观测函数：action_id -> outcome
) -> AuditTrace:
    """执行顺序 Audit-VOI 策略（Algorithm 2 骨架）。

    observer: callable(action_id) -> outcome 字符串（由分布式审计提供）。
    """
    belief = initial_belief
    steps: list[AuditStep] = []
    for _ in range(50):  # 步数上限防死循环
        action_id, best_voi, _ = choose_best_action(
            belief, catalog.likelihoods(), loss, catalog.costs()
        )
        if action_id is None or best_voi <= 0:
            break
        action = catalog.get(action_id)
        outcome = observer(action_id)
        lik = action.likelihood
        mv, _ = marginal_value_of_audit(belief, lik, loss)
        # 更新信念
        from .bayes_update import bayes_update

        belief = bayes_update(belief, lik.row(outcome))
        steps.append(AuditStep(
            action_id=action_id, observed_outcome=outcome,
            posterior=belief.to_plain(), mv=mv, voi=best_voi,
            cost_paid=action.expected_cash_cost,
        ))
    return AuditTrace(tx_id=tx_id, steps=tuple(steps))
