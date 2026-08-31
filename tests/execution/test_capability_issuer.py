"""Round 6 Phase 17: CapabilityToken unforgeability + worker start gate."""

from __future__ import annotations

import copy
from dataclasses import replace

import pytest

from valor.execution.secure_execution import CapabilityIssuer, CapabilityToken


def _issued(issuer):
    return issuer.issue(
        tx_id="tx-1", job_spec_hash="job", dataset_commitment="d",
        rights_hash="r", actor="buyer_org_A", purpose="digit-classification",
        algorithm_hash="alg", output_policy="MODEL_ARTIFACT",
        execution_profile="ep", expiry="2099-12-31", nonce="n1",
    )


def test_capability_verifies_and_rejects_actor_mutation():
    issuer = CapabilityIssuer("issuer-1")
    cap = _issued(issuer)
    assert issuer.verify(cap) is True
    bad = replace(cap, actor="buyer_org_B")
    assert issuer.verify(bad) is False


def test_capability_rejects_purpose_expiry_signature_mutation():
    issuer = CapabilityIssuer("issuer-1")
    cap = _issued(issuer)
    assert issuer.verify(replace(cap, purpose="marketing")) is False
    assert issuer.verify(replace(cap, expiry="2000-01-01")) is False
    assert issuer.verify(replace(cap, signature="0" * 128)) is False


def test_capability_nonce_replay_rejected():
    issuer = CapabilityIssuer("issuer-1")
    cap = _issued(issuer)
    assert issuer.verify(cap) is True
    assert issuer.verify(cap) is False  # single-use replay


def test_worker_execute_requires_valid_capability():
    from valor.execution.secure_execution import LocalIsolatedProvider
    prov = LocalIsolatedProvider()
    cap = prov.issuer.issue(
        tx_id="tx", job_spec_hash="job", dataset_commitment="d", rights_hash="r",
        actor="a", purpose="p", algorithm_hash="alg", output_policy="out",
        execution_profile="ep", expiry="2099-12-31", nonce="n2",
    )
    job = type("J", (), {"job_spec_hash": "job",
                         "dataset_commitment_hash": "d"})()
    bad = replace(cap, actor="mallory")
    with pytest.raises(ValueError, match="CAPABILITY_INVALID"):
        prov.execute(bad, job, [], [])


def test_invalid_forged_token_does_not_consume_nonce():
    issuer = CapabilityIssuer("issuer-1")
    cap = _issued(issuer)
    forged = replace(cap, actor="mallory", nonce="fresh-nonce")
    assert issuer.verify(forged) is False
    # nonce must NOT have been consumed by the invalid token
    good = issuer.issue(
        tx_id="tx-1", job_spec_hash="job", dataset_commitment="d",
        rights_hash="r", actor="buyer_org_A", purpose="digit-classification",
        algorithm_hash="alg", output_policy="MODEL_ARTIFACT",
        execution_profile="ep", expiry="2099-12-31", nonce="fresh-nonce",
    )
    assert issuer.verify(good) is True


def test_capability_uses_injectable_clock():
    from datetime import datetime, timezone
    from valor.execution.secure_execution import ClockProvider

    clock = ClockProvider(now=datetime(2099, 1, 1, tzinfo=timezone.utc))
    issuer = CapabilityIssuer("issuer-clock", clock=clock)
    cap = issuer.issue(
        tx_id="tx", job_spec_hash="job", dataset_commitment="d",
        rights_hash="r", actor="a", purpose="p", algorithm_hash="alg",
        output_policy="out", execution_profile="ep",
        expiry="2100-01-01", nonce="clock-nonce",
    )
    assert issuer.verify(cap) is True
    clock.set_now(datetime(2101, 1, 1, tzinfo=timezone.utc))
    assert issuer.verify(cap) is False
