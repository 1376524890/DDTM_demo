"""DistributedAuditCalibrationRunner (Round 4 P0-D).

Runs R_cal as a real distributed commit-challenge calibration:

    R_cal -> world X in {G,L,B}
          -> canonical DatasetCommitment
          -> real SellerCommittedDataset / seller service
          -> frozen AuditActionProfile
          -> real AuditMarketSnapshot
          -> PrivacyAuditScheduler with HTTP/process node clients
          -> challenge + selective openings + local signed evidence
          -> signature verification + quorum
          -> observed outcome
          -> raw calibration event

Then aggregates counts into a FrozenLikelihoodArtifact with Dirichlet posterior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from valor.audit.action_profile import AuditActionProfile
from valor.audit.likelihood_catalog import FrozenLikelihoodArtifact
from valor.core.enums import ExecutionMode
from valor.core.hashing import content_hash
from valor.core.ids import AuditorID
from valor.engine.scenario import CapstoneScenario
from valor.privacy_audit import (
    ClaimType,
    CommittedDatasetStore,
    DisclosureState,
    claim_from_data,
)
from valor.privacy_audit.models import AuditExecutionMode, PrivacyAuditAction
from valor.privacy_audit.primitives import CLAIM_TO_PRIMITIVE
from valor.privacy_audit.scheduler import PrivacyAuditScheduler
from valor.security.signing import SigningKeyPair


@dataclass
class RawCalibrationEvent:
    event_id: str
    action_profile_hash: str
    state: str
    outcome: str
    task_hash: str
    status: str
    committee: list[str] = field(default_factory=list)
    result_counts: dict = field(default_factory=dict)
    source_ref: str = ""

    def to_plain(self) -> dict:
        return {
            "event_id": self.event_id,
            "action_profile_hash": self.action_profile_hash,
            "state": self.state,
            "outcome": self.outcome,
            "task_hash": self.task_hash,
            "status": self.status,
            "committee": self.committee,
            "result_counts": self.result_counts,
            "source_ref": self.source_ref,
        }


def _action_profile(sc, k: int, f: int, claim_type: ClaimType) -> AuditActionProfile:
    a = sc.audit
    m, q = 3 * f + 1, 2 * f + 1
    return AuditActionProfile(
        action_id=f"{claim_type.value}_CC_{k}",
        primitive_id=CLAIM_TO_PRIMITIVE[claim_type],
        execution_mode=AuditExecutionMode.COMMIT_CHALLENGE.value,
        breach_family="quality",
        claim_type=claim_type.value,
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
        execution_version_hash=a["execution_version_hash"],
    )


class DistributedAuditCalibrationRunner:
    def __init__(
        self,
        *,
        scenario: CapstoneScenario,
        X: np.ndarray,
        y: np.ndarray,
        claim_type: ClaimType = ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes: list[int] | None = None,
        n_runs: int = 2,
        f: int = 2,
        seller_store: CommittedDatasetStore | None = None,
        node_client_factory: Callable[[str], Any] | None = None,
        public_keys: dict[str, str] | None = None,
        execution_mode: ExecutionMode = ExecutionMode.TEST_FIXTURE,
    ) -> None:
        self.scenario = scenario
        self.X = np.asarray(X, dtype=np.uint8)
        self.y = np.asarray(y, dtype=np.int64)
        self.claim_type = claim_type
        self.challenge_sizes = challenge_sizes or [32, 64]
        self.n_runs = n_runs
        self.f = f
        self.m, self.q = 3 * f + 1, 2 * f + 1
        self._store = seller_store or CommittedDatasetStore("seller_private")
        self.node_client_factory = node_client_factory
        self.public_keys = public_keys or {}
        self.execution_mode = execution_mode
        self.events: list[RawCalibrationEvent] = []

    def _seller(self, state: str, k: int, run: int):
        X, y = self.X, self.y
        if state == "L":
            rng = np.random.default_rng(run)
            y = y.copy()
            n = len(y)
            idx = rng.choice(n, size=max(1, int(0.05 * n)), replace=False)
            for i in idx:
                y[i] = rng.choice([c for c in range(10) if c != int(y[i])])
        from valor.seller import SellerCommittedDataset

        dataset_id = f"rcal-{state}-{k}-{run}"
        seller = SellerCommittedDataset.create(
            self._store, dataset_id=dataset_id, version="v1",
            X=X, y=y, schema_hash=content_hash({"schema": "MNIST-784"})[:64],
        )
        return seller, y

    def _run_once(self, state: str, k: int, run: int) -> RawCalibrationEvent:
        sc = self.scenario
        seller, y_committed = self._seller(state, k, run)
        claim = claim_from_data(
            claim_type=self.claim_type, X=self.X, y=y_committed,
            dataset_commitment_hash=seller.commitment.commitment_hash,
        )
        disclosure = DisclosureState(
            dataset_commitment_hash=seller.commitment.commitment_hash,
            max_unique_rows=int(sc.audit["privacy_budget"]["max_unique_rows"]),
            max_fraction=float(sc.audit["privacy_budget"]["max_fraction"]),
            max_bytes=int(sc.audit["privacy_budget"]["max_bytes"]),
            _n_rows=seller.commitment.n_rows,
        )
        profile = _action_profile(sc, k, self.f, self.claim_type)
        action = PrivacyAuditAction(
            action_id=profile.action_id,
            primitive_id=profile.primitive_id,
            execution_mode=AuditExecutionMode.COMMIT_CHALLENGE,
            claim_type=self.claim_type,
            challenge_size=k,
            sampling_method="uniform_random",
            decision_rule_id="MULTINOMIAL_GOF",
            payer="SELLER",
            trigger="BASE_LISTING",
            action_profile_hash=profile.action_profile_hash,
        )
        mkt = sc.audit["market"]
        registry = _registry_from_snapshot(mkt)
        bids = {AuditorID(nid): float(b) for nid, b in mkt["bids"].items()}
        from valor.seller.audit_service import SellerAuditService

        seller_svc = SellerAuditService(dataset=seller, disclosure=disclosure)
        seller_svc.add_claim(claim)
        scheduler = PrivacyAuditScheduler(
            registry=registry, f=self.f, bids=bids, seller_service=seller_svc,
            node_clients=self.node_client_factory, public_keys=self.public_keys,
            min_stake=float(mkt.get("min_stake", 0.0)),
        )
        res = scheduler.run(
            action, tx_id="tx-rcal", commitment=seller.commitment, claim=claim,
            disclosure=disclosure,
            task_id=f"rcal-{state}-{k}-{run}",
        )
        outcome = res.cert_result if res.status == "CERTIFIED" else res.status
        ev = RawCalibrationEvent(
            event_id=f"evt-{state}-{k}-{run}",
            action_profile_hash=profile.action_profile_hash,
            state=state,
            outcome=outcome,
            task_hash=res.task_hash,
            status=res.status,
            committee=res.committee,
            result_counts=res.result_counts,
            source_ref=f"rcal://{state}/{k}/{run}",
        )
        self.events.append(ev)
        return ev

    def run(self) -> list[RawCalibrationEvent]:
        for k in self.challenge_sizes:
            for run in range(self.n_runs):
                for state in ("G", "L", "B"):
                    self._run_once(state, k, run)
        return list(self.events)

    def freeze_likelihood(self, *, calibration_code_hash: str = "rcal-v1",
                          outcome_vocabulary_version: str = "v1") -> dict[str, FrozenLikelihoodArtifact]:
        """Aggregate CERTIFIED outcomes into per-profile FrozenLikelihoodArtifact."""
        from valor.engine.calibration import EmpiricalAuditLikelihood

        artifacts: dict[str, FrozenLikelihoodArtifact] = {}
        by_profile: dict[str, dict[str, dict[str, int]]] = {}
        for ev in self.events:
            if ev.status != "CERTIFIED":
                continue
            by_profile.setdefault(ev.action_profile_hash, {}).setdefault(
                ev.state, {o: 0 for o in ("PASS", "CLAIM_NOT_SUPPORTED",
                                           "BREACH_EVIDENCE", "INCONCLUSIVE")}
            )[ev.outcome] += 1
        for ph, state_counts in by_profile.items():
            lik = EmpiricalAuditLikelihood(action_id="rcal", breach_family="quality")
            for state, counts in state_counts.items():
                for outcome, n in counts.items():
                    for _ in range(n):
                        lik.add(state, outcome)
            action_id = self._action_id_for_profile(ph)
            artifacts[ph] = FrozenLikelihoodArtifact(
                action_profile_hash=ph,
                action_id=action_id,
                calibration_role_hash="R_cal",
                outcome_vocabulary_version=outcome_vocabulary_version,
                counts={s: {o: state_counts.get(s, {}).get(o, 0)
                            for o in ("PASS", "CLAIM_NOT_SUPPORTED",
                                       "BREACH_EVIDENCE", "INCONCLUSIVE")}
                        for s in ("G", "L", "B")},
                dirichlet_prior={o: 1.0 for o in (
                    "PASS", "CLAIM_NOT_SUPPORTED", "BREACH_EVIDENCE", "INCONCLUSIVE")},
                likelihood_rows=lik.likelihood_rows(),
                calibration_code_hash=calibration_code_hash,
                raw_event_refs=[ev.to_plain()["source_ref"] for ev in self.events
                                if ev.action_profile_hash == ph],
            )
        return artifacts

    def _action_id_for_profile(self, profile_hash: str) -> str:
        for ev in self.events:
            if ev.action_profile_hash == profile_hash:
                return f"action:{profile_hash[:12]}"
        return "unknown"


def _registry_from_snapshot(mkt: dict):
    from valor.core.ids import AuditorID
    from valor.distributed.node_state import AuditorNode, NodeRegistry

    reg = NodeRegistry()
    for nid in mkt["qualified_nodes"]:
        reg.register(AuditorNode(AuditorID(nid), ("quality",), 1.0,
                                 float(mkt.get("min_stake", 0.0))))
    return reg


__all__ = ["DistributedAuditCalibrationRunner", "RawCalibrationEvent"]
