"""货币与单位属性测试（检查单 R/F）。

性质：Money 算术保持 [CU]；不兼容维度被拒绝；概率范围强制。
"""

from __future__ import annotations

import random

import pytest

from valor.core.errors import OutOfCertifiedRangeError, UnitMismatchError
from valor.core.money import Money
from valor.params.models import ResolvedParameter
from valor.params.units import KnownUnits, compatible, dimension
from valor.params.validators import require_probability

H64 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"


def test_money_arithmetic_random():
    rng = random.Random(11)
    acc = Money(0.0, "CU")
    for _ in range(100):
        acc = acc + Money(rng.random() * 100, "CU")
    assert acc.unit == "CU"


def test_dimensions_distinguish():
    # 不同维度不兼容
    assert not compatible(KnownUnits.CU, KnownUnits.PROBABILITY)
    assert not compatible(KnownUnits.CU, KnownUnits.COUNT)
    assert not compatible(KnownUnits.RATE, KnownUnits.TIME)
    # 同维度兼容
    assert compatible(KnownUnits.PROBABILITY, KnownUnits.RATIO)
    assert compatible(KnownUnits.TIME, KnownUnits.DURATION)


def test_money_not_mixed_with_probability():
    m = Money(5.0, "CU")
    with pytest.raises(UnitMismatchError):
        m + Money(1.0, "probability")


def test_probability_range_property():
    from valor.core.enums import ParamSource as PS

    def mk(v):
        return ResolvedParameter(
            name="p", value=v, unit=KnownUnits.PROBABILITY,
            source_kind=PS.CONTRACT_INPUT,
            source_ref="contract://x", version_hash=H64,
        )
    require_probability(mk(0.0))
    require_probability(mk(1.0))
    require_probability(mk(0.5))
    with pytest.raises(OutOfCertifiedRangeError):
        require_probability(mk(1.0001))
    with pytest.raises(OutOfCertifiedRangeError):
        require_probability(mk(-0.0001))
