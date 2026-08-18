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


__all__ = ["AuditActionProfile"]
