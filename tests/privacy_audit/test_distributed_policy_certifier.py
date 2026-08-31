"""Round 4 Phase 5: independent R_cert full-policy certification."""

from __future__ import annotations

import numpy as np
import pytest

from valor.audit.policy import AuditPolicy
from valor.core.enums import ExecutionMode
from valor.core.hashing import content_hash
from valor.engine.distributed_calibration_runner import DistributedAuditCalibrationRunner
from valor.engine.distributed_policy_certifier import (
    DistributedPolicyCertifier,
    PolicyCertificationArtifact,
    PolicyCellCertification,
    reconcile_policy_certification,
)
from valor.engine.scenario import CapstoneScenario
from valor.experiments.registry import DataRoleManifest
from valor.privacy_audit import ClaimType, CommittedDatasetStore, create_privacy_app
from valor.privacy_audit.verifier import CommitChallengeVerifier
from valor.security.certification import CertifiedCell, CertificationCatalog
from valor.security.signing import SigningKeyPair
from scipy.stats import beta
from fastapi.testclient import TestClient


def _client_factory(n=10):
    clients = {}
    public_keys = {}
    for i in range(n):
        kp = SigningKeyPair.generate(f"node-{i}")
        clients[f"node-{i}"] = TestClient(
            create_privacy_app(CommitChallengeVerifier(f"node-{i}", signing_key=kp)))
        public_keys[f"node-{i}"] = kp.public_key_hex

    class _A:
        def __init__(self, tc):
            self._tc = tc

        def submit_task(self, task):
            r = self._tc.post("/privacy/tasks", json=task.to_plain())
            r.raise_for_status()
            return r.json()

    return lambda nid: _A(clients[str(nid)]), public_keys


def _scenario():
    sc = CapstoneScenario(scenario_id="rcert", seller_id="s", buyer_id="b")
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 64, "max_fraction": 0.5, "max_bytes": 64 * 784,
    }
    sc.audit["low_suitability_world"] = {
        "method": "buyer_task_utility",
        "threshold": 0.5,
        "row_utilities": [0.1] * 40 + [0.9] * 60,
        "ground_truth_ref": "rcal-L-buyer-task-utility",
    }
    sc.audit["breach_world"] = {
        "family": "POST_COMMIT_DATA_TAMPER",
        "tamper_fraction": 0.2,
        "ground_truth_ref": "rcal-B-post-commit-data-tamper",
    }
    return sc


def _role(role_id, n, seed, start=0):
    return DataRoleManifest(
        role_id=role_id, dataset_id="mnist", dataset_version="v1",
        sample_ids=tuple(range(start, start + n)), split_seed=seed,
        split_algorithm_hash=content_hash({"split": "four-way-v1"}),
        source_dataset_hash=content_hash({"dataset": "mnist"}),
        trainer_scope_hash=content_hash({"trainer": "mnist-mlp"}),
        task_family_hash=content_hash({"task": "digit-classification"}),
    )


def _policy(sc, action_profile_hashes=(), likelihood_artifact_hashes=()) -> AuditPolicy:
    return AuditPolicy(
        policy_version="v1",
        action_profile_hashes=tuple(action_profile_hashes),
        likelihood_artifact_hashes=tuple(likelihood_artifact_hashes),
        selection_algorithm_version="voi-v1",
        prior_family_version="dirichlet-v1",
        loss_matrix_hash="loss-v1",
        stop_rule="VOI_LE_0",
        mandatory_base_audit_policy="BASE_LISTING_ONCE",
        disclosure_policy="rows-fraction-bytes",
        market_quote_policy="FROZEN_SNAPSHOT",
        payer_policy="SELLER",
        evidence_verification_policy="ED25519_REQUIRED",
        quorum_policy="QUORUM_BY_RESULT",
        replacement_policy="OFFLINE_REPLACEMENT",
        certificate_requirements="R_CERT_INDEPENDENT",
    )


