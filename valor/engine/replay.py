"""ReplayVerificationArtifact for G50 (Round 7 P0-22).

G50 must verify a real nested replay artifact, not a bool. The artifact records
semantic equality across original/replay runs and any mismatches.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass
class ReplayVerificationArtifact:
    original_run_hash: str
    replay_run_hash: str
    randomness_manifest_hash: str
    decision_equality: bool
    terminal_equality: bool
    pricing_equality: bool
    stage_semantic_hashes: dict[str, str] = field(default_factory=dict)
    money_ledger_hash: str = ""
    lineage_hash: str = ""
    commitment_equality: bool = False
    policy_certificate_hashes: dict[str, str] = field(default_factory=dict)
    quote_execution_bindings: dict[str, str] = field(default_factory=dict)
    posterior_equality: bool = False
    provenance_root_equality: bool = False
    signature_verification_results: list[dict] = field(default_factory=list)
    mismatch_list: list[str] = field(default_factory=list)
    nested_replay_status: str = "REPLAY_SKIPPED_NESTED"

    @property
    def artifact_hash(self) -> str:
        return content_hash({
            "original_run_hash": self.original_run_hash,
            "replay_run_hash": self.replay_run_hash,
            "randomness_manifest_hash": self.randomness_manifest_hash,
            "decision_equality": self.decision_equality,
            "terminal_equality": self.terminal_equality,
            "pricing_equality": self.pricing_equality,
            "stage_semantic_hashes": self.stage_semantic_hashes,
            "money_ledger_hash": self.money_ledger_hash,
            "lineage_hash": self.lineage_hash,
            "commitment_equality": self.commitment_equality,
            "policy_certificate_hashes": self.policy_certificate_hashes,
            "quote_execution_bindings": self.quote_execution_bindings,
            "posterior_equality": self.posterior_equality,
            "provenance_root_equality": self.provenance_root_equality,
            "signature_verification_results": self.signature_verification_results,
            "mismatch_list": self.mismatch_list,
            "nested_replay_status": self.nested_replay_status,
        })

    @property
    def status(self) -> str:
        if self.nested_replay_status == "REPLAY_SKIPPED_NESTED":
            return "REPLAY_SKIPPED_NESTED"
        if self.mismatch_list:
            return "FAIL"
        if not (self.decision_equality and self.terminal_equality
                and self.pricing_equality and self.commitment_equality
                and self.posterior_equality and self.provenance_root_equality):
            return "FAIL"
        return "PASS"

    def to_plain(self) -> dict:
        return {
            "original_run_hash": self.original_run_hash,
            "replay_run_hash": self.replay_run_hash,
            "randomness_manifest_hash": self.randomness_manifest_hash,
            "decision_equality": self.decision_equality,
            "terminal_equality": self.terminal_equality,
            "pricing_equality": self.pricing_equality,
            "stage_semantic_hashes": self.stage_semantic_hashes,
            "money_ledger_hash": self.money_ledger_hash,
            "lineage_hash": self.lineage_hash,
            "commitment_equality": self.commitment_equality,
            "policy_certificate_hashes": self.policy_certificate_hashes,
            "quote_execution_bindings": self.quote_execution_bindings,
            "posterior_equality": self.posterior_equality,
            "provenance_root_equality": self.provenance_root_equality,
            "signature_verification_results": self.signature_verification_results,
            "mismatch_list": self.mismatch_list,
            "nested_replay_status": self.nested_replay_status,
            "artifact_hash": self.artifact_hash,
            "status": self.status,
        }


__all__ = ["ReplayVerificationArtifact"]
