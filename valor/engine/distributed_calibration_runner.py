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
from valor.audit.action_profile import build_action_profile, action_from_profile
from valor.audit.likelihood_catalog import FrozenLikelihoodArtifact
from valor.core.enums import ExecutionMode
from valor.core.hashing import content_hash
from valor.core.ids import AuditorID
from valor.engine.scenario import CapstoneScenario
from valor.experiments.registry import DataRoleManifest
from valor.privacy_audit import (
    ClaimType,
    CommittedDatasetStore,
    DisclosureState,
    claim_from_data,
)
from valor.privacy_audit.process_isolated import AuditRuntimeDescriptor
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
    calibration_run_id: str = ""
    world_id: str = ""
    world_ground_truth_ref: str = ""
    role_manifest_hash: str = ""
    action_id: str = ""
    action_profile_hash_full: str = ""
    market_snapshot_hash: str = ""
    quote_hash: str = ""
    task_binding_hash: str = ""
    challenge_hash: str = ""
    evidence_artifact_refs: list[str] = field(default_factory=list)
    valid_signature_count: int = 0
    final_outcome: str = ""
    disclosure: dict = field(default_factory=dict)
    execution_runtime_hash: str = ""
    raw_event_artifact_hash: str = ""

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
            "calibration_run_id": self.calibration_run_id,
            "world_id": self.world_id,
            "world_ground_truth_ref": self.world_ground_truth_ref,
            "role_manifest_hash": self.role_manifest_hash,
            "action_id": self.action_id,
            "action_profile_hash_full": self.action_profile_hash_full,
            "market_snapshot_hash": self.market_snapshot_hash,
            "quote_hash": self.quote_hash,
            "task_binding_hash": self.task_binding_hash,
            "challenge_hash": self.challenge_hash,
            "evidence_artifact_refs": self.evidence_artifact_refs,
            "valid_signature_count": self.valid_signature_count,
            "final_outcome": self.final_outcome,
            "disclosure": self.disclosure,
            "execution_runtime_hash": self.execution_runtime_hash,
            "raw_event_artifact_hash": self.raw_event_artifact_hash,
        }


def _action_profile(sc, k: int, f: int, claim_type: ClaimType) -> AuditActionProfile:
    return build_action_profile(
        scenario_audit=sc.audit,
        claim_type=claim_type.value,
        k=k, f=f,
        execution_version_hash=str(sc.audit.get("execution_version_hash", "cc-audit-v1")),
    )


