"""序列化 round-trip 属性测试（检查单 R/L）。

性质：x=Deserialize(Serialize(x)) 且 H(x)=H(Deserialize(Serialize(x)))
对一组核心对象成立。
"""

from __future__ import annotations

from valor.core.enums import DeliveryMode, ParamSource
from valor.core.hashing import content_hash
from valor.core.ids import AssetID, TransactionID
from valor.core.money import Money
from valor.asset import AssetVersion, DataAsset
from valor.params.models import Interval, ResolvedParameter
from valor.rights import RightsBundle

H64 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"


def _roundtrip(obj, from_plain):
    restored = from_plain(obj.to_plain())
    assert restored == obj
    assert content_hash(restored) == content_hash(obj)


def test_all_core_objects_roundtrip():
    _roundtrip(Money(3.0, "CU"), Money.from_plain)
    _roundtrip(Interval(0.0, 1.0, "probability", 0.9), Interval.from_plain)
    p = ResolvedParameter(
        name="alpha", value=0.05, unit="probability",
        source_kind=ParamSource.CONTRACT_INPUT, source_ref="contract://abc",
        version_hash=H64,
    )
    # ResolvedParameter 用 from_dict
    restored = ResolvedParameter.from_dict(p.to_plain())
    assert restored == p and content_hash(restored) == content_hash(p)
    rb = RightsBundle(
        r_class="lic", access_mode=DeliveryMode.API_GATEWAY,
        t0="2025-01-01", t1="2025-12-31", q=10,
        purposes=frozenset({"ml"}), scope="CN",
        exclusivity=False, redistribution=False, derivative=False,
    )
    _roundtrip(rb, RightsBundle.from_plain)
    v = AssetVersion("a1", "v1", data_commitment="a" * 64, metadata_commitment="b" * 64)
    _roundtrip(DataAsset("a1", (v,)), DataAsset.from_plain)
    _roundtrip(AssetID("asset-x"), AssetID.of)
    _roundtrip(TransactionID("tx-x"), TransactionID.of)


def test_id_equality_by_type():
    # 不同类型 ID 不相等（检查单 E）
    assert AssetID("a") != TransactionID("a")
