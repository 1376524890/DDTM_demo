"""P0-F 证据签名测试：真实 Ed25519 签名 + 验签 + 非法签名不计入 quorum。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.security.signing import (
    EvidenceSignatureError,
    SigningKeyPair,
    generate_node_keyring,
    sign_evidence,
    verify_evidence_signature,
)


def test_keypair_sign_and_verify():
    kp = SigningKeyPair.generate("node-0")
    payload = {"node_id": "node-0", "result": "PASS", "merkle_ok": True}
    sig = sign_evidence(kp, payload)
    assert len(sig) == 128  # Ed25519 签名 hex 长度
    assert verify_evidence_signature(
        public_key_hex=kp.public_key_hex, evidence_plain=payload, signature=sig)


def test_signature_fails_on_tamper():
    kp = SigningKeyPair.generate("node-0")
    payload = {"node_id": "node-0", "result": "PASS", "merkle_ok": True}
    sig = sign_evidence(kp, payload)
    tampered = dict(payload)
    tampered["result"] = "BREACH_EVIDENCE"
    assert not verify_evidence_signature(
        public_key_hex=kp.public_key_hex, evidence_plain=tampered, signature=sig)


def test_wrong_key_fails():
    kp1 = SigningKeyPair.generate("node-0")
    kp2 = SigningKeyPair.generate("node-0")
    payload = {"result": "PASS"}
    sig = sign_evidence(kp1, payload)
    assert not verify_evidence_signature(
        public_key_hex=kp2.public_key_hex, evidence_plain=payload, signature=sig)


def test_fingerprint_distinct():
    k1 = SigningKeyPair.generate("a").key_fingerprint
    k2 = SigningKeyPair.generate("b").key_fingerprint
    assert k1 != k2
