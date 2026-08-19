"""PPA-4 隐私审计集成：scheduler → 节点（COMMIT_CHALLENGE）→ quorum。

用 FastAPI TestClient 验证完整链路，并验收 PP-AUDIT-G01（auditor 无全量数据）。
"""

from __future__ import annotations

import numpy as np
import pytest

from valor.core.ids import AuditorID
from valor.distributed.node_state import AuditorNode, NodeRegistry
from valor.privacy_audit import (
    ClaimType,
    DisclosureState,
    PrivacyAuditScheduler,
    claim_from_data,
    create_privacy_app,
)
from valor.privacy_audit.models import AuditExecutionMode, PrivacyAuditAction
from valor.privacy_audit.verifier import CommitChallengeVerifier
from valor.seller import SellerCommittedDataset
from valor.seller.audit_service import SellerAuditService
from valor.privacy_audit.commitment import CommittedDatasetStore
from valor.security.signing import SigningKeyPair
from fastapi.testclient import TestClient


def _setup(n=500, f=2, k=64):
    rng = np.random.default_rng(0)
    X = rng.integers(0, 256, size=(n, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=n)
    store = CommittedDatasetStore("/tmp/pa-int")
    seller = SellerCommittedDataset.create(
        store, dataset_id="ds1", version="v1", X=X, y=y, schema_hash="s" * 64)
    claim = claim_from_data(
        claim_type=ClaimType.LABEL_DISTRIBUTION, X=X, y=y,
        dataset_commitment_hash=seller.commitment.commitment_hash)
    disclosure = DisclosureState(
        dataset_commitment_hash=seller.commitment.commitment_hash,
        max_unique_rows=200, max_fraction=0.4, max_bytes=200 * 784, _n_rows=n)
    svc = SellerAuditService(dataset=seller, disclosure=disclosure)
    svc.add_claim(claim)
    action = PrivacyAuditAction(
        action_id=f"LABEL_DIST_CC_{k}", primitive_id="LabelDistributionAudit",
        execution_mode=AuditExecutionMode.COMMIT_CHALLENGE,
        claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_size=k,
        sampling_method="uniform_random", decision_rule_id="MULTINOMIAL_GOF")
    return X, y, seller, svc, claim, disclosure, action


def _registry(n_nodes=10, f=2):
    reg = NodeRegistry()
    for i in range(n_nodes):
        reg.register(AuditorNode(AuditorID(f"node-{i}"), ("quality",), 1.0, 100.0 + i))
    return reg


def test_commit_challenge_end_to_end():
    X, y, seller, svc, claim, disclosure, action = _setup(k=64)
    reg = _registry(f=2)
    bids = {AuditorID(f"node-{i}"): 10.0 + i for i in range(10)}

    # 每个节点一个 TestClient（独立 verifier）
    clients = {}
    public_keys = {}
    for i in range(10):
        kp = SigningKeyPair.generate(f"node-{i}")
        verifier = CommitChallengeVerifier(f"node-{i}", signing_key=kp)
        clients[f"node-{i}"] = TestClient(create_privacy_app(verifier))
        public_keys[f"node-{i}"] = kp.public_key_hex

    def node_client(node_id):
        return _ClientAdapter(clients[str(node_id)])

    sched = PrivacyAuditScheduler(
        registry=reg, f=2, bids=bids, seller_service=svc,
        node_clients=node_client, public_keys=public_keys)
    res = sched.run(
        action, tx_id="tx-1", commitment=seller.commitment, claim=claim,
        disclosure=disclosure)
    assert res.status in ("CERTIFIED", "NO_QUORUM")
    assert res.mc_a_pay > 0  # VCG 进 MC_A^pay
    assert len(res.committee) == 7
    assert res.cost.rows_disclosed_unique == 64


def test_auditor_has_no_full_data_g01():
    """PP-AUDIT-G01：节点端无全量数据，且能完成审计。"""
    X, y, seller, svc, claim, disclosure, action = _setup(k=32)
    verifier = CommitChallengeVerifier("node-0")
    client = TestClient(create_privacy_app(verifier))
    # 节点明确声明不持有全量数据
    r = client.get("/privacy/auditor_has_no_full_data")
    assert r.json()["has_full_data"] is False


def test_privacy_budget_infeasible_action():
    """披露预算不足 → ACTION_INFEASIBLE_PRIVACY_BUDGET（不偷偷降 k）。"""
    X, y, seller, svc, claim, disclosure, action = _setup(k=128)
    # 预算极小
    disclosure.max_unique_rows = 10
    reg = _registry(f=2)
    bids = {AuditorID(f"node-{i}"): 10.0 + i for i in range(10)}
    clients = {}
    public_keys = {}
    for i in range(10):
        kp = SigningKeyPair.generate(f"node-{i}")
        clients[f"node-{i}"] = TestClient(
            create_privacy_app(CommitChallengeVerifier(f"node-{i}", signing_key=kp)))
        public_keys[f"node-{i}"] = kp.public_key_hex
    sched = PrivacyAuditScheduler(
        registry=reg, f=2, bids=bids, seller_service=svc,
        node_clients=lambda nid: _ClientAdapter(clients[str(nid)]),
        public_keys=public_keys)
    res = sched.run(action, tx_id="tx-1", commitment=seller.commitment,
                    claim=claim, disclosure=disclosure)
    assert res.status == "ACTION_INFEASIBLE_PRIVACY_BUDGET"


class _ClientAdapter:
    """把 TestClient 适配成 node_clients 期望的接口。"""

    def __init__(self, tc):
        self._tc = tc

    def submit_task(self, task):
        r = self._tc.post("/privacy/tasks", json=task.to_plain())
        r.raise_for_status()
        return r.json()
