"""SellerAuditService —— 卖方审计服务（PPA-2/5 集成）。

协调：承诺 → 声明 → 挑战 → 选择性开启 → 披露预算记录。
所有对 auditor 的输出只含 openings（k 行），不含全量数据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.privacy_audit.challenge import RowChallenge, validate_challenge_indices
from valor.privacy_audit.claims import AggregateClaim, claim_from_data
from valor.privacy_audit.commitment import DatasetCommitment
from valor.privacy_audit.disclosure import DisclosureState
from valor.privacy_audit.opening import RowOpening

from .committed_dataset import SellerCommittedDataset


@dataclass
class SellerAuditService:
    """卖方审计服务：承诺 + 声明 + 开启 + 披露预算。"""

    dataset: SellerCommittedDataset
    disclosure: DisclosureState
    claims: dict[str, AggregateClaim] = field(default_factory=dict)

    @property
    def commitment(self) -> DatasetCommitment:
        return self.dataset.commitment

    def add_claim(self, claim: AggregateClaim) -> None:
        self.claims[claim.claim_id] = claim

    def build_claim_from_data(
        self, *, claim_type, algorithm_spec_hash: str = "",
    ) -> AggregateClaim:
        """在明文数据上计算声明值并注册。"""
        claim = claim_from_data(
            claim_type=claim_type, X=self.dataset._store._datasets[
                self.dataset.dataset_id]["X"],
            y=self.dataset._store._datasets[self.dataset.dataset_id]["y"],
            dataset_commitment_hash=self.commitment.commitment_hash,
            algorithm_spec_hash=algorithm_spec_hash,
        )
        self.add_claim(claim)
        return claim

    def get_claim(self, claim_id: str) -> AggregateClaim:
        return self.claims[claim_id]

    def process_challenge(self, challenge: RowChallenge) -> list[RowOpening]:
        """校验挑战 → 检查披露预算 → 选择性开启。

        挑战 indices 必须有效（唯一、界内、len=k）且不超预算。
        """
        if not validate_challenge_indices(challenge, self.commitment.n_rows):
            raise ValueError("challenge indices 非法")
        indices = list(challenge.indices)
        if not self.disclosure.can_reveal(indices):
            from valor.privacy_audit.disclosure import PrivacyBudgetExceededError

            raise PrivacyBudgetExceededError(
                "隐私预算不足（ACTION_INFEASIBLE_PRIVACY_BUDGET）")
        openings = self.dataset.open_rows(indices)
        # 记录披露（字节 = 每行 canonical payload 长度）
        bytes_count = sum(len(o.row_payload) for o in openings)
        self.disclosure.record(indices, bytes_count)
        return openings

    def to_plain(self) -> dict:
        return {
            "commitment": self.commitment.public_artifact(),
            "disclosure": self.disclosure.to_plain(),
            "claims": {k: v.to_plain() for k, v in self.claims.items()},
        }


__all__ = ["SellerAuditService"]
