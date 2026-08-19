"""Round 4 Phase 5: independent R_cert full-policy certification."""

from __future__ import annotations

import numpy as np
import pytest

from valor.audit.policy import AuditPolicy
from valor.core.enums import ExecutionMode
from valor.engine.distributed_calibration_runner import DistributedAuditCalibrationRunner
from valor.engine.distributed_policy_certifier import DistributedPolicyCertifier
from valor.engine.scenario import CapstoneScenario
from valor.privacy_audit import ClaimType, CommittedDatasetStore, create_privacy_app
from valor.privacy_audit.verifier import CommitChallengeVerifier
from valor.security.signing import SigningKeyPair
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
    return sc


def _policy(sc) -> AuditPolicy:
    return AuditPolicy(
        policy_version="v1",
        action_profile_hashes=(),
        likelihood_artifact_hashes=(),
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
    X = rng.integers(0, 256, size=(100, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=100)
    sc = _scenario()
    factory, public_keys = _client_factory()
    rcal = DistributedAuditCalibrationRunner(
        scenario=sc, X=X, y=y, claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[32], n_runs=1, f=2,
        seller_store=CommittedDatasetStore(str(tmp_path / "rcal")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    rcal_events = rcal.run()
    lik_arts = rcal.freeze_likelihood()
    certifier = DistributedPolicyCertifier(
        policy=_policy(sc), scenario=sc, X=X, y=y,
        likelihood_artifacts=lik_arts,
        claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[32],
        n_runs=1, f=2, seller_store=CommittedDatasetStore(str(tmp_path / "rcert")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    art = certifier.run(r_cal_event_ids=[e.event_id for e in rcal_events])
    assert art.policy_hash == art.policy.policy_hash
    assert art.r_cert_hash
    assert art.raw_certification_event_refs


def test_rcert_rejects_overlap(tmp_path):
    rng = np.random.default_rng(12)
    X = rng.integers(0, 256, size=(100, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=100)
    sc = _scenario()
    factory, public_keys = _client_factory()
    certifier = DistributedPolicyCertifier(
        policy=_policy(sc), scenario=sc, X=X, y=y, likelihood_artifacts={},
        claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[32],
        n_runs=1, f=2, seller_store=CommittedDatasetStore(str(tmp_path / "x")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    # Pretend R_cal claimed the same event ids as R_cert will produce.
    with pytest.raises(ValueError, match="DATA_ROLE_OVERLAP"):
        certifier.run(r_cal_event_ids=["evt-rcert-G-32-0",
                                        "evt-rcert-L-32-0",
                                        "evt-rcert-B-32-0"])
