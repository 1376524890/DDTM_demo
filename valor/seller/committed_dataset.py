"""SellerCommittedDataset —— 卖方承诺数据集（PPA-2）。

卖方持有：X, y, salts, merkle 树。对外只暴露：
    - 公开承诺 artifact（不含 salts/树/数据）
    - openings 服务（按挑战 indices 揭示行 + salt + Merkle proof）
"""

from __future__ import annotations

import numpy as np

from valor.privacy_audit.commitment import (
    CommittedDatasetStore,
    DatasetCommitment,
)
from valor.privacy_audit.opening import RowOpening, make_opening
from valor.privacy_audit.merkle import MerkleProof


class SellerCommittedDataset:
    """卖方持有的已承诺数据集（私有数据 + salts 不对外）。"""

    def __init__(self, store: CommittedDatasetStore, dataset_id: str) -> None:
        self._store = store
        self.dataset_id = dataset_id
        self.commitment: DatasetCommitment = store.get_commitment(dataset_id)

    @classmethod
    def create(
        cls, store: CommittedDatasetStore, *, dataset_id: str, version: str,
        X: np.ndarray, y: np.ndarray, schema_hash: str,
    ) -> "SellerCommittedDataset":
        store.store(dataset_id=dataset_id, version=version, X=X, y=y,
                    schema_hash=schema_hash)
        return cls(store, dataset_id)

    def public_artifact(self) -> dict:
        """市场公开承诺（不含 salts/树/数据）。"""
        return self.commitment.public_artifact()

    def open_rows(self, indices: list[int]) -> list[RowOpening]:
        """按 indices 选择性揭示行（挑战用）。校验 indices 在界内。"""
        opens = []
        for i in indices:
            if not (0 <= i < self.commitment.n_rows):
                raise IndexError(f"index {i} 越界 (n={self.commitment.n_rows})")
            rec = self._store.open_row(self.dataset_id, i)
            proof = MerkleProof.from_plain(rec["merkle_proof"])
            opens.append(make_opening(
                index=i, row_payload=bytes.fromhex(rec["row_payload"]),
                salt=bytes.fromhex(rec["salt"]), proof=proof))
        return opens

    @property
    def n_rows(self) -> int:
        return self.commitment.n_rows


__all__ = ["SellerCommittedDataset"]
