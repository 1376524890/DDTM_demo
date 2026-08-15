"""MarketCatalog —— 市场目录（P2，交接文档第七节）。

维护 listings 注册表：上架 / 查询 / 下架。listing 按 availability 过滤，
提供按 listing_id 或 (asset_id, version) 检索。
"""

from __future__ import annotations

from typing import Any

from valor.core.errors import VALORError

from .listing import Listing


class CatalogError(VALORError):
    code = "CATALOG"


class MarketCatalog:
    """市场目录：listing 注册表。"""

    def __init__(self) -> None:
        self._listings: dict[str, Listing] = {}

    def add(self, listing: Listing) -> None:
        if listing.listing_id in self._listings:
            raise CatalogError(f"listing 已存在: {listing.listing_id}")
        self._listings[listing.listing_id] = listing

    def get(self, listing_id: str) -> Listing:
        if listing_id not in self._listings:
            raise CatalogError(f"listing 不存在: {listing_id}")
        return self._listings[listing_id]

    def active(self) -> list[Listing]:
        return [l for l in self._listings.values() if l.availability == "ACTIVE"]

    def by_asset(self, asset_id: str) -> list[Listing]:
        return [l for l in self._listings.values()
                if l.asset_id == asset_id and l.availability == "ACTIVE"]

    def suspend(self, listing_id: str) -> None:
        l = self.get(listing_id)
        self._listings[listing_id] = Listing(
            listing_id=l.listing_id, seller_id=l.seller_id,
            asset_id=l.asset_id, asset_version=l.asset_version,
            data_commitment=l.data_commitment,
            metadata_claim=l.metadata_claim, rights=l.rights,
            availability="SUSPENDED", provenance=l.provenance,
            created_at=l.created_at,
        )

    def to_plain(self) -> dict[str, Any]:
        return {
            "listings": {
                lid: l.to_plain() for lid, l in self._listings.items()
            }
        }


__all__ = ["MarketCatalog", "CatalogError"]
