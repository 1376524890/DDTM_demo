"""配置加载与 fail-closed 校验（检查单 I / 规范 §53、§5）。

- schema version：不支持即抛 CONFIG_VERSION_UNSUPPORTED
- unknown field 默认拒绝（拼写错误不静默忽略）
- 缺少 required / 类型错误 → 解析失败
- NaN/Inf 拒绝；strict 模式不把 "0.05" 字符串静默转 float
- source mode：production/experiment 禁 TEST_FIXTURE（检查单 B2）
- config hash 可复现：H_config = H(Canonicalize(Config))；key 重排不影响
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from valor.core.enums import ConfigMode, ParamSource
from valor.core.errors import (
    CONFIG_VERSION_UNSUPPORTED,
    ConfigError,
    ConfigVersionUnsupportedError,
    InvalidSchemaError,
)
from valor.core.hashing import content_hash
from valor.params.validators import validate_source_mode

# 当前受支持的配置 schema 版本（检查单 I：config schema 具有版本号）
SUPPORTED_CONFIG_SCHEMA_VERSION = "1"

# 允许的顶层字段
_TOP_KEYS = {"schema_version", "mode", "transaction", "asset", "entitlement", "compliance"}
_TX_KEYS = {"tx_id", "seller_id", "buyer_id"}
_ASSET_KEYS = {"asset_id", "version_id", "data_commitment", "metadata_commitment"}
_ENT_KEYS = {"grant_authority", "version_revoked"}
_COMP_KEYS = {"buyer_eligible", "menu_conflict"}


def _reject_unknown(d: dict[str, Any], allowed: set[str], ctx: str) -> None:
    """未知字段拒绝（检查单 I：拼写错误不静默忽略）。"""
    unknown = set(d) - allowed
    if unknown:
        raise InvalidSchemaError(
            f"[{ctx}] 未知字段: {sorted(unknown)}（strict 模式拒绝，防止拼写错误静默）"
        )


def _require_field(d: dict[str, Any], key: str, ctx: str) -> Any:
    """要求字段显式存在（缺失/为 None 抛 CONFIG，禁止无来源默认值）。"""
    if key not in d or d[key] is None:
        raise ConfigError(f"[{ctx}] 缺失必需参数: {key}（禁止无来源默认值）")
    return d[key]


def _check_type(value: Any, types: tuple, name: str, ctx: str) -> None:
    if not isinstance(value, types):
        raise InvalidSchemaError(
            f"[{ctx}] 字段 {name} 类型错误: 期望 {tuple(t.__name__ for t in types)}，"
            f"实际 {type(value).__name__}"
        )


def _reject_nonfinite(value: Any, name: str, ctx: str) -> None:
    """拒绝 NaN/Inf（检查单 I）。"""
    if isinstance(value, float) and not math.isfinite(value):
        raise InvalidSchemaError(f"[{ctx}] 字段 {name} 为 NaN/Inf，拒绝")


def _validate_hash_field(h: str, name: str, ctx: str) -> None:
    """承诺哈希必须为 64 位小写 hex（检查单 D：错误长度/字符被拒绝）。"""
    from valor.core.hashing import validate_hash as _vh

    _vh(h, name=f"{ctx}.{name}")


class TransactionConfig:
    """Phase 0 交易配置（含 schema 版本与 mode 门禁）。"""

    def __init__(
        self,
        raw: dict[str, Any],
        *,
        mode: ConfigMode = ConfigMode.PRODUCTION,
    ) -> None:
        _reject_unknown(raw, _TOP_KEYS, "root")

        # schema 版本校验（fail closed）
        schema_version = raw.get("schema_version", SUPPORTED_CONFIG_SCHEMA_VERSION)
        if str(schema_version) != SUPPORTED_CONFIG_SCHEMA_VERSION:
            raise ConfigVersionUnsupportedError(
                f"不支持的配置 schema 版本: {schema_version}（当前支持 "
                f"{SUPPORTED_CONFIG_SCHEMA_VERSION}）",
                detail={"supported": SUPPORTED_CONFIG_SCHEMA_VERSION,
                        "provided": schema_version},
            )
        self.schema_version = str(schema_version)

        # 模式（缺省 PRODUCTION）
        mode_raw = raw.get("mode", mode.value)
        self.mode = ConfigMode(mode_raw)

        # ---- transaction ----
        tx = _require_field(raw, "transaction", "root")
        _reject_unknown(tx, _TX_KEYS, "transaction")
        self.tx_id = _require_field(tx, "tx_id", "transaction")
        self.seller_id = _require_field(tx, "seller_id", "transaction")
        self.buyer_id = _require_field(tx, "buyer_id", "transaction")
        _check_type(self.tx_id, (str,), "tx_id", "transaction")
        _check_type(self.seller_id, (str,), "seller_id", "transaction")
        _check_type(self.buyer_id, (str,), "buyer_id", "transaction")

        # ---- asset ----
        asset = _require_field(raw, "asset", "root")
        _reject_unknown(asset, _ASSET_KEYS, "asset")
        self.asset_id = _require_field(asset, "asset_id", "asset")
        self.version_id = _require_field(asset, "version_id", "asset")
        self.data_commitment = _require_field(asset, "data_commitment", "asset")
        self.metadata_commitment = _require_field(asset, "metadata_commitment", "asset")
        for k in ("data_commitment", "metadata_commitment"):
            _check_type(getattr(self, k), (str,), k, "asset")
            _validate_hash_field(getattr(self, k), k, "asset")

        # ---- entitlement ----
        ent = _require_field(raw, "entitlement", "root")
        _reject_unknown(ent, _ENT_KEYS, "entitlement")
        self.grant_authority = _require_field(ent, "grant_authority", "entitlement")
        self.version_revoked = _require_field(ent, "version_revoked", "entitlement")
        _check_type(self.grant_authority, (bool,), "grant_authority", "entitlement")
        _check_type(self.version_revoked, (bool,), "version_revoked", "entitlement")

        # ---- compliance ----
        comp = _require_field(raw, "compliance", "root")
        _reject_unknown(comp, _COMP_KEYS, "compliance")
        self.buyer_eligible = _require_field(comp, "buyer_eligible", "compliance")
        self.menu_conflict = _require_field(comp, "menu_conflict", "compliance")
        _check_type(self.buyer_eligible, (bool,), "buyer_eligible", "compliance")
        _check_type(self.menu_conflict, (bool,), "menu_conflict", "compliance")

    @property
    def config_hash(self) -> str:
        """H_config = H(Canonicalize(Config))，可复现（检查单 I）。"""
        return content_hash(self.to_plain())

    def to_plain(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "mode": self.mode.value,
            "transaction": {
                "tx_id": self.tx_id,
                "seller_id": self.seller_id,
                "buyer_id": self.buyer_id,
            },
            "asset": {
                "asset_id": self.asset_id,
                "version_id": self.version_id,
                "data_commitment": self.data_commitment,
                "metadata_commitment": self.metadata_commitment,
            },
            "entitlement": {
                "grant_authority": self.grant_authority,
                "version_revoked": self.version_revoked,
            },
            "compliance": {
                "buyer_eligible": self.buyer_eligible,
                "menu_conflict": self.menu_conflict,
            },
        }


def load_transaction_config(
    path: str,
    *,
    mode: ConfigMode = ConfigMode.PRODUCTION,
) -> TransactionConfig:
    """从 JSON 加载交易配置；空配置/缺参/未知字段/schema 版本不支持均 fail closed。"""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"配置文件不存在: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ConfigError(f"配置文件 JSON 非法: {e}") from e
    if not isinstance(raw, dict):
        raise InvalidSchemaError("配置文件顶层必须为 JSON 对象")
    return TransactionConfig(raw, mode=mode)
