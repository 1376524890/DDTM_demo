"""RowOpening + verify_opening（方案 §13/§14/§28）。

RowOpening = (index, row_payload, salt, merkle_proof, opening_hash)。
verify_opening 重新构造 leaf_i = H(domain∥datasetID∥version∥i∥salt_i∥row_i)，
然后 MerkleVerify(leaf_i, proof_i, root)。

任何一个 opening 失败 → BREACH_EVIDENCE（seller breach），不是 QUALITY_FAIL。
"""

from __future__ import annotations

from dataclasses import dataclass

from valor.core.hashing import content_hash

from .commitment import DatasetCommitment
from .merkle import MerkleProof, leaf_hash


@dataclass(frozen=True)
class RowOpening:
    index: int
    row_payload: bytes  # canonical row
    salt: str  # hex
    proof: MerkleProof
    opening_hash: str

    def to_plain(self) -> dict:
        return {
            "index": self.index,
            "row_payload": self.row_payload.hex(),
            "salt": self.salt,
            "merkle_proof": self.proof.to_plain(),
            "opening_hash": self.opening_hash,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "RowOpening":
        return cls(
            index=d["index"], row_payload=bytes.fromhex(d["row_payload"]),
            salt=d["salt"], proof=MerkleProof.from_plain(d["merkle_proof"]),
            opening_hash=d["opening_hash"],
        )


def make_opening(
    *, index: int, row_payload: bytes, salt: bytes, proof: MerkleProof,
) -> RowOpening:
    opening_hash = content_hash({
        "index": index, "row": row_payload.hex(), "salt": salt.hex(),
        "proof": proof.to_plain(),
    })
    return RowOpening(
        index=index, row_payload=row_payload, salt=salt.hex(),
        proof=proof, opening_hash=opening_hash,
    )


def verify_opening(
    opening: RowOpening,
    commitment: DatasetCommitment,
) -> bool:
    """验证 opening 是否绑定到 commitment 的 Merkle 根。"""
    try:
        salt = bytes.fromhex(opening.salt)
    except ValueError:
        return False
    leaf = leaf_hash(
        commitment.dataset_id, commitment.version, opening.index,
        salt, opening.row_payload,
    )
    from .merkle import MerkleTree

    return MerkleTree.verify(
        leaf=leaf, index=opening.index, proof=opening.proof,
        root=commitment.merkle_root,
    )


__all__ = ["RowOpening", "make_opening", "verify_opening"]
