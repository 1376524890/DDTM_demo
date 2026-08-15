"""TransactionBinding —— 交易绑定 τ（P2，主链阶段 10-11）。

买方从市场目录选择 listing/权利束，构建交易绑定：
    τ = (tx_id, seller_id, buyer_id, listing, rights_selected, binding_hash)

binding_hash = H(listing ∥ rights ∥ buyer ∥ seller ∥ tx_id)，用于后续
所有阶段引用同一个不可篡改的交易身份。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from valor.core.hashing import content_hash
from valor.core.ids import new_id
from valor.market.listing import Listing


@dataclass(frozen=True)
class TransactionBinding:
    """一次交易绑定的完整身份。"""

    tx_id: str
    seller_id: str
    buyer_id: str
    listing: Listing
    rights_selected: Any  # RightsBundle（与 listing.rights 一致）
    note: str = ""

    @property
    def binding_hash(self) -> str:
        return content_hash({
            "tx_id": self.tx_id,
            "seller_id": self.seller_id,
            "buyer_id": self.buyer_id,
            "listing_id": self.listing.listing_id,
            "product_hash": self.listing.product_hash,
            "rights_hash": self.rights_selected.rights_hash,
        })

    def to_plain(self) -> dict:
        return {
            "tx_id": self.tx_id,
            "seller_id": self.seller_id,
            "buyer_id": self.buyer_id,
            "listing": self.listing.to_plain(),
            "rights_hash": self.rights_selected.rights_hash,
            "binding_hash": self.binding_hash,
            "note": self.note,
        }


def build_binding(
    *,
    listing: Listing,
    seller_id: str,
    buyer_id: str,
    tx_id: str | None = None,
    note: str = "",
) -> TransactionBinding:
    """构造交易绑定；自动生成 tx_id 若未提供。"""
    return TransactionBinding(
        tx_id=tx_id or new_id("tx", entropy=12),
        seller_id=seller_id,
        buyer_id=buyer_id,
        listing=listing,
        rights_selected=listing.rights,
        note=note,
    )


__all__ = ["TransactionBinding", "build_binding"]
