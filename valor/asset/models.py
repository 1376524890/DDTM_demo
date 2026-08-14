"""数据资产与版本模型（规范 §3.1）。

A_D = (assetID, versionID, D, M_D, H(D), H(M_D), ProvenanceRef)

实际数据对象 D 不直接入哈希（体积/隐私），而是记录其承诺哈希 H(D)；
元数据声明 M_D（含质量声明、合同声明）同样记录 H(M_D)。versionID 保证
后续更新不复用旧对象承诺。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


@dataclass(frozen=True)
class AssetVersion:
    """资产的一个不可变版本。

    data_commitment = H(D)：数据对象承诺哈希（对 canonical 化的数据摘要）
    metadata_commitment = H(M_D)：元数据/声明承诺哈希
    """

    asset_id: str
    version_id: str
    data_commitment: str
    metadata_commitment: str
    provenance_ref: str | None = None
    # 可选：原始数据摘要描述（供审计定位，不存数据本身）
    data_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # 承诺哈希必须为非空 64 位 hex（SHA-256）
        for name, h in (
            ("data_commitment", self.data_commitment),
            ("metadata_commitment", self.metadata_commitment),
        ):
            if not h or len(h) != 64:
                from valor.core.errors import CommitBindingError

                raise CommitBindingError(f"{name} 非法承诺哈希: {h!r}")

    def to_plain(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "version_id": self.version_id,
            "data_commitment": self.data_commitment,
            "metadata_commitment": self.metadata_commitment,
            "provenance_ref": self.provenance_ref,
            "data_summary": self.data_summary,
        }


@dataclass(frozen=True)
class DataAsset:
    """可交易数据资产（规范 §3.1）。可含多个版本；version_id 唯一。"""

    asset_id: str
    versions: tuple[AssetVersion, ...] = field(default_factory=tuple)

    def version(self, version_id: str) -> AssetVersion:
        for v in self.versions:
            if v.version_id == version_id:
                return v
        raise KeyError(f"资产 {self.asset_id} 不存在版本 {version_id}")

    def to_plain(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "versions": [v.to_plain() for v in self.versions],
        }
