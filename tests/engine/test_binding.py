"""P2 Listing / Catalog / TransactionBinding 测试。"""

from __future__ import annotations

import pytest

from valor.adapters import MNISTDatasetAdapter, MNISTTrainerAdapter
from valor.engine.binding import TransactionBinding, build_binding
from valor.market import MarketCatalog, create_listing
from valor.rights.models import RightsBundle
from valor.core.enums import DeliveryMode


def _mnist_listing(data_commitment="d" * 64):
    rights = RightsBundle(
        r_class="data", access_mode=DeliveryMode.COMPUTE_ONLY,
        t0="2026-01-01T00:00:00Z", t1="2026-12-31T00:00:00Z", q=1000,
        purposes=frozenset({"digit-classification"}),
        scope="buyer_org_A", exclusivity=False, redistribution=False,
        derivative=True, not_applicable_reason="retention/delete via ODRL policy",
    )
    return create_listing(
        seller_id="seller-1", asset_id="asset-mnist", asset_version="v1",
        data_commitment=data_commitment, rights=rights,
        metadata_claims={"schema": "MNIST-784", "classes": 10},
    )


def test_create_listing_has_hashes():
    l = _mnist_listing()
    assert l.listing_id.startswith("list-")
    assert len(l.data_commitment) == 64
    assert len(l.rights_hash) == 64
    assert len(l.product_hash) == 64
    assert l.availability == "ACTIVE"


def test_catalog_add_get_suspend():
    l = _mnist_listing()
    cat = MarketCatalog()
    cat.add(l)
    assert cat.get(l.listing_id) == l
    assert len(cat.active()) == 1
    cat.suspend(l.listing_id)
    assert len(cat.active()) == 0
    with pytest.raises(Exception):
        cat.add(l)  # 重复上架拒绝


def test_binding_hash_stable():
    l = _mnist_listing()
    b1 = build_binding(listing=l, seller_id="seller-1", buyer_id="buyer-1")
    b2 = build_binding(listing=l, seller_id="seller-1", buyer_id="buyer-1")
    assert b1.tx_id != b2.tx_id  # 随机 tx_id
    # binding_hash 包含 tx_id → 不同 tx 不同 hash
    assert b1.binding_hash != b2.binding_hash


def test_binding_references_listing_product():
    l = _mnist_listing()
    b = build_binding(listing=l, seller_id="seller-1", buyer_id="buyer-1")
    assert b.binding_hash is not None
    assert b.to_plain()["listing"]["listing_id"] == l.listing_id
