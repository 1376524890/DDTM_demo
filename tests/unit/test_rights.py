"""valor/rights 单元测试：权利束 / 兼容 / 支配 / 机会成本（规范 §3.2、§32、§29）。"""

from __future__ import annotations

import pytest

from valor.core.enums import DeliveryMode
from valor.core.errors import EntitlementError
from valor.rights import (
    Compatible,
    DominanceChecker,
    ODRLProfile,
    RightsBundle,
    check_compatible,
    compute_opportunity_cost,
)


def _bundle(**over):
    base = dict(
        r_class="license",
        access_mode=DeliveryMode.API_GATEWAY,
        t0="2025-01-01",
        t1="2025-12-31",
        q=100,
        purposes=frozenset({"ml_training"}),
        scope="CN",
        exclusivity=False,
        redistribution=False,
        derivative=False,
    )
    base.update(over)
    return RightsBundle(**base)


def test_bundle_hash_and_plain():
    rb = _bundle()
    assert len(rb.rights_hash) == 64
    assert rb.rights_hash == RightsBundle(**rb.to_plain()).rights_hash


def test_bundle_requires_fields_no_default():
    with pytest.raises(TypeError):
        RightsBundle()  # 字段均 required（§54.4）


def test_bundle_not_applicable_consistency():
    # 使用可选字段时不应同时声明 not_applicable_reason
    with pytest.raises(ValueError):
        _bundle(privacy_budget=1.0, not_applicable_reason="n/a")


def test_odrl_profile_maps_exclusivity():
    rb = _bundle(exclusivity=True)
    prof = ODRLProfile.from_bundle(rb)
    assert prof.prohibition_action == "reproduce"
    rb2 = _bundle(exclusivity=False)
    assert ODRLProfile.from_bundle(rb2).prohibition_action is None


def test_compatibility_conflict_on_exclusive():
    existing = [_bundle(exclusivity=True, scope="CN")]
    new = _bundle(exclusivity=True)
    res = check_compatible(new, existing)
    assert res.conflict is True
    with pytest.raises(EntitlementError):
        res.enforce()


def test_compatibility_non_conflict():
    existing = [_bundle(exclusivity=True, scope="CN")]
    new = _bundle(exclusivity=False, scope="EU")
    assert check_compatible(new, existing).passes


def test_dominance():
    dc = DominanceChecker()
    a = _bundle(exclusivity=True, q=200, purposes=frozenset({"ml_training", "eval"}))
    b = _bundle(exclusivity=False, q=100, purposes=frozenset({"ml_training"}))
    assert dc.dominates(a, b)
    assert not dc.dominates(b, a)


def test_opportunity_cost_non_exclusive_small():
    oc = compute_opportunity_cost(
        exclusivity=False, rev_future_without=100.0, rev_future_with=95.0
    )
    assert oc.oc_amount == 5.0
    assert oc.unit == "CU"
