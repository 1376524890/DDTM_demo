"""Phase 1: formal process-isolated auditor transport + node-local signing.

Checks:
- each auditor subprocess exposes public_key/key_fingerprint and holds its key in child
- AuditorIdentityRegistry sees only public identities
- coordinator-held key cannot produce evidence accepted under node-i public key
"""

from __future__ import annotations

import numpy as np
import pytest

from valor.privacy_audit.process_isolated import ProcessHttpAuditorCluster
from valor.security.signing import SigningKeyPair, verify_evidence_signature


def _evidence_plain(node_id: str) -> dict:
    return {
        "node_id": node_id,
        "task_id": "t-1",
        "execution_mode": "COMMIT_CHALLENGE",
        "claim_hash": "c" * 64,
        "commitment_hash": "d" * 64,
        "challenge_id": "ch-1",
        "challenge_hash": "e" * 64,
        "opening_indices": [0, 1],
        "opening_commitment_hashes": ["h0", "h1"],
        "merkle_verification_passed": True,
        "disclosed_rows": 2,
        "disclosed_bytes": 2 * 784,
        "test_statistic": 1.2,
        "p_value": 0.3,
        "result": "PASS",
        "execution_hash": "x" * 64,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "evidence_id": "evt-1",
    }


def test_process_cluster_exposes_public_identity_only():
    cluster = ProcessHttpAuditorCluster(n=2)
    try:
        for nid, client in cluster._pool._clients.items():
            health = client.health()
            assert health["node_id"] == nid
            assert health["public_key"]
            assert health["key_fingerprint"]
            assert health["private_key_in_child"] is True
            assert cluster.registry.public_key(nid) == health["public_key"]
            assert cluster.registry.key_fingerprint(nid) == health["key_fingerprint"]
    finally:
        cluster.close()


def test_coordinator_cannot_sign_valid_evidence_for_node_without_private_key():
    # node-i has its own key; coordinator does not have it.
    node_key = SigningKeyPair.generate("node-0")
    coordinator_key = SigningKeyPair.generate("coordinator")
    ev = _evidence_plain("node-0")
    from valor.security.signing import sign_evidence

    ev["signature"] = sign_evidence(coordinator_key, ev)
    # Verification with the node public key must fail.
    assert verify_evidence_signature(
        public_key_hex=node_key.public_key_hex,
        evidence_plain=ev,
        signature=ev["signature"],
    ) is False
    # Verification with coordinator key passes, but that key is not registered.
    assert verify_evidence_signature(
        public_key_hex=coordinator_key.public_key_hex,
        evidence_plain=ev,
        signature=ev["signature"],
    ) is True
