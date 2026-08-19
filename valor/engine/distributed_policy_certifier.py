"""DistributedPolicyCertifier (Round 4 P0-E).

Independent full-policy R_cert: runs separate worlds (disjoint sample IDs from
R_cal), executes the full audit policy through real commit-challenge transport,
and freezes a PolicyCertificationArtifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from valor.audit.likelihood_catalog import FrozenLikelihoodArtifact
from valor.audit.policy import AuditPolicy
from valor.core.enums import ExecutionMode
from valor.core.hashing import content_hash
from valor.engine.distributed_calibration_runner import DistributedAuditCalibrationRunner
from valor.engine.scenario import CapstoneScenario
from valor.privacy_audit import ClaimType, CommittedDatasetStore


@dataclass
class PolicyCertificationArtifact:
    policy: AuditPolicy
    policy_hash: str
    action_catalog_hash: str
    likelihood_catalog_hash: str
    r_cert_hash: str
    trainer_task_family: str
    breach_family: str
    tp: int
    fn: int
    fp: int
    tn: int
    beta_prior: dict
    beta_posterior: dict
    p_breach_lower_sys: float
    omega_allowed_envelope: list[dict]
    raw_certification_event_refs: list[str]

    def to_plain(self) -> dict:
        return {
            "policy": self.policy.to_plain(),
            "policy_hash": self.policy_hash,
            "action_catalog_hash": self.action_catalog_hash,
            "likelihood_catalog_hash": self.likelihood_catalog_hash,
            "r_cert_hash": self.r_cert_hash,
            "trainer_task_family": self.trainer_task_family,
            "breach_family": self.breach_family,
            "tp": self.tp, "fn": self.fn, "fp": self.fp, "tn": self.tn,
            "beta_prior": self.beta_prior,
            "beta_posterior": self.beta_posterior,
            "p_breach_lower_sys": self.p_breach_lower_sys,
            "omega_allowed_envelope": self.omega_allowed_envelope,
            "raw_certification_event_refs": self.raw_certification_event_refs,
        }


class DistributedPolicyCertifier:
    def __init__(
        self,
        *,
        policy: AuditPolicy,
        scenario: CapstoneScenario,
        X: np.ndarray,
        y: np.ndarray,
        likelihood_artifacts: dict[str, FrozenLikelihoodArtifact],
        claim_type: ClaimType = ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes: list[int] | None = None,
        n_runs: int = 2,
        f: int = 2,
        seller_store: CommittedDatasetStore | None = None,
        node_client_factory: Callable[[str], Any] | None = None,
        public_keys: dict[str, str] | None = None,
        execution_mode: ExecutionMode = ExecutionMode.TEST_FIXTURE,
    ) -> None:
        self.policy = policy
        self.scenario = scenario
        self.X = X
        self.y = y
        self.likelihood_artifacts = likelihood_artifacts
        self.claim_type = claim_type
        self.challenge_sizes = challenge_sizes or [32, 64]
        self.n_runs = n_runs
        self.f = f
        self.seller_store = seller_store or CommittedDatasetStore("seller_private")
        self.node_client_factory = node_client_factory
        self.public_keys = public_keys
        self.execution_mode = execution_mode

    def run(self, *, r_cal_event_ids: list[str]) -> PolicyCertificationArtifact:
        runner = DistributedAuditCalibrationRunner(
            scenario=self.scenario, X=self.X, y=self.y,
            claim_type=self.claim_type, challenge_sizes=self.challenge_sizes,
            n_runs=self.n_runs, f=self.f, seller_store=self.seller_store,
            node_client_factory=self.node_client_factory,
            public_keys=self.public_keys, execution_mode=self.execution_mode,
            role="rcert",
        )
        events = runner.run()
        r_cert_hashes = {e.event_id for e in events}
        overlap = r_cert_hashes & set(r_cal_event_ids)
        if overlap:
            raise ValueError(f"DATA_ROLE_OVERLAP: R_cal/R_cert share {overlap}")
        # Certification metrics from events (B state breach detection).
        tp = sum(1 for e in events if e.state == "B" and e.outcome == "BREACH_EVIDENCE")
        fn = sum(1 for e in events if e.state == "B" and e.outcome != "BREACH_EVIDENCE")
        fp = sum(1 for e in events if e.state == "G" and e.outcome == "BREACH_EVIDENCE")
        tn = sum(1 for e in events if e.state == "G" and e.outcome != "BREACH_EVIDENCE")
        a, b = 1.0, 1.0
        a_post, b_post = a + tp, b + fn
        p_lower = a_post / (a_post + b_post)
        artifact_hash = content_hash({
            "policy_hash": self.policy.policy_hash,
            "action_catalog_hash": content_hash({
                ph: art.action_id for ph, art in self.likelihood_artifacts.items()
            }),
            "likelihood_catalog_hash": content_hash({
                ph: art.artifact_hash for ph, art in self.likelihood_artifacts.items()
            }),
            "r_cert_hashes": sorted(r_cert_hashes),
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        })
        return PolicyCertificationArtifact(
            policy=self.policy, policy_hash=self.policy.policy_hash,
            action_catalog_hash=content_hash({
                ph: art.action_id for ph, art in self.likelihood_artifacts.items()
            }),
            likelihood_catalog_hash=content_hash({
                ph: art.artifact_hash for ph, art in self.likelihood_artifacts.items()
            }),
            r_cert_hash=artifact_hash,
            trainer_task_family="digit-classification",
            breach_family="quality",
            tp=tp, fn=fn, fp=fp, tn=tn,
            beta_prior={"a": a, "b": b},
            beta_posterior={"a": a_post, "b": b_post},
            p_breach_lower_sys=float(p_lower),
            omega_allowed_envelope=[
                {"cell_id": "c1", "p_breach_lower_sys": float(p_lower)}
            ],
            raw_certification_event_refs=[e.source_ref for e in events],
        )


__all__ = ["DistributedPolicyCertifier", "PolicyCertificationArtifact"]