class DistributedAuditCalibrationRunner:
    def __init__(
        self,
        *,
        scenario: CapstoneScenario,
        X: np.ndarray,
        y: np.ndarray,
        role_manifest: DataRoleManifest | None = None,
        claim_type: ClaimType = ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes: list[int] | None = None,
        n_runs: int = 2,
        f: int = 2,
        seller_store: CommittedDatasetStore | None = None,
        node_client_factory: Callable[[str], Any] | None = None,
        public_keys: dict[str, str] | None = None,
        execution_mode: ExecutionMode = ExecutionMode.TEST_FIXTURE,
        role: str = "rcal",
        audit_runtime: AuditRuntimeDescriptor | None = None,
    ) -> None:
        self.scenario = scenario
        full_X = np.asarray(X, dtype=np.uint8)
        full_y = np.asarray(y, dtype=np.int64)
        self.role_manifest = role_manifest
        if role_manifest is not None:
            self.role = role_manifest.role_id
            self._sample_ids = sorted(int(x) for x in role_manifest.sample_ids)
            if self._sample_ids and max(self._sample_ids) >= len(full_X):
                raise ValueError("role_manifest.sample_ids out of bounds for X")
            self.X = full_X[self._sample_ids]
            self.y = full_y[self._sample_ids]
        else:
            self.role = role
            self.X = full_X
            self.y = full_y
            self._sample_ids = list(range(len(self.X)))
        self.claim_type = claim_type
        self.challenge_sizes = challenge_sizes or [32, 64]
        self.n_runs = n_runs
        self.f = f
        self.m, self.q = 3 * f + 1, 2 * f + 1
        self._store = seller_store or CommittedDatasetStore("seller_private")
        self.node_client_factory = node_client_factory
        self.public_keys = public_keys or {}
        self.execution_mode = execution_mode
        self.audit_runtime = audit_runtime
        if execution_mode == ExecutionMode.FORMAL_EXPERIMENT:
            if audit_runtime is None or audit_runtime.transport_mode != "PROCESS_HTTP" or not audit_runtime.process_isolated:
                raise ValueError("FORMAL_AUDIT_RUNTIME_REQUIRED: FORMAL_EXPERIMENT requires ProcessHttpAuditorCluster")
        if role_manifest is None:
            self.role = role
        self._breach_family = ""
        self.events: list[RawCalibrationEvent] = []

    def _seller(self, state: str, k: int, run: int):
        from valor.engine.experiment_world import build_experiment_world

        world = build_experiment_world(
            scenario=self.scenario, store=self._store,
            X=self.X, y=self.y, role_id=self.role,
            state=state, k=k, run=run,
        )
        self._breach_family = world.breach_family
        return world.seller, world.y_committed

    def _run_once(self, state: str, k: int, run: int) -> RawCalibrationEvent:
        sc = self.scenario
        world_id = f"{self.role}-{state}-{k}-{run}"
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
        action = action_from_profile(profile)
        mkt = sc.audit["market"]
        registry = _registry_from_snapshot(mkt)
        bids = {AuditorID(nid): float(b) for nid, b in mkt["bids"].items()}
        from valor.audit.market_quote import AuditMarketSnapshot, build_quote

        snapshot = AuditMarketSnapshot(
            snapshot_id=mkt.get("snapshot_id", f"cal-{world_id}"),
            family=mkt.get("family", "quality"),
            qualified_nodes=[str(x) for x in mkt["qualified_nodes"]],
            bids={str(k2): float(v) for k2, v in mkt["bids"].items()},
            min_stake=float(mkt.get("min_stake", 0.0)),
            source_kind=mkt.get("source_kind", "THREAT_SCENARIO"),
            source_ref=mkt.get("source_ref", "scenario.audit.market"),
            version=mkt.get("version", "1"),
        )
        quote = build_quote(
            action_id=profile.action_id,
            action_profile_hash=profile.action_profile_hash,
            snapshot=snapshot, m=self.m, min_stake=snapshot.min_stake,
            expected_chain_fee=float(sc.audit.get("chain_fee", 0.0)),
            expected_challenge_cost=float(sc.audit.get("challenge_cost", 0.0)),
            expected_dispute_cost=float(sc.audit.get("dispute_cost", 0.0)),
            quote_time="",
            quote_seq=1,
            source_kind=snapshot.source_kind,
            source_ref=snapshot.source_ref,
            version=snapshot.version,
        )
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
            task_id=f"{self.role}-{state}-{k}-{run}",
        )
        outcome = res.cert_result if res.status == "CERTIFIED" else res.status
        ev = RawCalibrationEvent(
            event_id=f"evt-{world_id}",
            action_profile_hash=profile.action_profile_hash,
            state=state,
            outcome=outcome,
            task_hash=res.task_hash,
            status=res.status,
            committee=[str(x) for x in res.committee],
            result_counts=res.result_counts,
            source_ref=f"rcal://{world_id}",
            calibration_run_id=f"run-{self.role}-{k}-{run}",
            world_id=world_id,
            world_ground_truth_ref=(
                sc.audit.get("breach_world", {}).get("ground_truth_ref", "")
                if state == "B" else
                sc.audit.get("low_suitability_world", {}).get("ground_truth_ref", "")
                if state == "L" else "seller_honest_authentic_suitable"),
            role_manifest_hash=(
                self.role_manifest.role_manifest_hash
                if self.role_manifest is not None else ""),
            action_id=profile.action_id,
            action_profile_hash_full=profile.action_profile_hash,
            market_snapshot_hash=snapshot.snapshot_hash,
            quote_hash=quote.quote_hash,
            challenge_hash=res.challenge.challenge_hash if res.challenge else "",
            evidence_artifact_refs=getattr(res, "evidence_artifact_refs", []),
            valid_signature_count=getattr(res, "valid_signature_count", 0),
            final_outcome=outcome,
            disclosure=disclosure.to_plain() if hasattr(disclosure, "to_plain") else {},
            execution_runtime_hash=(
                content_hash(self.audit_runtime.to_plain())
                if self.audit_runtime is not None else
                content_hash({
                    "transport_mode": "TEST_FIXTURE"
                    if self.execution_mode == ExecutionMode.TEST_FIXTURE
                    else "PROCESS_HTTP",
                    "process_isolated": self.execution_mode
                    != ExecutionMode.TEST_FIXTURE,
                    "node_local_ed25519": self.execution_mode
                    != ExecutionMode.TEST_FIXTURE,
                })
            ),
        )
        ev.raw_event_artifact_hash = content_hash(ev.to_plain())
        self.events.append(ev)
        self._persist_raw_event(ev)
        return ev

    def _persist_raw_event(self, ev: RawCalibrationEvent) -> None:
        from pathlib import Path

        out = Path("reports/calibration/raw_events")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{ev.event_id}.json").write_text(
            __import__("json").dumps(ev.to_plain(), ensure_ascii=False, indent=2),
            encoding="utf-8")

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
                calibration_role_hash=(
                    self.role_manifest.role_manifest_hash
                    if self.role_manifest is not None else "R_cal"),
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
                return ev.action_id
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
