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
from valor.audit.action_catalog import ActionProfileCatalog
from valor.audit.action_profile import build_action_profile
from valor.audit.likelihood_catalog import LikelihoodCatalog
from valor.engine.full_policy_executor import FullAuditPolicyExecutor
from valor.engine.scenario import CapstoneScenario
from valor.experiments.registry import DataRoleManifest, DataRoleRegistry, DataSplitIsolationError
from valor.privacy_audit import ClaimType, CommittedDatasetStore
from valor.privacy_audit.process_isolated import AuditRuntimeDescriptor
from valor.security.certification import CertifiedCell, CertificationCatalog


@dataclass
class PolicyCellCertification:
    """Per-profile/cell certification evidence for R_cert.

    R_cert certifies Π_A over Ω_allowed: every profile/cell that is permitted
    to enter the policy gets its own statistical evidence and raw world refs.
    """

    cell_id: str
    action_profile_hash: str
    likelihood_artifact_hash: str
    policy_hash: str
    n_G: int
    n_L: int
    n_B: int
    tp: int
    fn: int
    fp: int
    tn: int
    beta_prior: dict
    beta_posterior: dict
    alpha: float
    p_breach_lower: float
    raw_world_refs: list[str]
    raw_evidence_refs: list[str]
    runtime_hash: str

    def to_plain(self) -> dict:
        return {
            "cell_id": self.cell_id,
            "action_profile_hash": self.action_profile_hash,
            "likelihood_artifact_hash": self.likelihood_artifact_hash,
            "policy_hash": self.policy_hash,
            "n_G": self.n_G,
            "n_L": self.n_L,
            "n_B": self.n_B,
            "tp": self.tp,
            "fn": self.fn,
            "fp": self.fp,
            "tn": self.tn,
            "beta_prior": self.beta_prior,
            "beta_posterior": self.beta_posterior,
            "alpha": self.alpha,
            "p_breach_lower": self.p_breach_lower,
            "raw_world_refs": self.raw_world_refs,
            "raw_evidence_refs": self.raw_evidence_refs,
            "runtime_hash": self.runtime_hash,
        }


def envelope_operator(values: list[float], *, mode: str = "min") -> float:
    """Pure EnvelopeOperator over per-cell p_B_lower values.

    Paper risk semantics (fail-closed): the certified system lower bound is the
    weakest cell lower bound across the allowed operating envelope. This is an
    independent pure function and must never be confused with computing one
    Beta lower bound over aggregated TP/FN.
    """
    if not values:
        raise ValueError("ENVELOPE_EMPTY: cannot compute EnvelopeOperator over no cells")
    vals = [float(v) for v in values]
    if mode == "min":
        return min(vals)
    if mode == "max":
        return max(vals)
    raise ValueError(f"UNKNOWN_ENVELOPE_OPERATOR: {mode}")


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
    alpha_D: float
    p_breach_lower_sys: float
    omega_allowed_envelope: list[dict]
    raw_certification_event_refs: list[str]
    n_runs: int = 1
    n_worlds: int = 0
    n_G: int = 0
    n_L: int = 0
    n_B: int = 0
    sample_size_by_cell: dict = field(default_factory=dict)
    cells: list[PolicyCellCertification] = field(default_factory=list)
    role_manifest_hash: str = ""
    trainer_hash: str = ""
    execution_runtime_hash: str = ""
    raw_event_hashes: list[str] = field(default_factory=list)
    policy_binding_mismatch: list[str] = field(default_factory=list)

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
            "alpha_D": self.alpha_D,
            "p_breach_lower_sys": self.p_breach_lower_sys,
            "omega_allowed_envelope": self.omega_allowed_envelope,
            "raw_certification_event_refs": self.raw_certification_event_refs,
            "n_runs": self.n_runs,
            "n_worlds": self.n_worlds,
            "n_G": self.n_G,
            "n_L": self.n_L,
            "n_B": self.n_B,
            "sample_size_by_cell": self.sample_size_by_cell,
            "cells": [c.to_plain() for c in self.cells],
            "role_manifest_hash": self.role_manifest_hash,
            "trainer_hash": self.trainer_hash,
            "execution_runtime_hash": self.execution_runtime_hash,
            "raw_event_hashes": self.raw_event_hashes,
            "policy_binding_mismatch": self.policy_binding_mismatch,
        }