def test_rcert_independent_artifact(tmp_path):
    rng = np.random.default_rng(11)
    X = rng.integers(0, 256, size=(200, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=200)
    sc = _scenario()
    factory, public_keys = _client_factory()
    rcal = DistributedAuditCalibrationRunner(
        scenario=sc, X=X, y=y, role_manifest=_role("R_cal", 100, 11),
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[32], n_runs=1, f=2,
        seller_store=CommittedDatasetStore(str(tmp_path / "rcal")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    rcal_events = rcal.run()
    lik_arts = rcal.freeze_likelihood()
    profile_hashes = sorted(lik_arts.keys())
    lik_hashes = [art.artifact_hash for art in lik_arts.values()]
    certifier = DistributedPolicyCertifier(
        policy=_policy(sc, profile_hashes, lik_hashes), scenario=sc, X=X, y=y,
        role_manifest=_role("R_cert", 100, 21, start=100),
        likelihood_artifacts=lik_arts,
        claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[32],
        n_runs=1, f=2, seller_store=CommittedDatasetStore(str(tmp_path / "rcert")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    art = certifier.run(r_cal_sample_ids=[int(x) for x in range(100)],
                        r_cal_event_ids=[e.event_id for e in rcal_events])
    assert art.policy_hash == art.policy.policy_hash
    assert art.r_cert_hash
    assert art.raw_certification_event_refs
    # Round 6 Phase 13: provenance binds canonical catalog hashes + trainer hash
    assert art.action_catalog_hash
    assert art.likelihood_catalog_hash
    assert art.trainer_hash != sc.trainer.get("type", "")
    assert art.trainer_hash == content_hash(sc.trainer)
    assert art.role_manifest_hash
    if certifier.audit_runtime is not None:
        assert art.execution_runtime_hash


def test_rcert_rejects_overlap(tmp_path):
    rng = np.random.default_rng(12)
    X = rng.integers(0, 256, size=(200, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=200)
    sc = _scenario()
    factory, public_keys = _client_factory()
    certifier = DistributedPolicyCertifier(
        policy=_policy(sc), scenario=sc, X=X, y=y,
        role_manifest=_role("R_cert", 100, 31),
        likelihood_artifacts={},
        claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[32],
        n_runs=1, f=2, seller_store=CommittedDatasetStore(str(tmp_path / "x")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    # Pretend R_cal claimed overlapping sample IDs.
    with pytest.raises(ValueError, match="DATA_ROLE_OVERLAP"):
        certifier.run(r_cal_sample_ids=[0, 1, 2],
                      r_cal_event_ids=["evt-rcert-G-32-0"])


def _cell(a_D, b_D, alpha_D, tp, fn, cell_id="c_k16"):
    return PolicyCellCertification(
        cell_id=cell_id,
        action_profile_hash="prof-1",
        likelihood_artifact_hash="lik-1",
        policy_hash="pol",
        n_G=1, n_L=1, n_B=1,
        tp=tp, fn=fn, fp=0, tn=0,
        beta_prior={"a": a_D, "b": b_D},
        beta_posterior={"a": a_D + tp, "b": b_D + fn},
        alpha=alpha_D,
        p_breach_lower=float(beta.ppf(alpha_D, a_D + tp, b_D + fn)),
        raw_world_refs=["rcert://G-16-0"],
        raw_evidence_refs=[],
        runtime_hash="",
    )


def test_rcert_beta_lower_matches_scipy_exactly():
    """Canonical Beta posterior must equal scipy.stats.beta.ppf exactly."""
    from scipy.stats import beta
    from valor.engine.distributed_policy_certifier import reconcile_policy_certification
    a_D, b_D, alpha_D = 1.0, 2.0, 0.05
    tp, fn = 7, 1
    expected = float(beta.ppf(alpha_D, a_D + tp, b_D + fn))
    cat = CertificationCatalog()
    cat.register(CertifiedCell(
        "c1", a_D, b_D, alpha_D, {"quality": (tp, fn)}))
    assert cat.p_breach_lower("c1", "quality") == expected

    cell = _cell(a_D, b_D, alpha_D, tp, fn)
    art = PolicyCertificationArtifact(
        policy=None, policy_hash="h", action_catalog_hash="ac",
        likelihood_catalog_hash="lc", r_cert_hash="r",
        trainer_task_family="digit-classification", breach_family="quality",
        tp=tp, fn=fn, fp=0, tn=0,
        beta_prior={"a": a_D, "b": b_D},
        beta_posterior={"a": a_D + tp, "b": b_D + fn},
        alpha_D=alpha_D,
        p_breach_lower_sys=expected,
        omega_allowed_envelope=[],
        raw_certification_event_refs=[],
        cells=[cell],
    )
    assert reconcile_policy_certification(art)


def test_rcert_beta_double_count_mutation_fails_reconciliation():
    """Artificially doubling TP must fail certification reconciliation."""
    from valor.engine.distributed_policy_certifier import reconcile_policy_certification
    a_D, b_D, alpha_D = 1.0, 2.0, 0.05
    tp, fn = 7, 1
    expected = float(beta.ppf(alpha_D, a_D + tp, b_D + fn))
    cell = _cell(a_D, b_D, alpha_D, tp, fn)
    art = PolicyCertificationArtifact(
        policy=None, policy_hash="h", action_catalog_hash="ac",
        likelihood_catalog_hash="lc", r_cert_hash="r",
        trainer_task_family="digit-classification", breach_family="quality",
        tp=tp, fn=fn, fp=0, tn=0,
        beta_prior={"a": a_D, "b": b_D},
        beta_posterior={"a": a_D + tp, "b": b_D + fn},
        alpha_D=alpha_D,
        p_breach_lower_sys=expected,
        omega_allowed_envelope=[],
        raw_certification_event_refs=[],
        cells=[cell],
    )
    assert reconcile_policy_certification(art)
    mutated = PolicyCertificationArtifact(
        policy=None, policy_hash="h", action_catalog_hash="ac",
        likelihood_catalog_hash="lc", r_cert_hash="r",
        trainer_task_family="digit-classification", breach_family="quality",
        tp=2 * tp, fn=fn, fp=0, tn=0,  # mutation: double TP
        beta_prior={"a": a_D, "b": b_D},
        beta_posterior={"a": a_D + 2 * tp, "b": b_D + fn},
        alpha_D=alpha_D,
        p_breach_lower_sys=expected,
        omega_allowed_envelope=[],
        raw_certification_event_refs=[],
    )
    assert not reconcile_policy_certification(mutated)


def test_rcert_n_runs_creates_independent_worlds(tmp_path):
    """n_runs=5 must produce 15 PolicyWorldResults, not one per state."""
    from valor.engine.full_policy_executor import FullAuditPolicyExecutor
    from valor.engine.distributed_policy_certifier import DistributedPolicyCertifier
    rng = np.random.default_rng(41)
    X = rng.integers(0, 256, size=(200, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=200)
    sc = _scenario()
    factory, public_keys = _client_factory()
    rcal = DistributedAuditCalibrationRunner(
        scenario=sc, X=X, y=y, role_manifest=_role("R_cal", 100, 11),
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[16], n_runs=1, f=2,
        seller_store=CommittedDatasetStore(str(tmp_path / "rcal")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    rcal_events = rcal.run()
    lik_arts = rcal.freeze_likelihood()
    profile_hashes = sorted(lik_arts.keys())
    lik_hashes = [art.artifact_hash for art in lik_arts.values()]
    certifier = DistributedPolicyCertifier(
        policy=_policy(sc, profile_hashes, lik_hashes), scenario=sc, X=X, y=y,
        role_manifest=_role("R_cert", 100, 21, start=100),
        likelihood_artifacts=lik_arts,
        claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[16],
        n_runs=5, f=2, seller_store=CommittedDatasetStore(str(tmp_path / "rcert")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    art = certifier.run(r_cal_sample_ids=[int(x) for x in range(100)],
                        r_cal_event_ids=[e.event_id for e in rcal_events])
    assert art.n_runs == 5
    assert art.n_worlds == 15
    assert art.n_G == 5
    assert art.n_L == 5
    assert art.n_B == 5
    assert art.sample_size_by_cell["c_k16"]["tp"] + art.sample_size_by_cell["c_k16"]["fn"] == 5


def test_rcert_multi_profile_envelope_and_reconciliation(tmp_path):
    """R_cert certifies Π_A over Ω_allowed across multiple profiles/cells."""
    from dataclasses import replace
    rng = np.random.default_rng(91)
    X = rng.integers(0, 256, size=(400, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=400)
    sc = _scenario()
    factory, public_keys = _client_factory()
    challenge_sizes = [16, 32, 64]
    sc.audit["low_suitability_world"]["row_utilities"] = [0.1]*80 + [0.9]*120
    rcal = DistributedAuditCalibrationRunner(
        scenario=sc, X=X, y=y, role_manifest=_role("R_cal", 200, 11),
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=challenge_sizes, n_runs=1, f=2,
        seller_store=CommittedDatasetStore(str(tmp_path / "rcal")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    rcal_events = rcal.run()
    lik_arts = rcal.freeze_likelihood()
    profile_hashes = sorted(lik_arts.keys())
    lik_hashes = [art.artifact_hash for art in lik_arts.values()]
    assert len(profile_hashes) == 3
    certifier = DistributedPolicyCertifier(
        policy=_policy(sc, profile_hashes, lik_hashes), scenario=sc, X=X, y=y,
        role_manifest=_role("R_cert", 200, 21, start=200),
        likelihood_artifacts=lik_arts,
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=challenge_sizes,
        n_runs=1, f=2,
        seller_store=CommittedDatasetStore(str(tmp_path / "rcert")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    art = certifier.run(r_cal_sample_ids=[int(x) for x in range(200)],
                        r_cal_event_ids=[e.event_id for e in rcal_events])
    assert len(art.cells) == 3
    assert len(art.omega_allowed_envelope) == 3
    cell_ids = [c.cell_id for c in art.cells]
    assert "c1" not in cell_ids
    assert sorted(cell_ids) == sorted(art.sample_size_by_cell.keys())
    for c in art.cells:
        assert c.action_profile_hash in lik_arts
        assert c.likelihood_artifact_hash == lik_arts[c.action_profile_hash].artifact_hash
        assert c.policy_hash == art.policy_hash
        assert c.n_G == 1 and c.n_L == 1 and c.n_B == 1
        assert c.p_breach_lower > 0.0
    # per-cell and system scipy reconciliation must PASS
    assert reconcile_policy_certification(art)
    # mutation: change one cell's TP/FN must make per-cell reconciliation fail
    mutated_cells = [replace(c, tp=c.tp + 1) if c.cell_id == cell_ids[0] else c
                     for c in art.cells]
    mutated = replace(art, cells=mutated_cells)
    assert not reconcile_policy_certification(mutated)
    # mutation: change system envelope lower bound must fail system reconciliation
    mutated_sys = replace(art, p_breach_lower_sys=art.p_breach_lower_sys + 0.01)
    assert not reconcile_policy_certification(mutated_sys)
