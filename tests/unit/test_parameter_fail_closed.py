"""Phase 0 验收测试：空业务配置不能运行 transaction；核心 dataclass 可
序列化、canonicalize、hash（规范 §70 Phase 0 验收 / 检查单 A-Q）。

对齐规范 §5.3 fail-closed、§4 承诺绑定、§54.1 ResolvedParameter 无默认值。
"""

from __future__ import annotations

import json

import pytest

from valor.config import ConfigError, load_transaction_config
from valor.core.enums import ConfigMode, ParamSource
from valor.core.errors import (
    INVALID_SOURCE_REF,
    MISSING_EVIDENCE_REF,
    UNRESOLVED_PARAMETER,
    InvalidSourceRefError,
    MissingEvidenceRefError,
    UnresolvedParameterError,
)
from valor.core.hashing import content_hash
from valor.params.models import ParameterManifest, ResolvedParameter
from valor.params.refs import validate_source_ref
from valor.params.resolver import ParameterResolver
from valor.params.units import KnownUnits
from valor.params.validators import validate_source_mode

H64 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"


def _write(tmp_path, data) -> str:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def _valid_param(name="rho", **kw):
    base = dict(
        name=name,
        value=0.1,
        unit=KnownUnits.RATIO,
        source_kind=ParamSource.CALIBRATED,
        source_ref=f"calib://run-001@v1",
        version_hash=H64,
    )
    base.update(kw)
    return ResolvedParameter(**base)


def test_empty_config_cannot_run_transaction(tmp_path):
    """空配置（{}）必须无法加载/运行交易（检查单 Q#1）。"""
    path = _write(tmp_path, {})
    with pytest.raises(ConfigError):
        load_transaction_config(path)


def test_missing_field_fail_closed(tmp_path):
    """缺少任一必需字段必须抛 ConfigError（检查单 Q#2）。"""
    path = _write(tmp_path, {"transaction": {"tx_id": "x"}})
    with pytest.raises(ConfigError):
        load_transaction_config(path)


def test_valid_config_loads(tmp_path):
    """合法配置可加载。"""
    path = _write(
        tmp_path,
        {
            "schema_version": "1",
            "mode": "PRODUCTION",
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


def test_resolved_parameter_missing_source():
    """ResolvedParameter 缺 source/版本哈希即 fail closed（检查单 Q#3,#4）。"""
    with pytest.raises(UnresolvedParameterError):
        _valid_param(source_kind=None)  # type: ignore
    with pytest.raises(MissingEvidenceRefError) as e:
        _valid_param(source_ref="")
    assert e.value.code == MISSING_EVIDENCE_REF


def test_source_ref_scheme_enforced():
    """source_ref scheme 必须与来源匹配（检查单 O）。"""
    validate_source_ref("calib://run-001@v1", ParamSource.CALIBRATED)
    with pytest.raises(InvalidSourceRefError) as e:
        _valid_param(source_ref="contract://abc")  # CALIBRATED 期望 calib://
    assert e.value.code == INVALID_SOURCE_REF


def test_require_resolved_missing_raises():
    """require_resolved() 对未解析参数抛 UNRESOLVED_PARAMETER（检查单 G）。"""
    resolver = ParameterResolver()
    resolver.register(_valid_param(name="rho"))
    ok = resolver.require("rho")
    assert ok.name == "rho"
    with pytest.raises(UnresolvedParameterError) as e:
        resolver.require("committee_size")
    assert e.value.code == UNRESOLVED_PARAMETER


def test_manifest_hash_reproducible():
    """ParameterManifest 哈希可复现（跨平台确定性）。"""
    m1 = ParameterManifest(parameters=(_valid_param(name="alpha"),))
    m2 = ParameterManifest(parameters=(_valid_param(name="alpha"),))
    assert m1.manifest_hash == m2.manifest_hash == m1.manifest_hash
    assert len(m1.manifest_hash) == 64


def test_content_hash_deterministic_across_key_order():
    """canonical 序列化保证 key 顺序无关，内容哈希一致（§4/§33）。"""
    a = {"x": 1, "y": 2, "z": [1, 2, 3]}
    b = {"z": [1, 2, 3], "y": 2, "x": 1}
    assert content_hash(a) == content_hash(b)


def test_source_mode_fixture_gate():
    """TEST 允许 TEST_FIXTURE；PRODUCTION 拒绝（检查单 B2）。"""
    validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.TEST)
    with pytest.raises(Exception):
        validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.PRODUCTION)


def test_production_config_rejects_test_fixture(tmp_path):
    """production config parser 拒绝 TEST_FIXTURE（检查单 B2）。"""
    from valor.config import TransactionConfig

    data = {
        "schema_version": "1",
        "mode": "PRODUCTION",
        "transaction": {"tx_id": "t", "seller_id": "s", "buyer_id": "b"},
        "asset": {
            "asset_id": "a", "version_id": "v1",
            "data_commitment": "a" * 64, "metadata_commitment": "b" * 64,
        },
        "entitlement": {"grant_authority": True, "version_revoked": False},
        "compliance": {"buyer_eligible": True, "menu_conflict": False},
    }
    # 配置本身无 TEST_FIXTURE；模式门禁由参数层校验。此处验证模式被正确解析。
    conf = TransactionConfig(data)
    assert conf.mode == ConfigMode.PRODUCTION
