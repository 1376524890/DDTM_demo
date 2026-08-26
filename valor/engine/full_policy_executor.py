"""FullAuditPolicyExecutor (Round 5 §11).

Executes the complete frozen AuditPolicy for R_cert worlds:

    Frozen Market Snapshot
      -> quote all eligible actions
      -> likelihood lookup
      -> VOI selection
      -> chosen action
      -> challenge
      -> signed evidence
      -> quorum
      -> posterior
      -> continue / stop
      -> replacement if applicable
      -> final policy decision

R_cert must certify Π_A (the whole policy), not a single primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from valor.audit.action_catalog import ActionProfileCatalog
from valor.audit.likelihood_catalog import LikelihoodCatalog
from valor.audit.policy import AuditPolicy
from valor.core.enums import ExecutionMode
from valor.core.hashing import content_hash
from valor.engine.experiment_world import build_experiment_world
from valor.engine.scenario import CapstoneScenario
from valor.experiments.registry import DataRoleManifest
from valor.privacy_audit import ClaimType, CommittedDatasetStore
from valor.privacy_audit.process_isolated import AuditRuntimeDescriptor
from valor.privacy_audit.voi import PrivacyAuditVOIExecutor


class AuditPolicyExecutionStatus:
    CERTIFIED = "CERTIFIED"
    POLICY_STOP = "POLICY_STOP"
    NO_QUORUM = "NO_QUORUM"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    ACTION_NOT_CERTIFIED = "ACTION_NOT_CERTIFIED"
    ACTION_INFEASIBLE_DISCLOSURE = "ACTION_INFEASIBLE_DISCLOSURE"
    MARKET_INFEASIBLE = "MARKET_INFEASIBLE"
    POLICY_ERROR = "POLICY_ERROR"


@dataclass
class AuditAttemptRecord:
    attempt_id: str
    world_id: str
    state: str
    action_id: str
    action_profile_hash: str
    quote_hash: str
    status: str
    outcome: str | None
    committee: list[str] = field(default_factory=list)
    result_counts: dict = field(default_factory=dict)
    valid_signature_count: int = 0
    evidence_artifact_refs: list[str] = field(default_factory=list)
    posterior_after: dict = field(default_factory=dict)
    execution_runtime_hash: str = ""

    def to_plain(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "world_id": self.world_id,
            "state": self.state,
            "action_id": self.action_id,
            "action_profile_hash": self.action_profile_hash,
            "quote_hash": self.quote_hash,
            "status": self.status,
            "outcome": self.outcome,
            "committee": self.committee,
            "result_counts": self.result_counts,
            "valid_signature_count": self.valid_signature_count,
            "evidence_artifact_refs": self.evidence_artifact_refs,
            "posterior_after": self.posterior_after,
            "execution_runtime_hash": self.execution_runtime_hash,
        }


@dataclass
class PolicyWorldResult:
    world_id: str
    state: str
    ground_truth_ref: str
    policy_status: str
    posterior: dict
    p_breach_lower_sys: float
    audit_pay_s: float
    audit_pay_b: float
    attempts: list[AuditAttemptRecord] = field(default_factory=list)
    raw_event_hashes: list[str] = field(default_factory=list)

    def to_plain(self) -> dict:
        return {
            "world_id": self.world_id,
            "state": self.state,
            "ground_truth_ref": self.ground_truth_ref,
            "policy_status": self.policy_status,
            "posterior": self.posterior,
            "p_breach_lower_sys": self.p_breach_lower_sys,
            "audit_pay_s": self.audit_pay_s,
            "audit_pay_b": self.audit_pay_b,
            "attempts": [a.to_plain() for a in self.attempts],
            "raw_event_hashes": self.raw_event_hashes,
        }


class FullAuditPolicyExecutor:
    """Independent full-policy executor for R_cert worlds."""

    def __init__(
        self,
        *,
        policy: AuditPolicy,
        scenario: CapstoneScenario,
        X: np.ndarray,
        y: np.ndarray,
        role_manifest: DataRoleManifest | None = None,
        likelihood_catalog: LikelihoodCatalog | None = None,
        action_profile_catalog: ActionProfileCatalog | None = None,
        claim_type: ClaimType = ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes: list[int] | None = None,
        f: int = 2,
        n_runs: int = 1,
        seller_store: CommittedDatasetStore | None = None,
        node_client_factory: Callable[[str], Any] | None = None,
        public_keys: dict[str, str] | None = None,
        execution_mode: ExecutionMode = ExecutionMode.TEST_FIXTURE,
        audit_runtime: AuditRuntimeDescriptor | None = None,
        role_registry=None,
        market_provider=None,
    ) -> None:
        if n_runs < 1:
            raise ValueError("R_cert n_runs must be >= 1")
        self.policy = policy
        self.n_runs = n_runs
        self.scenario = scenario
        self.role_manifest = role_manifest
        self.likelihood_catalog = likelihood_catalog
        self.action_profile_catalog = action_profile_catalog
        self.claim_type = claim_type
        self.challenge_sizes = challenge_sizes or [32, 64]
        self.f = f
        self.seller_store = seller_store or CommittedDatasetStore("seller_private")
        self.node_client_factory = node_client_factory
        self.public_keys = public_keys or {}
        self.execution_mode = execution_mode
        self.audit_runtime = audit_runtime
        self.role_registry = role_registry
        self.market_provider = market_provider

        full_X = np.asarray(X, dtype=np.uint8)
        full_y = np.asarray(y, dtype=np.int64)
        if role_manifest is not None:
            idx = sorted(int(x) for x in role_manifest.sample_ids)
            if idx and max(idx) >= len(full_X):
                raise ValueError("role_manifest.sample_ids out of bounds for X")
            self.X = full_X[idx]
            self.y = full_y[idx]
            self.role_id = role_manifest.role_id
        else:
            self.X = full_X
            self.y = full_y
            self.role_id = "R_cert"

    def run(self) -> list[PolicyWorldResult]:
        if self.execution_mode == ExecutionMode.FORMAL_EXPERIMENT:
            if self.audit_runtime is None or self.audit_runtime.transport_mode != "PROCESS_HTTP" or not self.audit_runtime.process_isolated:
                raise ValueError("FORMAL_AUDIT_RUNTIME_REQUIRED")
        if self.execution_mode == ExecutionMode.PRODUCTION:
            if self.audit_runtime is None or self.audit_runtime.transport_mode != "PRODUCTION":
                raise ValueError("PRODUCTION_AUDIT_RUNTIME_REQUIRED")
        if not self.policy.action_profile_hashes:
            raise ValueError("AUDIT_POLICY_EMPTY: policy.action_profile_hashes must be non-empty")
        if not self.policy.likelihood_artifact_hashes:
            raise ValueError("AUDIT_POLICY_EMPTY: policy.likelihood_artifact_hashes must be non-empty")

        results: list[PolicyWorldResult] = []
        k = self.challenge_sizes[0]
        for state in ("G", "L", "B"):
            for run in range(self.n_runs):
                world = build_experiment_world(
                    scenario=self.scenario, store=self.seller_store,
                    X=self.X, y=self.y, role_id=self.role_id,
                    state=state, k=k, run=run,
                )
                world_id = f"{self.role_id}-{state}-{k}-{run}"
                res = self._run_world(state, world, world_id, k)
                results.append(res)
        return results

    def _run_world(self, state: str, world, world_id: str, k: int) -> PolicyWorldResult:
        sc = self.scenario
        ctx = {
            "binding": type("B", (), {"tx_id": f"tx-{world_id}"})(),
            "market_snapshot": self._snapshot(world_id),
        }
        ex = PrivacyAuditVOIExecutor(
            scenario=sc,
            candidate_X=self.X,
            candidate_y=world.y_committed,
            claim_type=self.claim_type,
            challenge_sizes=self.challenge_sizes,
            f=self.f,
            seller_store=self.seller_store,
            seller_committed=world.seller,
            dataset_commitment=world.seller.commitment,
            node_client_factory=self.node_client_factory,
            likelihood_catalog=self.likelihood_catalog,
            action_profile_catalog=self.action_profile_catalog,
            execution_mode=self.execution_mode,
            public_keys=self.public_keys,
            audit_runtime=self.audit_runtime,
            market_provider=self.market_provider,
            audit_policy=self.policy,
            role_registry=self.role_registry,
        )
        result = ex.run(sc, ctx)
        attempts: list[AuditAttemptRecord] = []
        for step in result.action_results:
            attempts.append(AuditAttemptRecord(
                attempt_id=f"att-{world_id}-{step.get('audit_step', 0)}",
                world_id=world_id, state=state,
                action_id=step.get("action_id", ""),
                action_profile_hash=step.get("action_profile_hash", ""),
                quote_hash=step.get("quote_hash", ""),
                status=step.get("status", result.audit_policy_status),
                outcome=step.get("outcome"),
                committee=step.get("committee", []),
                result_counts=step.get("result_counts", {}),
                valid_signature_count=step.get("valid_signature_count", 0),
                evidence_artifact_refs=step.get("evidence_artifact_refs", []),
                posterior_after=step.get("posterior_after", {}),
                execution_runtime_hash=(
                    content_hash(self.audit_runtime.to_plain())
                    if self.audit_runtime is not None else ""),
            ))
        if not attempts:
            status = AuditPolicyExecutionStatus.POLICY_ERROR
        elif any(a.status == "CERTIFIED" for a in attempts):
            status = AuditPolicyExecutionStatus.CERTIFIED
        elif any(a.status == "INVALID_EVIDENCE" for a in attempts):
            status = AuditPolicyExecutionStatus.INVALID_EVIDENCE
        elif any(a.status == "NO_QUORUM" for a in attempts):
            status = AuditPolicyExecutionStatus.NO_QUORUM
        elif any(a.status == "ACTION_INFEASIBLE_PRIVACY_BUDGET" for a in attempts):
            status = AuditPolicyExecutionStatus.ACTION_INFEASIBLE_DISCLOSURE
        else:
            status = AuditPolicyExecutionStatus.POLICY_STOP
        raw_hashes = [content_hash(a.to_plain()) for a in attempts]
        return PolicyWorldResult(
            world_id=world_id, state=state,
            ground_truth_ref=world.ground_truth_ref,
            policy_status=status,
            posterior=result.posterior,
            p_breach_lower_sys=result.p_breach_lower_sys,
            audit_pay_s=result.audit_pay_s,
            audit_pay_b=result.audit_pay_b,
            attempts=attempts,
            raw_event_hashes=raw_hashes,
        )

    def _snapshot(self, world_id: str):
        from valor.audit.market_quote import AuditMarketSnapshot

        if self.market_provider is not None:
            snap = self.market_provider.snapshot() if hasattr(self.market_provider, "snapshot") else self.market_provider
            if isinstance(snap, AuditMarketSnapshot):
                return snap
            if isinstance(snap, dict):
                return AuditMarketSnapshot(
                    snapshot_id=snap.get("snapshot_id", f"mkt-{world_id}"),
                    family=snap.get("family", "quality"),
                    qualified_nodes=snap["qualified_nodes"],
                    bids={str(k): float(v) for k, v in snap["bids"].items()},
                    min_stake=float(snap.get("min_stake", 0.0)),
                    source_kind=snap.get("source_kind", "MARKET_DISCOVERED"),
                    source_ref=snap.get("source_ref", "market_provider"),
                    version=snap.get("version", "1"),
                    capability=snap.get("capability", {}),
                    stake=snap.get("stake", {}),
                    availability=snap.get("availability", {}),
                    reliability=snap.get("reliability", {}),
                    public_key_fingerprint=snap.get("public_key_fingerprint", {}),
                )
        mkt = self.scenario.audit.get("market")
        return AuditMarketSnapshot(
            snapshot_id=mkt.get("snapshot_id", f"mkt-{world_id}"),
            family=mkt.get("family", "quality"),
            qualified_nodes=[str(x) for x in mkt["qualified_nodes"]],
            bids={str(k): float(v) for k, v in mkt["bids"].items()},
            min_stake=float(mkt.get("min_stake", 0.0)),
            source_kind=mkt.get("source_kind", "THREAT_SCENARIO"),
            source_ref=mkt.get("source_ref", "scenario.audit.market"),
            version=mkt.get("version", "1"),
            capability=mkt.get("capability", {}),
            stake={str(k): float(v) for k, v in mkt.get("stake", {}).items()},
            availability={str(k): float(v) for k, v in mkt.get("availability", {}).items()},
            reliability={str(k): float(v) for k, v in mkt.get("reliability", {}).items()},
            public_key_fingerprint=mkt.get("public_key_fingerprint", {}),
        )


__all__ = [
    "AuditPolicyExecutionStatus",
    "AuditAttemptRecord",
    "PolicyWorldResult",
    "FullAuditPolicyExecutor",
]
