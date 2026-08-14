"""序列化 round-trip 测试（检查单 L）。

x → JSON(to_plain) → x'（from_plain），要求 x == x' 且 H(x) == H(x')。
对象：ResolvedParameter、Money、Interval、DataAsset、RightsBundle、IDs、enums、manifest。
"""

from __future__ import annotations

import pytest

from valor.core.enums import DeliveryMode, ParamSource
from valor.core.hashing import content_hash
from valor.core.ids import AssetID, TransactionID
from valor.core.money import Money
from valor.asset import AssetVersion, DataAsset
from valor.params.models import Interval, ResolvedParameter
from valor.rights import RightsBundle

H64 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"


def assert_roundtrip(obj, from_plain):
    plain = obj.to_plain()
    restored = from_plain(plain)
    assert restored == obj, f"round-trip 对象不等: {obj} vs {restored}"
    assert content_hash(restored) == content_hash(obj), "round-trip 后 hash 变化"
    return restored


def test_money_roundtrip():
    assert_roundtrip(Money(12.5, "CU"), Money.from_plain)


def test_interval_roundtrip():
    iv = Interval(0.1, 0.9, "probability", confidence=0.95)
    assert_roundtrip(iv, Interval.from_plain)


def test_resolved_parameter_roundtrip():
    p = ResolvedParameter(
        name="alpha", value=0.05, unit="probability",
        source_kind=ParamSource.CONTRACT_INPUT, source_ref="contract://abc",
        version_hash=H64,
    )
    restored = ResolvedParameter.from_dict(p.to_plain())
    assert restored == p
    assert content_hash(restored) == content_hash(p)


def test_rights_bundle_roundtrip():
    rb = RightsBundle(
        r_class="lic", access_mode=DeliveryMode.API_GATEWAY,
        t0="2025-01-01", t1="2025-12-31", q=10,
        purposes=frozenset({"ml_training"}),
        scope="CN", exclusivity=False, redistribution=False, derivative=False,
    )
    assert_roundtrip(rb, RightsBundle.from_plain)


def test_data_asset_roundtrip():
    v = AssetVersion(
        asset_id="a1", version_id="v1",
        data_commitment="a" * 64, metadata_commitment="b" * 64,
        provenance_ref="dataset://a1b2c3",
    )
    da = DataAsset(asset_id="a1", versions=(v,))
    restored = DataAsset.from_plain(da.to_plain())
    assert restored == da
    assert content_hash(restored) == content_hash(da)


def test_id_roundtrip():
    aid = AssetID("asset-abc")
    assert AssetID.of(aid.to_plain()) == aid
    assert content_hash({"id": aid.to_plain()}) == content_hash({"id": str(aid)})


def test_enum_roundtrip():
    # Enum 序列化为 .value，可重建
    assert DeliveryMode(DeliveryMode.API_GATEWAY.value) == DeliveryMode.API_GATEWAY
    assert ParamSource(ParamSource.CALIBRATED.value) == ParamSource.CALIBRATED


def test_version_change_changes_hash():
    """版本变化导致承诺/对象 hash 变化（检查单 J）。"""
    v1 = AssetVersion("a1", "v1", data_commitment="a" * 64, metadata_commitment="b" * 64)
    v2 = AssetVersion("a1", "v2", data_commitment="a" * 64, metadata_commitment="b" * 64)
    assert content_hash(v1) != content_hash(v2)


def test_committed_field_change_changes_hash():
    """任意 committed 字段变化改变 hash（检查单 D tamper）。"""
    p1 = ResolvedParameter(
        name="alpha", value=0.05, unit="probability",
        source_kind=ParamSource.CONTRACT_INPUT, source_ref="contract://abc",
        version_hash=H64,
    )
    p2 = ResolvedParameter(
        name="alpha", value=0.06, unit="probability",
        source_kind=ParamSource.CONTRACT_INPUT, source_ref="contract://abc",
        version_hash=H64,
    )
    assert content_hash(p1) != content_hash(p2)