class DistributedPolicyCertifier:
    def __init__(
        self,
        *,
        policy: AuditPolicy,
        scenario: CapstoneScenario,
        X: np.ndarray,
        y: np.ndarray,
        role_manifest: DataRoleManifest | None = None,
        likelihood_artifacts: dict[str, FrozenLikelihoodArtifact],
        claim_type: ClaimType = ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes: list[int] | None = None,
        n_runs: int = 2,
        f: int = 2,
        seller_store: CommittedDatasetStore | None = None,
        node_client_factory: Callable[[str], Any] | None = None,
        public_keys: dict[str, str] | None = None,
        execution_mode: ExecutionMode = ExecutionMode.TEST_FIXTURE,
        audit_runtime: AuditRuntimeDescriptor | None = None,
        role_registry=None,
        market_provider=None,
    ) -> None:
        self.policy = policy
        self.role_registry = role_registry
        self.market_provider = market_provider
        self.scenario = scenario
        self.X = X
        self.y = y
        self.role_manifest = role_manifest
        self.likelihood_artifacts = likelihood_artifacts
        self.claim_type = claim_type
        self.challenge_sizes = challenge_sizes or [32, 64]
        self.n_runs = n_runs
        self.f = f
        self.seller_store = seller_store or CommittedDatasetStore("seller_private")
        self.node_client_factory = node_client_factory
        self.public_keys = public_keys
        self.execution_mode = execution_mode
        self.audit_runtime = audit_runtime

    def run(self, *, r_cal_sample_ids: list[int] | None = None,
            r_cal_event_ids: list[str] | None = None) -> PolicyCertificationArtifact:
        r_cal_event_ids = r_cal_event_ids or []
        r_cal_sample_ids = [int(x) for x in (r_cal_sample_ids or [])]
        # Round 5/6: hard sample-ID overlap check via DataRoleRegistry.
        # Event-ID overlap logic is obsolete (r_cert_hashes was always empty).
        if self.role_manifest is not None:
            reg = DataRoleRegistry()
            if r_cal_sample_ids:
                from valor.experiments.registry import DataRoleManifest as _M
                cal_manifest = _M(
                    role_id="R_cal", dataset_id=self.role_manifest.dataset_id,
                    dataset_version=self.role_manifest.dataset_version,
                    sample_ids=tuple(r_cal_sample_ids),
                    split_seed=self.role_manifest.split_seed - 1,
                    split_algorithm_hash=self.role_manifest.split_algorithm_hash,
                    source_dataset_hash=self.role_manifest.source_dataset_hash,
                    trainer_scope_hash=self.role_manifest.trainer_scope_hash,
                    task_family_hash=self.role_manifest.task_family_hash,
                )
                reg.register_role_manifest(cal_manifest)
            reg.register_role_manifest(self.role_manifest)
            try:
                reg.freeze()
            except DataSplitIsolationError as e:
                raise ValueError(f"DATA_ROLE_OVERLAP: {e}") from e
        # Build canonical catalogs from likelihood artifacts and scenario profiles.
        # Build canonical catalogs from likelihood artifacts and scenario profiles.
        lik_catalog = LikelihoodCatalog()
        for art in self.likelihood_artifacts.values():
            lik_catalog.register(art)
        profile_catalog = ActionProfileCatalog()
        profile_by_k: dict[int, str] = {}
        for k in self.challenge_sizes:
            profile = build_action_profile(
                scenario_audit=self.scenario.audit,
                claim_type=self.claim_type.value,
                k=k, f=self.f,
                execution_version_hash=str(self.scenario.audit.get("execution_version_hash", "cc-audit-v1")),
            )
            if profile.action_profile_hash not in self.likelihood_artifacts:
                raise ValueError(
                    f"ACTION_NOT_CERTIFIED: no likelihood artifact for profile "
                    f"{profile.action_profile_hash} (k={k})")
            profile_catalog.register(profile)
            profile_by_k[k] = profile.action_profile_hash

        # Phase 14: policy must be generated from the exact catalogs.
        mismatch: list[str] = []
        if sorted(self.policy.action_profile_hashes) != sorted(profile_catalog._profiles.keys()):
            mismatch.append("action_profile_hashes")
        if sorted(self.policy.likelihood_artifact_hashes) != sorted(
                art.artifact_hash for art in lik_catalog._artifacts.values()):
            mismatch.append("likelihood_artifact_hashes")
        if mismatch:
            raise ValueError(
                f"CERTIFICATION_POLICY_BINDING_MISMATCH: {mismatch}"
            )

        executor = FullAuditPolicyExecutor(
            policy=self.policy, scenario=self.scenario, X=self.X, y=self.y,
            role_manifest=self.role_manifest,
            likelihood_catalog=lik_catalog,
            action_profile_catalog=profile_catalog,
            claim_type=self.claim_type, challenge_sizes=self.challenge_sizes,
            f=self.f, n_runs=self.n_runs, seller_store=self.seller_store,
            node_client_factory=self.node_client_factory,
            public_keys=self.public_keys,
            execution_mode=self.execution_mode,
            audit_runtime=self.audit_runtime,
            role_registry=self.role_registry,
            market_provider=self.market_provider,
        )
        world_results = executor.run()
        execution_runtime_hash = (
            content_hash(self.audit_runtime.to_plain())
            if self.audit_runtime is not None else "")
        role_manifest_hash = (
            self.role_manifest.role_manifest_hash
            if self.role_manifest is not None else "")
        a, b = 1.0, 1.0
        alpha_D = float(self.scenario.audit.get("alpha_D", 0.05))
        cells: list[PolicyCellCertification] = []
        cells_plain: list[dict] = []
        sample_size_by_cell: dict[str, dict] = {}
        for k in self.challenge_sizes:
            profile_hash = profile_by_k[k]
            k_worlds = [w for w in world_results if w.challenge_k == k]
            if not k_worlds:
                continue
            n_G = sum(1 for w in k_worlds if w.state == "G")
            n_L = sum(1 for w in k_worlds if w.state == "L")
            n_B = sum(1 for w in k_worlds if w.state == "B")
            tp = sum(1 for w in k_worlds if w.state == "B"
                     and any(a.outcome == "BREACH_EVIDENCE" for a in w.attempts))
            fn = sum(1 for w in k_worlds if w.state == "B"
                     and not any(a.outcome == "BREACH_EVIDENCE" for a in w.attempts))
            fp = sum(1 for w in k_worlds if w.state == "G"
                     and any(a.outcome == "BREACH_EVIDENCE" for a in w.attempts))
            tn = sum(1 for w in k_worlds if w.state == "G"
                     and not any(a.outcome == "BREACH_EVIDENCE" for a in w.attempts))
            a_post, b_post = a + tp, b + fn
            p_lower = float(_beta_ppf(alpha_D, a_post, b_post))
            cell_id = f"c_k{k}"
            lik_artifact_hash = ""
            if profile_hash in self.likelihood_artifacts:
                lik_artifact_hash = self.likelihood_artifacts[profile_hash].artifact_hash
            raw_world_refs = [f"rcert://{w.world_id}" for w in k_worlds]
            raw_evidence_refs = [
                f"rcert://{w.world_id}#evidence/{i}"
                for w in k_worlds for i in range(len(w.attempts))
                if w.attempts[i].evidence_artifact_refs
            ]
            cell = PolicyCellCertification(
                cell_id=cell_id,
                action_profile_hash=profile_hash,
                likelihood_artifact_hash=lik_artifact_hash,
                policy_hash=self.policy.policy_hash,
                n_G=n_G, n_L=n_L, n_B=n_B,
                tp=tp, fn=fn, fp=fp, tn=tn,
                beta_prior={"a": a, "b": b},
                beta_posterior={"a": a_post, "b": b_post},
                alpha=alpha_D,
                p_breach_lower=p_lower,
                raw_world_refs=raw_world_refs,
                raw_evidence_refs=raw_evidence_refs,
                runtime_hash=execution_runtime_hash,
            )
            cells.append(cell)
            cells_plain.append(cell.to_plain())
            sample_size_by_cell[cell_id] = {
                "n_G": n_G, "n_L": n_L, "n_B": n_B,
                "tp": tp, "fn": fn, "fp": fp, "tn": tn,
                "action_profile_hash": profile_hash,
                "likelihood_artifact_hash": lik_artifact_hash,
            }
        if not cells:
            raise ValueError(
                "R_CERT_NO_CELLS: no certified cells produced (policy/world "
                "execution failed for every profile)")
        # System envelope: independent pure EnvelopeOperator over per-cell bounds.
        p_lower_sys = envelope_operator([c.p_breach_lower for c in cells])
        omega_allowed_envelope = [{
            "cell_id": c.cell_id,
            "action_profile_hash": c.action_profile_hash,
            "likelihood_artifact_hash": c.likelihood_artifact_hash,
            "policy_hash": c.policy_hash,
            "p_breach_lower": c.p_breach_lower,
        } for c in cells]
        action_catalog_hash = profile_catalog.catalog_hash()
        likelihood_catalog_hash = lik_catalog.catalog_hash()
        world_construction_hashes = sorted(
            content_hash({
                "world_id": w.world_id,
                "state": w.state,
                "ground_truth_ref": w.ground_truth_ref,
                "construction_hash": getattr(w, "construction_hash", ""),
            }) for w in world_results)
        artifact_hash = content_hash({
            "role_manifest_hash": role_manifest_hash,
            "policy_hash": self.policy.policy_hash,
            "action_catalog_hash": action_catalog_hash,
            "likelihood_catalog_hash": likelihood_catalog_hash,
            "execution_runtime_hash": execution_runtime_hash,
            "world_construction_hashes": world_construction_hashes,
            "world_result_hashes": sorted(
                content_hash(w.to_plain()) for w in world_results),
            "cells": [c.to_plain() for c in cells],
            "beta_prior": {"a": a, "b": b},
            "alpha_D": alpha_D,
            "omega_allowed_envelope": omega_allowed_envelope,
            "envelope_operator": "min",
        })
        return PolicyCertificationArtifact(
            policy=self.policy, policy_hash=self.policy.policy_hash,
            action_catalog_hash=action_catalog_hash,
            likelihood_catalog_hash=likelihood_catalog_hash,
            r_cert_hash=artifact_hash,
            trainer_task_family="digit-classification",
            breach_family="quality",
            tp=sum(c.tp for c in cells),
            fn=sum(c.fn for c in cells),
            fp=sum(c.fp for c in cells),
            tn=sum(c.tn for c in cells),
            beta_prior={"a": a, "b": b},
            beta_posterior={"a": a + sum(c.tp for c in cells),
                            "b": b + sum(c.fn for c in cells)},
            alpha_D=alpha_D,
            p_breach_lower_sys=float(p_lower_sys),
            omega_allowed_envelope=omega_allowed_envelope,
            raw_certification_event_refs=[
                f"rcert://{w.world_id}" for w in world_results],
            n_runs=self.n_runs,
            n_worlds=len(world_results),
            n_G=sum(1 for w in world_results if w.state == "G"),
            n_L=sum(1 for w in world_results if w.state == "L"),
            n_B=sum(1 for w in world_results if w.state == "B"),
            sample_size_by_cell=sample_size_by_cell,
            cells=cells,
            role_manifest_hash=role_manifest_hash,
            trainer_hash=content_hash(self.scenario.trainer),
            execution_runtime_hash=execution_runtime_hash,
            raw_event_hashes=[
                h for w in world_results for h in w.raw_event_hashes],
            policy_binding_mismatch=mismatch,
        )


