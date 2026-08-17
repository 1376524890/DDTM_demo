"""Listing / Catalog —— 市场层（P2，交接文档第七节）。

Listing 定义「卖什么」：Z_τ = (A_D, R_τ)。包含 seller_id、DataAsset、H(D)、
MetadataClaim、RightsBundle、H(R)、asset_version、availability、provenance。

关键语义：Listing 只定义产品，不直接给出最终成交价。最终卖方最低价仍必须由
P_τ^min 公式计算，而不是简单使用 seller ask（定价公式不被市场层篡改）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash
from valor.core.ids import AssetID, SellerID, new_id
from valor.rights.models import RightsBundle


@dataclass(frozen=True)
class MetadataClaim:
    """元数据/质量声明（供审计定位；不替代真实质量验证）。"""

    claim_id: str
    claims: dict[str, Any]  # 如 {"max_missing_rate": 0.0, "schema": "MNIST-784"}
    declared_by: str = "seller"

    def to_plain(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claims": self.claims,
            "declared_by": self.declared_by,
        }


@dataclass(frozen=True)
class Listing:
    """市场可交易产品 Z_τ = (A_D, R_τ)。"""

    listing_id: str
    seller_id: str
    asset_id: str
    asset_version: str
    data_commitment: str  # H(D)
    metadata_claim: MetadataClaim
    rights: RightsBundle
    availability: str  # "ACTIVE" / "SUSPENDED"
    provenance: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        for name, h in (("data_commitment", self.data_commitment),):
            if not h or len(h) != 64:
                from valor.core.errors import CommitBindingError

                raise CommitBindingError(f"{name} 非法承诺哈希: {h!r}")

    @property
    def rights_hash(self) -> str:
        return self.rights.rights_hash

    @property
    def product_hash(self) -> str:
        """Z_τ 产品承诺：H(A_D 承诺 ∥ R_τ 承诺)。"""
        return content_hash({
            "listing_id": self.listing_id,
            "data_commitment": self.data_commitment,
            "rights_hash": self.rights_hash,
        })

    def to_plain(self) -> dict:
        return {
            "listing_id": self.listing_id,
            "seller_id": self.seller_id,
            "asset_id": self.asset_id,
            "asset_version": self.asset_version,
            "data_commitment": self.data_commitment,
            "metadata_claim": self.metadata_claim.to_plain(),
            "rights": self.rights.to_plain(),
            "rights_hash": self.rights_hash,
            "product_hash": self.product_hash,
            "availability": self.availability,
            "provenance": self.provenance,
            "created_at": self.created_at,
        }


def create_listing(
    *,
    seller_id: str,
    asset_id: str,
    asset_version: str,
    data_commitment: str,
    rights: RightsBundle,
    metadata_claims: dict[str, Any] | None = None,
    provenance: str = "",
    created_at: str = "",
    listing_id: str = "",
) -> Listing:
    """便捷构造 Listing，自动生成 listing_id 与 metadata claim。

    listing_id 可显式传入以实现确定性重放（§69）。
    """
    return Listing(
        listing_id=listing_id or new_id("list", entropy=12),
        seller_id=seller_id,
        asset_id=asset_id,
        asset_version=asset_version,
        data_commitment=data_commitment,
        metadata_claim=MetadataClaim(
            claim_id=new_id("claim", entropy=8),
            claims=metadata_claims or {},
        ),
        rights=rights,
        availability="ACTIVE",
        provenance=provenance,
        created_at=created_at,
    )


__all__ = ["Listing", "MetadataClaim", "create_listing"]
