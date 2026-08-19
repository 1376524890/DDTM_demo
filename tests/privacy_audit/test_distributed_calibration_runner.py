"""Round 4 Phase 4: real commit-challenge distributed R_cal."""

from __future__ import annotations

import numpy as np

from valor.core.enums import ExecutionMode
from valor.engine.distributed_calibration_runner import DistributedAuditCalibrationRunner
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


def test_distributed_rcal_produces_likelihood_artifacts(tmp_path):
    rng = np.random.default_rng(7)
    X = rng.integers(0, 256, size=(120, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=120)
    sc = CapstoneScenario(scenario_id="rcal", seller_id="s", buyer_id="b")
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 64, "max_fraction": 0.5, "max_bytes": 64 * 784,
    }
    factory, public_keys = _client_factory()
    runner = DistributedAuditCalibrationRunner(
        scenario=sc, X=X, y=y, claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[32], n_runs=1, f=2,
        seller_store=CommittedDatasetStore(str(tmp_path / "store")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    events = runner.run()
    assert len(events) == 3  # G/L/B
    assert all(e.status in ("CERTIFIED", "NO_QUORUM") for e in events)
    arts = runner.freeze_likelihood()
    assert arts
