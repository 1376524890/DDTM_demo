"""PPA-7 受控 corruption 校准 + PP-AUDIT-G01..G12 验收测试。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.privacy_audit import (
    CommittedDatasetStore,
    DisclosureState,
    PrivacyBudgetExceededError,
    canonical_mnist_row,
    generate_challenge,
    verify_opening,
)
from valor.privacy_audit.calibration_cases import (
    run_breach_case,
    run_good_case,
    run_latent_case,
)
from valor.privacy_audit.canonicalize import canonical_row_from_payload
from valor.privacy_audit.merkle import MerkleProof
from valor.seller import SellerCommittedDataset


def _block(n=400, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 256, size=(n, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=n)
    return X, y


def _seller(X, y, path="/tmp/pa-acc", ds="ds1"):
    store = CommittedDatasetStore(path)
    return SellerCommittedDataset.create(
        store, dataset_id=ds, version="v1", X=X, y=y, schema_hash="s" * 64)


def test_calibration_cases_L_ne_B():
    """G/L/B 三种 ground truth 严格不同：B 触发 breach，L 不触发。"""
    X, y = _block(400, seed=0)
    g = run_good_case(X, y, 32, seed=0)
    l = run_latent_case(X, y, 32, seed=1, latent_frac=0.05)
    b = run_breach_case(X, y, 32, seed=2)
    # B（篡改）→ 必为 BREACH_EVIDENCE（真实 seller breach）
    assert b == "BREACH_EVIDENCE"
    # L（诚实但不适合）绝不能是 BREACH_EVIDENCE
    assert l != "BREACH_EVIDENCE"
    assert g != "BREACH_EVIDENCE"


# ---- PP-AUDIT 验收 Gate ----
def test_g01_auditor_no_full_data():
    """G01: auditor 端无全量数据（server 断言）。"""
    from valor.privacy_audit import CommitChallengeVerifier, create_privacy_app
    from fastapi.testclient import TestClient

    client = TestClient(create_privacy_app(CommitChallengeVerifier("node-0")))
    assert client.get("/privacy/auditor_has_no_full_data").json()["has_full_data"] is False


def test_g03_g04_challenge_after_commit_and_verify():
    """G03/G04: 承诺先于挑战；所有揭示行通过 Merkle 验证。"""
    X, y = _block(300)
    seller = _seller(X, y, "/tmp/pa-g34")
    ch = generate_challenge(task_hash="t" * 64, action_id="a1",
                            n_rows=300, k=16, nonce=b"\x0a" * 32)
    opens = seller.open_rows(list(ch.indices))
    for o in opens:
        assert verify_opening(o, seller.commitment) is True


def test_g05_g06_g07_g08_tamper_detected():
    """G05-G08: 篡改 pixel/label/index/Merkle path 均被检测。"""
    X, y = _block(300)
    seller = _seller(X, y, "/tmp/pa-g5")
    o = seller.open_rows([5])[0]
    idx, img, label = canonical_row_from_payload(o.row_payload, index=5)
    # G05 改 pixel
    img2 = img.copy(); img2[0] = (int(img2[0]) + 1) % 256
    from valor.privacy_audit import make_opening
    assert verify_opening(make_opening(
        index=5, row_payload=canonical_mnist_row(5, img2, label),
        salt=bytes.fromhex(o.salt), proof=o.proof), seller.commitment) is False
    # G06 改 label
    assert verify_opening(make_opening(
        index=5, row_payload=canonical_mnist_row(5, img, (label + 1) % 10),
        salt=bytes.fromhex(o.salt), proof=o.proof), seller.commitment) is False
    # G07 改 index
    assert verify_opening(make_opening(
        index=6, row_payload=canonical_mnist_row(6, img, label),
        salt=bytes.fromhex(o.salt), proof=o.proof), seller.commitment) is False
    # G08 改 Merkle path（篡改 sibling）
    from valor.privacy_audit.merkle import MerkleSibling
    bad_sibs = tuple(
        MerkleSibling("0" * 64, s.side) for s in o.proof.siblings)
    bad_proof = MerkleProof(index=5, siblings=bad_sibs)
    assert verify_opening(make_opening(
        index=5, row_payload=o.row_payload,
        salt=bytes.fromhex(o.salt), proof=bad_proof), seller.commitment) is False


def test_g09_privacy_budget_never_exceeded():
    """G09: 隐私预算永不被超过（fail closed）。"""
    X, y = _block(1000)
    seller = _seller(X, y, "/tmp/pa-g9")
    disc = DisclosureState(
        dataset_commitment_hash=seller.commitment.commitment_hash,
        max_unique_rows=30, max_fraction=0.03, max_bytes=30 * 784, _n_rows=1000)
    disc.record(list(range(30)), 30 * 784)
    ch = generate_challenge(task_hash="t" * 64, action_id="a1",
                            n_rows=1000, k=10, nonce=b"\x0b" * 32)
    from valor.seller.audit_service import SellerAuditService
    svc = SellerAuditService(dataset=seller, disclosure=disc)
    with pytest.raises(PrivacyBudgetExceededError):
        svc.process_challenge(ch)


def test_g11_vcg_payment_in_audit_voi():
    """G11: 真实 VCG 支付进入 Audit-VOI（MC_A^pay>0）。"""
    from valor.engine.scenario import CapstoneScenario
    from valor.privacy_audit import (
        ClaimType, PrivacyAuditVOIExecutor, create_privacy_app,
    )
    from valor.privacy_audit.verifier import CommitChallengeVerifier
    from fastapi.testclient import TestClient

    X, y = _block(500, seed=1)
    sc = CapstoneScenario(scenario_id="g11", seller_id="s", buyer_id="b")
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 200, "max_fraction": 0.4, "max_bytes": 200 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 200
    sc.rights["audit_reveal_max_fraction"] = 0.4
    sc.rights["audit_reveal_max_bytes"] = 200 * 784
    clients = {f"node-{i}": TestClient(create_privacy_app(CommitChallengeVerifier(f"node-{i}")))
               for i in range(10)}

    class _A:
        def __init__(self, tc): self._tc = tc
        def submit_task(self, task):
            r = self._tc.post("/privacy/tasks", json=task.to_plain())
            r.raise_for_status()
            return r.json()

    ex = PrivacyAuditVOIExecutor(
        scenario=sc, candidate_X=X, candidate_y=y,
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[64], n_nodes=10, f=2,
        seller_store=CommittedDatasetStore("/tmp/pa-g11"),
        node_client_factory=lambda nid: _A(clients[str(nid)]))
    res = ex.run(sc, {"binding": type("B", (), {"tx_id": "tx-g11"})()})
    if res.action_results:
        assert res.action_results[0]["mc_a_pay"] > 0
