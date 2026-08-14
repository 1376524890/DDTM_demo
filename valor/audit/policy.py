"""AuditPolicySpec 与顺序审计策略（规范 §54.3 / §50 Algorithm 2）。

认证对象必须是 rule（policy_id + action_catalog_hash + decision_rule_hash +
certified_cell_id）。策略运行：从初始信念出发，按 VOI 依次选择动作并观测
结果，直到无可行动作或 VOI≤0。
"""

from __future__ import annotations

from dataclasses import dataclass

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
