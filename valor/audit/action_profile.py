"""AuditActionProfile — frozen profile for an audit action (P0-C/P0-B)."""

from __future__ import annotations

from dataclasses import dataclass

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class AuditActionProfile:
    action_id: str
    primitive_id: str
    execution_mode: str
    breach_family: str
    claim_type: str
    challenge_k: int
    sampling_method: str
    committee_m: int
    quorum_q: int
    byzantine_f: int
    rho: float
    eta_b: float
    eta_o: float
    min_stake: float
    aggregation_rule: str
    signature_requirement: str
    challenge_policy: str
    disclosure_policy: str
    timeout_replacement_policy: str
    payer: str
    trigger: str
    security_profile: str
    decision_thresholds: dict
    execution_version_hash: str

    @property
    def action_profile_hash(self) -> str:
        return content_hash(self.to_plain())

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "primitive_id": self.primitive_id,
            "execution_mode": self.execution_mode,
            "breach_family": self.breach_family,
            "claim_type": self.claim_type,
            "challenge_k": self.challenge_k,
            "sampling_method": self.sampling_method,
            "committee_m": self.committee_m,
            "quorum_q": self.quorum_q,
            "byzantine_f": self.byzantine_f,
            "rho": self.rho,
            "eta_b": self.eta_b,
            "eta_o": self.eta_o,
            "min_stake": self.min_stake,
            "aggregation_rule": self.aggregation_rule,
            "signature_requirement": self.signature_requirement,
            "challenge_policy": self.challenge_policy,
            "disclosure_policy": self.disclosure_policy,
            "timeout_replacement_policy": self.timeout_replacement_policy,
            "payer": self.payer,
            "trigger": self.trigger,
            "security_profile": self.security_profile,
            "decision_thresholds": self.decision_thresholds,
            "execution_version_hash": self.execution_version_hash,
        }


def build_action_profile(
    *,
    scenario_audit: dict,
    claim_type: str,
    k: int,
    f: int,
    execution_version_hash: str | None = None,
) -> AuditActionProfile:
    """Canonical action profile builder (Round 5 §7).

    action_id is the semantic action id (e.g. LABEL_DISTRIBUTION_CC_32); it must
    equal the action_id stored in FrozenLikelihoodArtifact and used in quotes.
    """
    from valor.privacy_audit.primitives import CLAIM_TO_PRIMITIVE

    primitive_id = CLAIM_TO_PRIMITIVE[claim_type]
    m, q = 3 * f + 1, 2 * f + 1
    a = scenario_audit
    return AuditActionProfile(
        action_id=f"{claim_type}_CC_{k}",
        primitive_id=primitive_id,
        execution_mode="COMMIT_CHALLENGE",
        breach_family="quality",
        claim_type=str(claim_type),
        challenge_k=k,
        sampling_method="uniform_random",
        committee_m=m,
        quorum_q=q,
        byzantine_f=f,
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
        execution_version_hash=(
            execution_version_hash if execution_version_hash is not None
            else str(a["execution_version_hash"])),
    )


def action_from_profile(profile: AuditActionProfile):
    """Construct a PrivacyAuditAction from a frozen AuditActionProfile."""
    from valor.privacy_audit.models import AuditExecutionMode, ClaimType, PrivacyAuditAction

    ct = ClaimType(profile.claim_type)
    return PrivacyAuditAction(
        action_id=profile.action_id,
        primitive_id=profile.primitive_id,
        execution_mode=AuditExecutionMode.COMMIT_CHALLENGE,
        claim_type=ct,
        challenge_size=profile.challenge_k,
        sampling_method=profile.sampling_method,
        decision_rule_id="MULTINOMIAL_GOF",
        payer=profile.payer,
        trigger=profile.trigger,
        action_profile_hash=profile.action_profile_hash,
    )


__all__ = ["AuditActionProfile", "build_action_profile", "action_from_profile"]
