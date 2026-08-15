"""Merkle 树（方案 §5）。

leaf_i = H(domain ∥ datasetID ∥ version ∥ i ∥ salt_i ∥ canonical(row_i))
MerkleProof 带 MerkleSibling(side=LEFT/RIGHT) 供验证。

必须测试：正确行 PASS；改 pixel/label/index/salt/proof/其他 dataset 均 FAIL。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from valor.core.hashing import sha256_hex

# 域分隔符，防止不同 hash 用途间语义混淆
LEAF_DOMAIN = "VALOR-DATASET-ROW-V1"


@dataclass(frozen=True)
class MerkleSibling:
    hash: str
    side: Literal["LEFT", "RIGHT"]


@dataclass(frozen=True)
class MerkleProof:
    index: int
    siblings: tuple[MerkleSibling, ...]

    def to_plain(self) -> dict:
        return {
            "index": self.index,
            "siblings": [{"hash": s.hash, "side": s.side} for s in self.siblings],
        }

    @classmethod
    def from_plain(cls, d: dict) -> "MerkleProof":
        return cls(
            index=d["index"],
            siblings=tuple(
                MerkleSibling(s["hash"], s["side"]) for s in d["siblings"]
            ),
        )


class MerkleTree:
    """标准二进制 Merkle 树（叶子已含 salt，父 = H(left∥right)）。"""

    def __init__(self, leaves: Sequence[bytes]) -> None:
        if not leaves:
            raise ValueError("Merkle 树需至少一个叶子")
        # leaf_hash() 返回 hex 字符串的 utf-8 bytes → 解码为 64 字符 hex
        self._leaves: list[str] = [h.decode("ascii") for h in leaves]
        self._levels: list[list[str]] = self._build(self._leaves)

    def _build(self, leaves: list[str]) -> list[list[str]]:
        level = leaves
        levels = [level]
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                a = level[i]
                b = level[i + 1] if i + 1 < len(level) else a
                nxt.append(sha256_hex((a + b).encode()))
            levels.append(nxt)
            level = nxt
        return levels

    @property
    def root(self) -> str:
        return self._levels[-1][0]

    @property
    def n_leaves(self) -> int:
        return len(self._leaves)

    def proof(self, index: int) -> MerkleProof:
        if not (0 <= index < len(self._leaves)):
            raise IndexError(f"index {index} 越界")
        siblings: list[MerkleSibling] = []
        idx = index
        for level in self._levels[:-1]:
            if idx % 2 == 0:
                sib = idx + 1
                side: Literal["LEFT", "RIGHT"] = "RIGHT"
            else:
                sib = idx - 1
                side = "LEFT"
            # 奇数层复制节点：若 sibling 越界，用自身（build 时复制了最后节点）
            if sib >= len(level):
                sib = idx
            siblings.append(MerkleSibling(level[sib], side))
            idx //= 2
        return MerkleProof(index=index, siblings=tuple(siblings))

    @staticmethod
    def verify(*, leaf: bytes, index: int, proof: MerkleProof, root: str) -> bool:
        h = leaf.decode("ascii")
        idx = index
        for sib in proof.siblings:
            if sib.side == "RIGHT":
                h = sha256_hex((h + sib.hash).encode())
            else:
                h = sha256_hex((sib.hash + h).encode())
            idx //= 2
        return h == root


def leaf_hash(
    dataset_id: str,
    version: str,
    index: int,
    salt: bytes,
    row_bytes: bytes,
) -> bytes:
    """leaf_i = H(domain ∥ datasetID ∥ version ∥ i ∥ salt_i ∥ row_bytes)。"""
    from valor.core.hashing import content_hash

    return content_hash({
        "domain": LEAF_DOMAIN,
        "dataset_id": dataset_id,
        "version": version,
        "index": index,
        "salt": salt.hex(),
        "row": row_bytes.hex(),
    }).encode()


__all__ = [
    "MerkleSibling", "MerkleProof", "MerkleTree", "leaf_hash", "LEAF_DOMAIN",
]
