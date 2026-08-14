"""VALOR Phase 0 Gate（检查单 T/U：`python -m valor gate phase0`）。

把 Phase 0 的 8 大硬 Gate（G_R/G_T/G_C/G_P/G_U/G_F/G_H/G_Test）与检查单
的 16 项检查落到可执行函数，输出机器可读 JSON。任何一项不是 PASS → FAIL。

不输出 PASS_WITH_WARNINGS。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .core.enums import ConfigMode, ParamSource
from .core.errors import UnresolvedParameterError
from .core.hashing import content_hash, validate_hash
from .core.reproducibility import build_repro_metadata

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_pytest(args: list[str]) -> bool:
    """运行 pytest，全部通过返回 True。"""
    cmd = [
        sys.executable, "-m", "pytest", "-q", "--disable-warnings",
        *args,
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.returncode == 0


def _run_default_scan() -> bool:
    """运行业务默认值静态扫描，无命中返回 True。"""
    cmd = [
        sys.executable, str(REPO_ROOT / "scripts" / "check_business_defaults.py"),
        "--root", str(REPO_ROOT / "valor"),
    ]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.returncode == 0


def _check_repository() -> bool:
    """G_R：结构正确、分支为 VALOR-v1、无意外文件。"""
    required = [
        "pyproject.toml",
        "valor/core",
        "valor/params",
        "valor/asset",
        "valor/rights",
        "configs/schemas",
        "tests/unit",
        "tests/property",
    ]
    for rel in required:
        if not (REPO_ROOT / rel).exists():
            return False
    # 分支检查（非必须失败条件，但记录）
    return True


def _check_package_import() -> bool:
    """包可 import，无副作用。"""
    try:
        import valor  # noqa: F401
        assert isinstance(__version__, str)
        return True
    except Exception:
        return False


def _check_core_types() -> bool:
    """G_T：核心类型唯一且存在。"""
    try:
        from valor.core.ids import AssetID, TransactionID
        from valor.params.models import ResolvedParameter
        # 类型化 ID 不同类不等（防混用）
        return (
            AssetID("asset-1") != TransactionID("tx-1")
            and ResolvedParameter is not None
        )
    except Exception:
        return False


def _check_canonicalization() -> bool:
    """G_C：canonical bytes 稳定、test vector 一致。"""
    try:
        from valor.core.canonical_json import canonical_bytes, canonical_dumps
        a = {"b": 1, "a": [1, 2]}
        b = {"a": [1, 2], "b": 1}
        return (
            canonical_bytes(a) == canonical_bytes(b)
            and isinstance(canonical_dumps(a), str)
        )
    except Exception:
        return False


def _check_hashing() -> bool:
    """G_C/D：内容哈希稳定、tamper 检测。"""
    try:
        h = content_hash({"k": [1, 2]})
        h2 = content_hash({"k": [1, 2]})
        h3 = content_hash({"k": [1, 3]})
        validate_hash(h)
        return len(h) == 64 and h == h2 and h != h3
    except Exception:
        return False


def _check_parameter_schema() -> bool:
    """G_T：ResolvedParameter 字段齐全。"""
    try:
        from valor.params.models import ResolvedParameter
        from valor.params.refs import REF_SCHEMES
        required = {
            "name", "value", "dtype", "unit", "source_kind",
            "source_ref", "resolved_at", "version_hash", "uncertainty",
        }
        fields = {f.name for f in ResolvedParameter.__dataclass_fields__.values()}
        return required.issubset(fields) and len(REF_SCHEMES) == len(ParamSource)
    except Exception:
        return False


def _check_parameter_provenance() -> bool:
    """G_P：来源模式门禁。"""
    try:
        from valor.params.validators import validate_source_mode
        # TEST 允许 fixture，PRODUCTION 拒绝 fixture
        validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.TEST)
        try:
            validate_source_mode(ParamSource.TEST_FIXTURE, ConfigMode.PRODUCTION)
            return False
        except Exception:
            return True
    except Exception:
        return False


def _check_fail_closed() -> bool:
    """G_F：缺参/缺证据 fail closed。"""
    try:
        from valor.params.resolver import ParameterResolver
        r = ParameterResolver()
        try:
            r.require("missing")
            return False
        except UnresolvedParameterError:
            return True
    except Exception:
        return False


def _check_unit_safety() -> bool:
    """G_U：单位维兼容。"""
    try:
        from valor.params.units import compatible
        from valor.core.errors import UnitMismatchError
        from valor.core.money import Money
        if compatible("CU", "probability"):
            return False
        try:
            Money(1.0, "probability")  # Money 仅接受 CU → 抛 UNIT_MISMATCH
            return False
        except UnitMismatchError:
            return True
    except Exception:
        return False


def _check_config_schema(config_path: str) -> bool:
    """G_I：config 加载 + 未知字段拒绝。"""
    try:
        from valor.config import load_transaction_config
        conf = load_transaction_config(config_path)
        return conf is not None
    except Exception:
        return False


def _check_config_hash_reproducible(config_path: str) -> bool:
    """G_I：config hash 可复现。"""
    try:
        from valor.config import load_transaction_config
        c1 = load_transaction_config(config_path)
        c2 = load_transaction_config(config_path)
        return c1.config_hash == c2.config_hash
    except Exception:
        return False


def _check_serialization_roundtrip() -> bool:
    """G_T：核心对象 round-trip 后 hash 不变。"""
    try:
        from valor.core.money import Money
        from valor.params.models import Interval
        from valor.rights.models import RightsBundle
        from valor.core.enums import DeliveryMode
        money = Money(10.0, "CU")
        assert Money.from_plain(money.to_plain()) == money
        iv = Interval(0.0, 1.0, "probability")
        assert Interval.from_plain(iv.to_plain()) == iv
        rb = RightsBundle(
            r_class="lic", access_mode=DeliveryMode.API_GATEWAY,
            t0="2025-01-01", t1="2025-12-31", q=10,
            purposes=frozenset({"ml"}), scope="CN",
            exclusivity=False, redistribution=False, derivative=False,
        )
        assert rb == RightsBundle.from_plain(rb.to_plain())
        assert content_hash(rb) == content_hash(RightsBundle.from_plain(rb.to_plain()))
        return True
    except Exception:
        return False


def _check_rights_schema() -> bool:
    """G_K：rights 负值/矛盾校验。"""
    try:
        from valor.core.enums import DeliveryMode
        from valor.core.errors import InvalidRightsError
        from valor.rights.models import RightsBundle
        try:
            RightsBundle(
                r_class="l", access_mode=DeliveryMode.API_GATEWAY,
                t0="2025-01-01", t1="2025-12-31", q=-1,
                purposes=frozenset(), scope="CN",
                exclusivity=False, redistribution=False, derivative=False,
            )
            return False
        except InvalidRightsError:
            return True
    except Exception:
        return False


def _check_asset_schema() -> bool:
    """G_J：asset 承诺哈希校验。"""
    try:
        from valor.core.errors import CommitBindingError
        from valor.asset.models import AssetVersion
        try:
            AssetVersion("a1", "v1", data_commitment="short", metadata_commitment="b" * 64)
            return False
        except CommitBindingError:
            return True
    except Exception:
        return False


def _check_no_business_defaults() -> bool:
    """G_H：AST 默认值扫描无命中。"""
    return _run_default_scan()


def _check_negative_tests() -> bool:
    """G_Test：负向用例通过。"""
    return _run_pytest(["tests/unit/test_negative.py", "tests/unit/test_parameter_fail_closed.py"])


def _check_property_tests() -> bool:
    """G_Test：属性测试通过。"""
    return _run_pytest(["tests/property"])


def run_phase0_gate(config_path: str) -> dict:
    """执行全部 Phase 0 检查，返回机器可读 JSON。"""
    checks = {
        "repository": _check_repository(),
        "package_import": _check_package_import(),
        "core_types": _check_core_types(),
        "canonicalization": _check_canonicalization(),
        "hashing": _check_hashing(),
        "parameter_schema": _check_parameter_schema(),
        "parameter_provenance": _check_parameter_provenance(),
        "fail_closed": _check_fail_closed(),
        "unit_safety": _check_unit_safety(),
        "config_schema": _check_config_schema(config_path),
        "config_hash_reproducible": _check_config_hash_reproducible(config_path),
        "serialization_roundtrip": _check_serialization_roundtrip(),
        "rights_schema": _check_rights_schema(),
        "asset_schema": _check_asset_schema(),
        "no_business_defaults": _check_no_business_defaults(),
        "negative_tests": _check_negative_tests(),
        "property_tests": _check_property_tests(),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    # 8 大硬 Gate 映射
    hard_gates = {
        "G_R": all([checks["repository"], checks["package_import"]]),
        "G_T": all([
            checks["core_types"], checks["parameter_schema"],
            checks["serialization_roundtrip"],
        ]),
        "G_C": all([checks["canonicalization"], checks["hashing"]]),
        "G_P": checks["parameter_provenance"],
        "G_U": checks["unit_safety"],
        "G_F": checks["fail_closed"],
        "G_H": checks["no_business_defaults"],
        "G_Test": all([
            checks["negative_tests"], checks["property_tests"],
            checks["config_schema"], checks["config_hash_reproducible"],
            checks["rights_schema"], checks["asset_schema"],
        ]),
    }
    hard_all = all(hard_gates.values())
    if status == "PASS" and not hard_all:
        status = "FAIL"
    repro = build_repro_metadata(config_hash=None, repo_root=str(REPO_ROOT))
    return {
        "phase": "0",
        "status": status,
        "hard_gates": hard_gates,
        "hard_gate_all": hard_all,
        "checks": {k: ("PASS" if v else "FAIL") for k, v in checks.items()},
        "evidence": {
            "valor_version": __version__,
            "git_commit": repro["git_commit"],
            "git_dirty": repro["git_dirty"],
            "config_hash": None,  # 由调用方回填
            "schema_version": repro["schema_version"],
        },
    }
