"""DatasetCommitment / CommittedRow / CommittedDatasetStore（PPA-1/2）。

对齐方案 §2/§3/§4/§6：
    DatasetCommitment = (dataset_id, version, n_rows, schema_hash,
                         canonicalization_spec_hash, merkle_root, dataset_hash,
                         commitment_hash)
    datasetHash = H(canonical(D))          # 完整数据一致性
    MerkleRoot(D)                          # 局部开启
    commitment_hash = H(datasetHash, merkleRoot, schemaHash, n, canonVersion)
    每个行独立 salt（256-bit），salt 仅在 reveal 时公开。

市场公开只含 dataset_id/n_rows/schema_hash/merkle_root/dataset_hash/commitment_hash；
merkle_nodes.bin 与 row_salts.bin 留在卖方（seller_private/），绝不发给 auditor。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from valor.core.hashing import content_hash, sha256_hex

from .canonicalize import canonical_mnist_row
from .merkle import MerkleTree, MerkleProof, leaf_hash

CANONICALIZATION_SPEC_HASH = sha256_hex(
    content_hash({"canonical": "VALOR-MNIST-ROW-V1", "endian": "le"}).encode())


@dataclass(frozen=True)
class CommittedRow:
    """一行承诺：index + 独立 salt + leaf_hash。"""

    index: int
    salt: bytes  # 256-bit
    leaf_hash: str

    def to_plain(self) -> dict:
        return {"index": self.index, "salt": self.salt.hex(), "leaf_hash": self.leaf_hash}


@dataclass(frozen=True)
class DatasetCommitment:
    """数据集承诺（方案 §2）。"""

    dataset_id: str
    version: str
    n_rows: int
    schema_hash: str
    canonicalization_spec_hash: str
    merkle_root: str
    dataset_hash: str
    commitment_hash: str

    def to_plain(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "n_rows": self.n_rows,
            "schema_hash": self.schema_hash,
            "canonicalization_spec_hash": self.canonicalization_spec_hash,
            "merkle_root": self.merkle_root,
            "dataset_hash": self.dataset_hash,
            "commitment_hash": self.commitment_hash,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "DatasetCommitment":
        return cls(
            dataset_id=d["dataset_id"], version=d["version"], n_rows=d["n_rows"],
            schema_hash=d["schema_hash"],
            canonicalization_spec_hash=d["canonicalization_spec_hash"],
            merkle_root=d["merkle_root"], dataset_hash=d["dataset_hash"],
            commitment_hash=d["commitment_hash"],
        )

    def public_artifact(self) -> dict:
        """市场公开版本（不含 merkle_nodes / salts）。"""
        return {
            "dataset_id": self.dataset_id,
            "n_rows": self.n_rows,
            "schema_hash": self.schema_hash,
            "merkle_root": self.merkle_root,
            "dataset_hash": self.dataset_hash,
            "commitment_hash": self.commitment_hash,
            "canonicalization_spec_hash": self.canonicalization_spec_hash,
        }


def build_dataset_commitment(
    *,
    dataset_id: str,
    version: str,
    X: np.ndarray,
    y: np.ndarray,
    schema_hash: str,
) -> tuple[DatasetCommitment, MerkleTree, list[CommittedRow]]:
    """构建数据集承诺：生成每行 salt → leaf → Merkle 树 → DatasetCommitment。

    返回 (commitment, tree, committed_rows)。tree 与 committed_rows（含 salt）
    属于卖方私有，不公开。
    """
    import secrets

    n = len(X)
    salts: list[bytes] = [secrets.token_bytes(32) for _ in range(n)]
    leaves: list[bytes] = []
    committed_rows: list[CommittedRow] = []
    for i in range(n):
        row_bytes = canonical_mnist_row(i, X[i], int(y[i]))
        lf = leaf_hash(dataset_id, version, i, salts[i], row_bytes)
        leaves.append(lf)
        committed_rows.append(CommittedRow(i, salts[i], lf.hex()))
    tree = MerkleTree(leaves)
    dataset_hash = content_hash({
        "dataset_id": dataset_id, "version": version,
        "rows": [canonical_mnist_row(i, X[i], int(y[i])).hex()
                 for i in range(n)],
    })
    commitment_hash = sha256_hex(content_hash({
        "datasetHash": dataset_hash,
        "merkleRoot": tree.root,
        "schemaHash": schema_hash,
        "n": n,
        "canonicalizationVersion": CANONICALIZATION_SPEC_HASH,
    }).encode())
    commitment = DatasetCommitment(
        dataset_id=dataset_id, version=version, n_rows=n,
        schema_hash=schema_hash,
        canonicalization_spec_hash=CANONICALIZATION_SPEC_HASH,
        merkle_root=tree.root, dataset_hash=dataset_hash,
        commitment_hash=commitment_hash,
    )
    return commitment, tree, committed_rows


class CommittedDatasetStore:
    """卖方私有存储：承诺 + 树 + 行数据 + salts（PPA-2）。

    merkle_nodes / row_salts / 原始行 绝不发给 auditor。
    """

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self._datasets: dict[str, dict] = {}  # dataset_id -> store record

    def store(
        self,
        *,
        dataset_id: str,
        version: str,
        X: np.ndarray,
        y: np.ndarray,
        schema_hash: str,
    ) -> DatasetCommitment:
        commitment, tree, rows = build_dataset_commitment(
            dataset_id=dataset_id, version=version, X=X, y=y,
            schema_hash=schema_hash)
        record = {
            "commitment": commitment,
            "tree": tree,
            "committed_rows": rows,
            "X": X,
            "y": y,
        }
        self._datasets[dataset_id] = record
        self._persist(dataset_id, commitment, tree, rows)
        return commitment

    def _persist(self, dataset_id, commitment, tree, rows) -> None:
        d = self.root_dir / "seller_private" / "commitment"
        d.mkdir(parents=True, exist_ok=True)
        (d / "dataset_commitment.json").write_text(
            __import__("json").dumps(commitment.to_plain(), indent=2), encoding="utf-8")
        (d / "merkle_nodes.bin").write_bytes(
            b"".join(h.encode() for level in tree._levels for h in level))
        (d / "row_salts.bin").write_bytes(
            b"".join(r.salt for r in rows))

    def get_commitment(self, dataset_id: str) -> DatasetCommitment:
        return self._datasets[dataset_id]["commitment"]

    def get_row_payload(self, dataset_id: str, index: int) -> bytes:
        """卖方按 index 生成 canonical row payload（reveal 时用）。"""
        rec = self._datasets[dataset_id]
        return canonical_mnist_row(index, rec["X"][index], int(rec["y"][index]))

    def open_row(self, dataset_id: str, index: int) -> dict:
        """生成单个 opening（row_payload + salt + merkle_proof）。"""
        rec = self._datasets[dataset_id]
        row = rec["committed_rows"][index]
        proof = rec["tree"].proof(index)
        payload = self.get_row_payload(dataset_id, index)
        return {
            "index": index,
            "row_payload": payload.hex(),
            "salt": row.salt.hex(),
            "merkle_proof": proof.to_plain(),
        }

    def open_rows(self, dataset_id: str, indices: list[int]) -> list[dict]:
        return [self.open_row(dataset_id, i) for i in indices]


__all__ = [
    "DatasetCommitment", "CommittedRow", "build_dataset_commitment",
    "CommittedDatasetStore",
]
