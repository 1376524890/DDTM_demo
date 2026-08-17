"""Evidence 签名与验签（规范 §19 / P0-F）。

每个 auditor node 持有 Ed25519 密钥对。NodeRegistry 记录 node_id / public_key /
key_fingerprint。Evidence canonical payload 签名：

    sig_i = Sign_sk_i(H(Canonical(E_i_without_signature)))

Scheduler 收到 evidence 后必须先验签，非法签名 → INVALID_EVIDENCE_SIGNATURE，
不得计入 result_counts / quorum（MFC-G05 / MFC-G06）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from valor.core.hashing import content_hash, sha256_hex


class EvidenceSignatureError(Exception):
    """证据签名无效。"""

    code = "INVALID_EVIDENCE_SIGNATURE"


@dataclass(frozen=True)
class SigningKeyPair:
    """一个节点的一对 Ed25519 密钥。"""

    node_id: str
    private_key: ed25519.Ed25519PrivateKey
    public_key: ed25519.Ed25519PublicKey

    @property
    def public_key_hex(self) -> str:
        return self.public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    @property
    def key_fingerprint(self) -> str:
        return sha256_hex(self.public_key_hex.encode())[:32]

    @classmethod
    def generate(cls, node_id: str) -> "SigningKeyPair":
        priv = ed25519.Ed25519PrivateKey.generate()
        return cls(node_id=node_id, private_key=priv, public_key=priv.public_key())

    def sign(self, payload: bytes) -> bytes:
        return self.private_key.sign(payload)


def canonical_payload_without_signature(evidence_plain: dict) -> bytes:
    """evidence canonical payload（不含 signature 字段）→ bytes。"""
    payload = {k: v for k, v in evidence_plain.items()
               if k not in ("signature", "evidence_id")}
    return content_hash(payload).encode()


def sign_evidence(kp: SigningKeyPair, evidence_plain: dict) -> str:
    """sig_i = Sign_sk_i(H(Canonical(E_i_without_signature)))。"""
    payload = canonical_payload_without_signature(evidence_plain)
    return kp.sign(payload).hex()


def verify_evidence_signature(
    *, public_key_hex: str, evidence_plain: dict, signature: str,
) -> bool:
    """用节点公钥验签 canonical payload。失败返回 False（INVALID_EVIDENCE_SIGNATURE）。"""
    try:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(public_key_hex))
        pub.verify(bytes.fromhex(signature),
                   canonical_payload_without_signature(evidence_plain))
        return True
    except Exception:  # noqa: BLE001
        return False


def generate_node_keyring(node_ids: list[str]) -> dict[str, SigningKeyPair]:
    """为一批节点生成密钥对，返回 {node_id: keypair}。"""
    return {nid: SigningKeyPair.generate(nid) for nid in node_ids}


__all__ = [
    "SigningKeyPair", "generate_node_keyring",
    "sign_evidence", "verify_evidence_signature",
    "canonical_payload_without_signature", "EvidenceSignatureError",
]
