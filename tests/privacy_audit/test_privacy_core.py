"""PPA-1/2/3 隐私审计核心测试：Merkle / Commitment / Opening / Primitive / 披露预算。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.privacy_audit import (
    CommittedDatasetStore,
    DisclosureState,
    PrivacyBudgetExceededError,
    canonical_mnist_row,
    generate_challenge,
    make_opening,
    verify_opening,
)
from valor.privacy_audit.canonicalize import canonical_row_from_payload
from valor.privacy_audit.models import ClaimType
from valor.seller import SellerCommittedDataset
from valor.privacy_audit.claims import claim_from_data, make_claim


def _mnist_block(n=200, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 256, size=(n, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=n)
    return X, y


def _make_seller(store_path, X, y, ds="ds1"):
    store = CommittedDatasetStore(store_path)
    return SellerCommittedDataset.create(
        store, dataset_id=ds, version="v1", X=X, y=y, schema_hash="s" * 64)


def test_canonical_row_roundtrip():
    X, y = _mnist_block(1)
    payload = canonical_mnist_row(0, X[0], int(y[0]))
    idx, img, label = canonical_row_from_payload(payload, index=0)
    assert idx == 0 and label == int(y[0])
    assert (img == X[0]).all()


def test_commitment_and_opening_verify():
    X, y = _mnist_block(200)
    seller = _make_seller("/tmp/pa-test", X, y)
    ch = generate_challenge(task_hash="t" * 64, action_id="a1",
                            n_rows=200, k=8, nonce=b"\x01" * 32)
    opens = seller.open_rows(list(ch.indices))
    for o in opens:
        assert verify_opening(o, seller.commitment) is True


def test_tampered_pixel_label_index_salt_fail():
    X, y = _mnist_block(200)
    seller = _make_seller("/tmp/pa-test2", X, y)
    opens = seller.open_rows([3])
    bad = opens[0]
    idx, img, label = canonical_row_from_payload(bad.row_payload, index=3)

    # 改 pixel
    img2 = img.copy(); img2[0] = (int(img2[0]) + 1) % 256
    o2 = make_opening(index=3, row_payload=canonical_mnist_row(3, img2, label),
                      salt=bytes.fromhex(bad.salt), proof=bad.proof)
    assert verify_opening(o2, seller.commitment) is False
    # 改 label
    o3 = make_opening(index=3, row_payload=canonical_mnist_row(3, img, (label + 1) % 10),
                      salt=bytes.fromhex(bad.salt), proof=bad.proof)
    assert verify_opening(o3, seller.commitment) is False
    # 改 index
    o4 = make_opening(index=4, row_payload=canonical_mnist_row(4, img, label),
                      salt=bytes.fromhex(bad.salt), proof=bad.proof)
    assert verify_opening(o4, seller.commitment) is False
    # 改 salt
    o5 = make_opening(index=3, row_payload=bad.row_payload,
                      salt=bytes.fromhex("00" * 32), proof=bad.proof)
    assert verify_opening(o5, seller.commitment) is False


def test_other_dataset_proof_fails():
    X1, y1 = _mnist_block(200, seed=0)
    X2, y2 = _mnist_block(200, seed=1)
    s1 = _make_seller("/tmp/a", X1, y1, "ds1")
    s2 = _make_seller("/tmp/b", X2, y2, "ds2")
    o = s1.open_rows([0])[0]
    assert verify_opening(o, s2.commitment) is False


def test_disclosure_budget_enforced():
    X, y = _mnist_block(1000)
    seller = _make_seller("/tmp/pa-budget", X, y)
    disc = DisclosureState(
        dataset_commitment_hash=seller.commitment.commitment_hash,
        max_unique_rows=50, max_fraction=0.05, max_bytes=50 * 784, _n_rows=1000)
    disc.record(list(range(40)), 40 * 784)
    assert disc.remaining_unique() == 10
    ch = generate_challenge(task_hash="t" * 64, action_id="a1",
                            n_rows=1000, k=20, nonce=b"\x02" * 32)
    from valor.seller.audit_service import SellerAuditService
    svc = SellerAuditService(dataset=seller, disclosure=disc)
    with pytest.raises(PrivacyBudgetExceededError):
        svc.process_challenge(ch)


def test_label_distribution_primitive():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 10, size=500)
    X = rng.integers(0, 256, size=(500, 784), dtype=np.uint8)
    seller = _make_seller("/tmp/pa-cl", X, y)
    claim_true = claim_from_data(
        claim_type=ClaimType.LABEL_DISTRIBUTION, X=X, y=y,
        dataset_commitment_hash=seller.commitment.commitment_hash)
    claim_fake = make_claim(
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        value={str(c): (1000 if c == 0 else 1) for c in range(10)},
        dataset_commitment_hash=seller.commitment.commitment_hash)
    ch = generate_challenge(task_hash="t" * 64, action_id="a1", n_rows=500, k=200, nonce=b"\x03" * 32)
    opens = seller.open_rows(list(ch.indices))
    from valor.privacy_audit.primitives import run_primitive
    out_true = run_primitive("LabelDistributionAudit", opens, claim_true)
    out_fake = run_primitive("LabelDistributionAudit", opens, claim_fake)
    assert out_true.result.value == "PASS"
    assert out_fake.result.value in ("CLAIM_NOT_SUPPORTED", "INCONCLUSIVE")


def test_public_artifact_hides_salts_and_rows():
    X, y = _mnist_block(50)
    seller = _make_seller("/tmp/pa-pub", X, y)
    pub = seller.public_artifact()
    assert "merkle_root" in pub and "n_rows" in pub
    assert "salt" not in str(pub).lower()
    assert "merkle_nodes" not in str(pub)
    assert "row_payload" not in str(pub)
