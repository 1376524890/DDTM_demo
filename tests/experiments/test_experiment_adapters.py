"""Round 6 Phase 19: experiment adapters physically inject failures."""

from __future__ import annotations

import numpy as np
import pytest

from valor.experiments.adapters import (
    InvalidSignatureAuditorTransport, MismatchedDeliveryProvider,
    OfflineAuditorTransport, TamperingSellerProvider,
)


class _FakeClient:
    def submit_task(self, task):
        return {"signature": "abc", "result": "PASS"}


class _FakeSeller:
    def __init__(self):
        from valor.privacy_audit.opening import make_opening
        self._make = make_opening

    def process_challenge(self, challenge):
        return []


def test_offline_transport_raises_for_offline_node():
    def base(nid):
        return _FakeClient()
    t = OfflineAuditorTransport(base, ["node-1"])
    assert isinstance(t("node-0"), _FakeClient)
    with pytest.raises(ConnectionError):
        t("node-1")


def test_invalid_signature_transport_corrupts():
    def base(nid):
        return _FakeClient()
    t = InvalidSignatureAuditorTransport(base, ["node-2"])
    ev = t("node-2").submit_task(object())
    assert ev["signature"] == "0" * 128
    ev0 = t("node-0").submit_task(object())
    assert ev0["signature"] == "abc"


def test_mismatched_delivery_provider():
    p = MismatchedDeliveryProvider()
    r = p.deliver(delivery_commitment="d")
    assert r["verified"] is False
    assert r["reason"] == "SELLER_BREACH_DELIVERY_EXPERIMENT"


def test_tampering_seller_provider_tampers():
    from valor.privacy_audit.verifier import CommitChallengeVerifier
    from valor.privacy_audit.challenge import generate_challenge
    from valor.privacy_audit.claims import claim_from_data
    from valor.privacy_audit.models import ClaimType
    from valor.privacy_audit.verifier import AuditExecutionContext
    from valor.privacy_audit.opening import RowOpening
    from valor.seller import SellerCommittedDataset
    from valor.privacy_audit import CommittedDatasetStore

    rng = np.random.default_rng(1)
    X = rng.integers(0, 256, size=(50, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=50)
    store = CommittedDatasetStore("/tmp/tamper-adapter")
    seller = SellerCommittedDataset.create(store, dataset_id="tamp", version="v1", X=X, y=y, schema_hash="s"*64)
    claim = claim_from_data(claim_type=ClaimType.LABEL_DISTRIBUTION, X=X, y=y,
                            dataset_commitment_hash=seller.commitment.commitment_hash)
    ch = generate_challenge(task_hash="t", action_id="a", n_rows=len(y), k=8)
    opens = [RowOpening.from_plain(o) for o in store.open_rows(seller.dataset_id, list(ch.indices))] if False else [
        __import__("valor.privacy_audit.opening", fromlist=["make_opening"]).make_opening(
            index=o["index"], row_payload=bytes.fromhex(o["row_payload"]),
            salt=bytes.fromhex(o["salt"]),
            proof=__import__("valor.privacy_audit.merkle", fromlist=["MerkleProof"]).MerkleProof.from_plain(o["merkle_proof"]))
        for o in store.open_rows(seller.dataset_id, list(ch.indices))]
    verifier = CommitChallengeVerifier("node-0")
    ctx = AuditExecutionContext(commitment=seller.commitment, claim=claim,
                                challenge=ch, openings=opens)
    ev = verifier.execute("t", "LabelDistributionAudit", ctx)
    assert ev.result != "BREACH_EVIDENCE"
    # tampered openings -> BREACH_EVIDENCE
    raw = store.open_rows(seller.dataset_id, list(ch.indices))
    class _Dummy:
        def process_challenge(self, challenge):
            return raw
    tampered = TamperingSellerProvider(_Dummy())
    topens = tampered.process_challenge(ch)
    ctx2 = AuditExecutionContext(commitment=seller.commitment, claim=claim,
                                 challenge=ch, openings=topens)
    ev2 = verifier.execute("t", "LabelDistributionAudit", ctx2)
    assert ev2.result == "BREACH_EVIDENCE"
