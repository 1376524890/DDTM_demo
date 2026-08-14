"""Phase 0 验收测试：空业务配置不能运行 transaction；核心 dataclass 可
序列化、canonicalize、hash（规范 §70 Phase 0 验收）。

对齐规范 §5.3 fail-closed、§4 承诺绑定、§54.1 ResolvedParameter 无默认值。
"""

from __future__ import annotations

import json

import pytest

from valor.config import ConfigError, load_transaction_config
from valor.core.errors import (
    UNRESOLVED_PARAMETER,
    UnresolvedParameterError,
)
from valor.core.hashing import content_hash
from valor.params.models import ParameterManifest, ResolvedParameter
from valor.params.resolver import ParameterResolver
from valor.params.units import KnownUnits


def _write(tmp_path, data) -> str:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_empty_config_cannot_run_transaction(tmp_path):
    """空配置（{}）必须无法加载/运行交易。"""
    path = _write(tmp_path, {})
    with pytest.raises(ConfigError):
        load_transaction_config(path)


def test_missing_field_fail_closed(tmp_path):
    """缺少任一必需字段必须抛 ConfigError（禁止无来源默认值）。"""
    path = _write(tmp_path, {"transaction": {"tx_id": "x"}})
    with pytest.raises(ConfigError):
        load_transaction_config(path)


def test_valid_config_loads(tmp_path):
    """合法配置可加载。"""
    path = _write(
        tmp_path,
        {
            "transaction": {"tx_id": "t", "seller_id": "s", "buyer_id": "b"},
            "asset": {
                "asset_id": "a",
                "version_id": "v1",
                "data_commitment": "a" * 64,
                "metadata_commitment": "b" * 64,
            },
            "entitlement": {"grant_authority": True, "version_revoked": False},
            "compliance": {"buyer_eligible": True, "menu_conflict": False},
        },
    )
    conf = load_transaction_config(path)
    assert conf.tx_id == "t"


def test_resolved_parameter_requires_source():
    """ResolvedParameter 必须携带来源与版本哈希；缺失即 fail closed。"""
    with pytest.raises(UnresolvedParameterError):
        ResolvedParameter(
            name="alpha",
            value=0.05,
            unit=KnownUnits.PROBABILITY,
            source_kind=None,  # type: ignore
            source_ref="",
            version_hash="",
        )


def test_require_resolved_missing_raises():
    """require_resolved() 对未解析参数抛 UNRESOLVED_PARAMETER。"""
    resolver = ParameterResolver()
    from valor.core.enums import ParamSource

    resolver.register(
        ResolvedParameter(
            name="rho",
            value=0.1,
            unit=KnownUnits.RATIO,
            source_kind=ParamSource.CALIBRATED,
            source_ref="calib/run-001",
            version_hash="abc123",
        )
    )
    ok = resolver.require("rho")
    assert ok.name == "rho"
    with pytest.raises(UnresolvedParameterError) as e:
        resolver.require("committee_size")
    assert e.value.code == UNRESOLVED_PARAMETER


def test_manifest_hash_reproducible():
    """ParameterManifest 哈希可复现（跨平台确定性）。"""
    from valor.core.enums import ParamSource

    p = ResolvedParameter(
        name="alpha",
        value=0.05,
        unit=KnownUnits.PROBABILITY,
        source_kind=ParamSource.CONTRACT_INPUT,
        source_ref="contract/abc",
        version_hash="v1",
    )
    m1 = ParameterManifest(parameters=(p,))
    m2 = ParameterManifest(parameters=(p,))
    assert m1.manifest_hash == m2.manifest_hash == m1.manifest_hash
    assert len(m1.manifest_hash) == 64


def test_content_hash_deterministic_across_key_order():
    """canonical 序列化保证 key 顺序无关，内容哈希一致（§4/§33）。"""
    a = {"x": 1, "y": 2, "z": [1, 2, 3]}
    b = {"z": [1, 2, 3], "y": 2, "x": 1}
    assert content_hash(a) == content_hash(b)
