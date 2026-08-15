"""VALOR Privacy-Preserving Commit-and-Challenge Distributed Audit。

核心抽象（方案 §42 的七个对象）：
    DatasetCommitment + AggregateClaim + PrivacyAuditAction +
    RowChallenge + RowOpening + PrivacyAuditEvidence + DisclosureState

只负责产生 Evidence 与 MC_A^pay（及校准后 Λ_j），不改变原主链经济机制。
正式 MNIST 默认 AuditExecutionMode.COMMIT_CHALLENGE。
"""

from __future__ import annotations

from .models import (
    AuditExecutionMode,
    ClaimType,
    DecisionRule,
    PrimitiveResult,
    PrivacyAuditAction,
)
from .canonicalize import (
    MNIST_FLAT,
    MNIST_H,
    MNIST_W,
    canonical_mnist_row,
    canonical_row_from_payload,
)
from .merkle import MerkleProof, MerkleSibling, MerkleTree, leaf_hash
from .commitment import (
    CommittedDatasetStore,
    CommittedRow,
    DatasetCommitment,
    build_dataset_commitment,
)
from .claims import AggregateClaim, claim_from_data, make_claim
from .challenge import RowChallenge, generate_challenge, validate_challenge_indices
from .opening import RowOpening, make_opening, verify_opening
from .disclosure import (
    DisclosureState,
    PrivacyBudgetExceededError,
    budget_from_rights,
)
from .cost import AuditCostBreakdown, cost_breakdown
from .evidence import PrivacyAuditEvidence, build_evidence
from .primitives import PrimitiveOutput, run_primitive
from .verifier import AuditExecutionContext, CommitChallengeVerifier

__all__ = [
    "AuditExecutionMode", "ClaimType", "DecisionRule", "PrimitiveResult",
    "PrivacyAuditAction",
    "MNIST_FLAT", "MNIST_H", "MNIST_W",
    "canonical_mnist_row", "canonical_row_from_payload",
    "MerkleProof", "MerkleSibling", "MerkleTree", "leaf_hash",
    "CommittedDatasetStore", "CommittedRow", "DatasetCommitment",
    "build_dataset_commitment",
    "AggregateClaim", "claim_from_data", "make_claim",
    "RowChallenge", "generate_challenge", "validate_challenge_indices",
    "RowOpening", "make_opening", "verify_opening",
    "DisclosureState", "PrivacyBudgetExceededError", "budget_from_rights",
    "AuditCostBreakdown", "cost_breakdown",
    "PrivacyAuditEvidence", "build_evidence",
    "PrimitiveOutput", "run_primitive",
    "AuditExecutionContext", "CommitChallengeVerifier",
]