def _beta_ppf(alpha_D: float, a_post: float, b_post: float) -> float:
    from scipy.stats import beta as beta_dist
    if a_post <= 0 or b_post <= 0:
        raise ValueError("INVALID_BETA_PARAMS: posterior shape must be positive")
    return float(beta_dist.ppf(alpha_D, a_post, b_post))


__all__ = [
    "DistributedPolicyCertifier",
    "PolicyCertificationArtifact",
    "PolicyCellCertification",
    "envelope_operator",
    "reconcile_policy_certification",
]


def reconcile_policy_certification(artifact: PolicyCertificationArtifact) -> bool:
    """Recompute per-cell and system p_B_lower from scipy Beta ppf.

    Requirement: each cell is verified independently, then the system envelope
    is recomputed through the pure EnvelopeOperator. A mutation to one cell's
    TP/FN or to the envelope operator output must make reconciliation FAIL.
    """
    if not artifact.cells:
        return False
    for cell in artifact.cells:
        a = float(cell.beta_prior["a"])
        b = float(cell.beta_prior["b"])
        expected = _beta_ppf(cell.alpha, a + cell.tp, b + cell.fn)
        if abs(expected - cell.p_breach_lower) > 1e-12:
            return False
    expected_sys = envelope_operator([c.p_breach_lower for c in artifact.cells])
    return abs(expected_sys - float(artifact.p_breach_lower_sys)) < 1e-12


