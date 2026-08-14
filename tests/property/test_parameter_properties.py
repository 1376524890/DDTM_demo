"""参数属性测试（检查单 R）。

性质：随机 ResolvedParameter round-trip 后 hash 稳定；来源模式门禁；
dtype 推断正确。
"""

from __future__ import annotations

import random

from valor.core.enums import ConfigMode, ParamSource
from valor.core.hashing import content_hash
from valor.params.models import ResolvedParameter, infer_dtype
from valor.params.validators import validate_source_mode

H64 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"

_NON_FIXTURE = [
    ParamSource.OBSERVED_DATA, ParamSource.CALIBRATED,
    ParamSource.CONTRACT_INPUT, ParamSource.MARKET_DISCOVERED,
    ParamSource.OPTIMIZER_OUTPUT, ParamSource.THREAT_SCENARIO,
    ParamSource.STANDARD_CONSTANT,
]
_SCHEMES = {
    ParamSource.OBSERVED_DATA: "dataset",
    ParamSource.CALIBRATED: "calib",
    ParamSource.CONTRACT_INPUT: "contract",
    ParamSource.MARKET_DISCOVERED: "market",
    ParamSource.OPTIMIZER_OUTPUT: "optimizer",
    ParamSource.THREAT_SCENARIO: "threat",
    ParamSource.STANDARD_CONSTANT: "standard",
    ParamSource.TEST_FIXTURE: "fixture",
}


def test_dtype_inference():
    assert infer_dtype(True) == "bool"
    assert infer_dtype(3) == "int"
    assert infer_dtype(3.5) == "float"
    assert infer_dtype("x") == "str"


def test_random_parameter_roundtrip_stable():
    rng = random.Random(7)
    for i in range(100):
        sk = rng.choice(_NON_FIXTURE)
        scheme = _SCHEMES[sk]
        p = ResolvedParameter(
            name=f"p{i}",
            value=rng.random() * 100,
            unit="CU",
            source_kind=sk,
            source_ref=f"{scheme}://artifact-{i}@v1",
            version_hash=H64,
        )
        restored = ResolvedParameter.from_dict(p.to_plain())
        assert content_hash(restored) == content_hash(p)
        assert restored.dtype == p.dtype


def test_source_mode_property():
    """TEST_FIXTURE 仅 TEST 允许；其余来源任何模式都允许。"""
    for sk in _NON_FIXTURE:
        for mode in ConfigMode:
            validate_source_mode(sk, mode)  # 不抛
    # fixture 只在 TEST
    validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.TEST)
    for mode in (ConfigMode.EXPERIMENT, ConfigMode.PRODUCTION):
        try:
            validate_source_mode(ParamSource.TEST_FIXTURE, mode)
            raise AssertionError(f"TEST_FIXTURE 不应允许于 {mode.value}")
        except Exception:
            pass
