"""Phase 0 必测负向用例（检查单 Q，共 24 项）。

每个测试的目标是"必须失败"——Phase 0 的核心能力就是拒绝不合法状态。
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from valor.config import ConfigError, load_transaction_config, TransactionConfig
from valor.core.canonical_json import canonical_bytes, canonicalize
from valor.core.enums import ConfigMode, DeliveryMode, ParamSource
from valor.core.errors import (
    CanonicalizationError,
    ConfigVersionUnsupportedError,
    InvalidHashError,
    InvalidIDError,
    InvalidRightsError,
    InvalidSchemaError,
    InvalidSourceKindError,
    MissingEvidenceRefError,
    OutOfCertifiedRangeError,
    ParameterConflictError,
    UnitMismatchError,
    UnresolvedParameterError,
)
from valor.core.hashing import validate_hash
from valor.core.ids import AssetID, TransactionID
from valor.core.money import Money
from valor.params.models import ResolvedParameter
from valor.params.resolver import ParameterResolver
from valor.params.units import KnownUnits, validate_unit
from valor.params.validators import (
    require_positive,
    require_probability,
    validate_source_mode,
)
from valor.rights.models import RightsBundle

H64 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3"
REPO = Path(__file__).resolve().parent.parent.parent


def _write(tmp_path, data) -> str:
    p = tmp_path / "c.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def _valid_cfg():
    return {
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


def _param(**kw):
    base = dict(
        name="rho", value=0.1, unit=KnownUnits.RATIO,
        source_kind=ParamSource.CALIBRATED, source_ref="calib://run@v1",
        version_hash=H64,
    )
    base.update(kw)
    return ResolvedParameter(**base)


# ---- Q 1-5：配置/参数 fail closed ----
def test_q1_empty_business_config(tmp_path):
    with pytest.raises(ConfigError):
        load_transaction_config(_write(tmp_path, {}))


def test_q2_missing_required_parameter(tmp_path):
    with pytest.raises(ConfigError):
        load_transaction_config(_write(tmp_path, {"transaction": {"tx_id": "x"}}))


def test_q3_value_none(tmp_path):
    cfg = _valid_cfg()
    cfg["entitlement"]["grant_authority"] = None
    with pytest.raises(ConfigError):
        load_transaction_config(_write(tmp_path, cfg))


def test_q4_missing_source_ref():
    with pytest.raises(MissingEvidenceRefError):
        _param(source_ref="")


def test_q5_unknown_source_kind():
    with pytest.raises(UnresolvedParameterError):
        _param(source_kind="HACKED")  # type: ignore


# ---- Q 6：TEST_FIXTURE 在 production ----
def test_q6_test_fixture_in_production():
    validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.TEST)
    with pytest.raises(InvalidSourceKindError):
        validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.PRODUCTION)


# ---- Q 7-9：money/probability 量纲 ----
def test_q7_money_plus_probability():
    with pytest.raises(UnitMismatchError):
        Money(1.0, "probability")


def test_q8_probability_greater_than_1():
    with pytest.raises(OutOfCertifiedRangeError):
        require_probability(_param(value=1.5, unit=KnownUnits.PROBABILITY))


def test_q9_probability_negative():
    with pytest.raises(OutOfCertifiedRangeError):
        require_probability(_param(value=-0.1, unit=KnownUnits.PROBABILITY))


# ---- Q 10-11：单位 / NaN ----
def test_q10_invalid_unit():
    with pytest.raises(UnitMismatchError):
        validate_unit("furlongs")


def test_q11_nan_inf_canonical():
    with pytest.raises(CanonicalizationError):
        canonicalize(float("nan"))
    with pytest.raises(CanonicalizationError):
        canonicalize(float("inf"))


# ---- Q 12-13：无效 hash / ID ----
def test_q12_invalid_hash():
    with pytest.raises(InvalidHashError):
        validate_hash("not-a-hash!")


def test_q13_invalid_id():
    with pytest.raises(InvalidIDError):
        AssetID("")  # 禁止空 ID
    with pytest.raises(InvalidIDError):
        TransactionID("BAD ID!")


# ---- Q 14-16：RightsBundle ----
def test_q14_rights_missing_field():
    with pytest.raises(TypeError):
        RightsBundle()  # 字段均 required


def test_q15_rights_none_without_reason():
    with pytest.raises(InvalidRightsError):
        RightsBundle(
            r_class="l", access_mode=DeliveryMode.API_GATEWAY,
            t0="2025-01-01", t1="2025-12-31", q=10,
            purposes=frozenset(), scope="CN",
            exclusivity=False, redistribution=False, derivative=False,
            privacy_budget=1.0, not_applicable_reason="n/a",  # 矛盾
        )


def test_q16_rights_t1_lt_t0():
    with pytest.raises(InvalidRightsError):
        RightsBundle(
            r_class="l", access_mode=DeliveryMode.API_GATEWAY,
            t0="2025-12-31", t1="2025-01-01", q=10,
            purposes=frozenset(), scope="CN",
            exclusivity=False, redistribution=False, derivative=False,
        )


# ---- Q 17-18：config schema ----
def test_q17_unknown_field(tmp_path):
    cfg = _valid_cfg()
    cfg["challange_rate"] = 0.1  # 拼写错误
    with pytest.raises(InvalidSchemaError):
        load_transaction_config(_write(tmp_path, cfg))


def test_q18_schema_version_unsupported(tmp_path):
    cfg = _valid_cfg()
    cfg["schema_version"] = "99"
    with pytest.raises(ConfigVersionUnsupportedError):
        load_transaction_config(_write(tmp_path, cfg))


# ---- Q 19：canonicalization 遇到 unsupported type ----
def test_q19_canonical_unsupported_type():
    class Foo:
        pass

    with pytest.raises(CanonicalizationError):
        canonicalize(Foo())


# ---- Q 20-21：同名参数冲突 ----
def test_q20_same_name_source_conflict():
    r = ParameterResolver()
    r.register(_param(name="rho", source_kind=ParamSource.CALIBRATED,
                      source_ref="calib://a@v1"))
    with pytest.raises(ParameterConflictError):
        r.register(_param(name="rho", source_kind=ParamSource.CONTRACT_INPUT,
                          source_ref="contract://a"))


def test_q21_same_name_unit_conflict():
    r = ParameterResolver()
    r.register(_param(name="rho"))
    with pytest.raises(ParameterConflictError):
        r.register(_param(name="rho", unit=KnownUnits.COUNT, value=5))


# ---- Q 22：fallback 被拒绝（resolver 不返回 None/0）----
def test_q22_no_fallback():
    r = ParameterResolver()
    with pytest.raises(UnresolvedParameterError):
        r.require("alpha")  # 绝不返回 None/0


# ---- Q 23：CLI 未提供 --config 必须失败 ----
def test_q23_cli_missing_config():
    proc = subprocess.run(
        [sys.executable, "-m", "valor", "transaction", "run"],
        cwd=str(REPO), capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "config" in (proc.stderr + proc.stdout).lower()


# ---- Q 24：production 不加载 TEST_FIXTURE 参数 ----
def test_q24_production_rejects_fixture_param():
    # 参数层：TEST_FIXTURE 来源在 PRODUCTION 模式被拒绝
    with pytest.raises(InvalidSourceKindError):
        validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.PRODUCTION)


# ---- 额外：config hash 可复现 / key 重排不影响 ----
def test_config_hash_reproducible():
    c1 = TransactionConfig(_valid_cfg())
    c2 = TransactionConfig(_valid_cfg())
    assert c1.config_hash == c2.config_hash


def test_config_hash_key_reorder_invariant():
    a = TransactionConfig(_valid_cfg()).config_hash
    cfg = _valid_cfg()
    # 重排顶层 key
    reordered = dict(reversed(list(cfg.items())))
    b = TransactionConfig(reordered).config_hash
    assert a == b
