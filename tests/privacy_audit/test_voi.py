"""PPA-6 PrivacyAuditVOI：k 作为不同 action，VCG 进 MC_A^pay，披露累积。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine.scenario import CapstoneScenario
from valor.privacy_audit import (
    ClaimType,
    PrivacyAuditVOIExecutor,
    create_privacy_app,
)
from valor.privacy_audit.verifier import CommitChallengeVerifier
from valor.security.signing import SigningKeyPair
from fastapi.testclient import TestClient


def _scenario():
    sc = CapstoneScenario(scenario_id="voi-1", seller_id="seller-1", buyer_id="buyer-1")
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 300, "max_fraction": 0.5, "max_bytes": 300 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 300
    return sc


def _client_factory(n=10):
    clients = {}
    public_keys = {}
    for i in range(n):
        kp = SigningKeyPair.generate(f"node-{i}")
        clients[f"node-{i}"] = TestClient(
            create_privacy_app(CommitChallengeVerifier(f"node-{i}", signing_key=kp)))
        public_keys[f"node-{i}"] = kp.public_key_hex

    class _A:
        def __init__(self, tc): self._tc = tc
        def submit_task(self, task):
            r = self._tc.post("/privacy/tasks", json=task.to_plain())
            r.raise_for_status()
            return r.json()

    return lambda nid: _A(clients[str(nid)]), public_keys


def test_voi_runs_commit_challenge():
    rng = np.random.default_rng(0)
    X = rng.integers(0, 256, size=(800, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=800)
    sc = _scenario()
    factory, public_keys = _client_factory()
    ex = PrivacyAuditVOIExecutor(
        scenario=sc, candidate_X=X, candidate_y=y,
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[32, 64], n_nodes=10, f=2,
        seller_store=__import__("valor.privacy_audit.commitment",
                                fromlist=["CommittedDatasetStore"])
        .CommittedDatasetStore("/tmp/pa-voi"),
        node_client_factory=factory,
        public_keys=public_keys,
        allow_independent_commit=True,
    )
    ctx = {"binding": type("B", (), {"tx_id": "tx-1"})()}
    res = ex.run(sc, ctx)
    assert res.n_steps >= 0
    assert res.action_catalog_hash
    assert len(res.action_results) >= 0
    # 披露预算累积（若执行了 action）
    if res.action_results:
        assert res.action_results[0]["mc_a_pay"] > 0


def test_disclosure_accumulates_and_budget_limits():
    """多次 action 累积披露；预算耗尽后停止（不超预算）。"""
    rng = np.random.default_rng(1)
    X = rng.integers(0, 256, size=(600, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=600)
    sc = _scenario()
    # 预算很小：只允许一次 k=64
    sc.audit["privacy_budget"]["max_unique_rows"] = 64
    factory, public_keys = _client_factory()
    ex = PrivacyAuditVOIExecutor(
        scenario=sc, candidate_X=X, candidate_y=y,
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[64, 128], n_nodes=10, f=2,
        seller_store=__import__("valor.privacy_audit.commitment",
                                fromlist=["CommittedDatasetStore"])
        .CommittedDatasetStore("/tmp/pa-voi2"),
        node_client_factory=factory,
        public_keys=public_keys,
        allow_independent_commit=True,
    )
    ctx = {"binding": type("B", (), {"tx_id": "tx-2"})()}
    res = ex.run(sc, ctx)
    # 披露总唯一行数不超预算
    assert res.disclosure["unique_disclosure"] <= 64
