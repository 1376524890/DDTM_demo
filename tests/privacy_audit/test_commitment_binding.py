"""Phase 2 exit-gate tests for canonical commitment and task/challenge binding."""

from __future__ import annotations

import numpy as np

from valor.core.hashing import content_hash
from valor.privacy_audit.canonicalize import canonical_mnist_row
from valor.privacy_audit.challenge import generate_challenge
from valor.privacy_audit.claims import make_claim
from valor.privacy_audit.commitment import CommittedDatasetStore
from valor.privacy_audit.merkle import MerkleProof, MerkleSibling
from valor.privacy_audit.models import ClaimType
from valor.privacy_audit.opening import make_opening, verify_opening
from valor.privacy_audit.task import PrivacyAuditTask
from valor.privacy_audit.verifier import AuditExecutionContext, CommitChallengeVerifier
from valor.seller import SellerCommittedDataset


def _store(n=32, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.integers(0, 256, size=(n, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=n)
    store = CommittedDatasetStore("/tmp/pa-binding-test")
    seller = SellerCommittedDataset.create(
        store, dataset_id="d", version="v1", X=X, y=y,
        schema_hash=content_hash({"schema": "TEST"}))
    return seller, seller.commitment, X, y


def _opening(store, idx):
    return store.open_rows([idx])[0]


def test_valid_openings_pass():
    store, commitment, _, _ = _store()
    ch = generate_challenge(task_hash="binding-1", action_id="a1",
                            n_rows=commitment.n_rows, k=8, nonce=b"n" * 32)
    for o in store.open_rows(list(ch.indices)):
        assert verify_opening(o, commitment) is True


def test_payload_tamper_fails():
    store, commitment, X, y = _store()
    o = _opening(store, 0)
    img = X[0].copy()
    img[0] = (int(img[0]) + 1) % 256
    bad = make_opening(index=o.index, row_payload=canonical_mnist_row(o.index, img, y[0]),
                       salt=bytes.fromhex(o.salt), proof=o.proof)
    assert verify_opening(bad, commitment) is False


def test_salt_tamper_fails():
    store, commitment, _, _ = _store()
    o = _opening(store, 0)
    bad = make_opening(index=o.index, row_payload=o.row_payload,
                       salt=b"\x00" * 32, proof=o.proof)
    assert verify_opening(bad, commitment) is False


def test_merkle_proof_tamper_fails():
    store, commitment, _, _ = _store()
    o = _opening(store, 0)
    bad_sibs = tuple(MerkleSibling("0" * 64, s.side) for s in o.proof.siblings)
    bad = make_opening(index=o.index, row_payload=o.row_payload,
                       salt=bytes.fromhex(o.salt),
                       proof=MerkleProof(index=o.index, siblings=bad_sibs))
    assert verify_opening(bad, commitment) is False


def test_wrong_commitment_fails():
    store1, c1, _, _ = _store(seed=0)
    store2, c2, _, _ = _store(seed=1)
    o = store1.open_rows([0])[0]
    assert verify_opening(o, c2) is False


def test_challenge_task_binding_fails_closed():
    store, commitment, _, _ = _store()
    claim = make_claim(
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        value={str(i): 1 for i in range(10)},
        dataset_commitment_hash=commitment.commitment_hash)
    binding = content_hash({"tx": "tx-1", "action": "a1",
                            "commitment": commitment.commitment_hash})
    ch = generate_challenge(task_binding_hash=binding, task_hash=binding,
                            action_id="a1", n_rows=commitment.n_rows, k=4,
                            nonce=b"z" * 32)
    opens = [store.open_rows([i])[0] for i in ch.indices]
    task = PrivacyAuditTask(
        task_id="t1", tx_id="tx-1", commitment=commitment, claim=claim,
        primitive_id="LabelDistributionAudit", task_binding_hash=binding,
        challenge=ch, openings=opens)
    # Finalized task hash includes binding + challenge and is not self-referential.
    assert task.task_binding_hash == binding
    assert task.task_hash != task.task_binding_hash

    verifier = CommitChallengeVerifier("node-0")
    ctx = AuditExecutionContext(commitment=commitment, claim=claim,
                                challenge=ch, openings=opens)
    ev_ok = verifier.execute(task_binding_hash=binding,
                             primitive_id="LabelDistributionAudit", ctx=ctx)
    assert ev_ok.result != "BREACH_EVIDENCE"

    ctx_bad = AuditExecutionContext(commitment=commitment, claim=claim,
                                    challenge=ch, openings=opens)
    ev_bad = verifier.execute(task_binding_hash="wrong-binding",
                              primitive_id="LabelDistributionAudit", ctx=ctx_bad)
    assert ev_bad.result == "BREACH_EVIDENCE"
