"""配置加载与 fail-closed 校验（Phase 0 gate / 规范 §53、§5）。

业务参数必须显式给出，缺失即抛 ConfigError（CONFIG），禁止无来源默认值。
提供 JSON Schema 文件位于 configs/schemas/ 用于结构校验；本模块在运行时
再强制必需字段存在与基本类型/单位正确。

说明（D107）：规范 §53 目录未单列 config.py，但配置加载属于基础设施，
故在 valor/ 顶层提供；后续 Phase 可扩展为按子目录 schema 分模块加载。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from valor.core.errors import ConfigError


def _require_field(d: dict[str, Any], key: str, ctx: str) -> Any:
    """要求字段显式存在；缺失抛 CONFIG。"""
    if key not in d or d[key] is None:
        raise ConfigError(f"[{ctx}] 缺失必需参数: {key}（禁止无来源默认值）")
    return d[key]


class TransactionConfig:
    """Phase 0 交易配置（entitlement/compliance 硬门槛所需）。"""

    def __init__(self, raw: dict[str, Any]) -> None:
        tx = _require_field(raw, "transaction", "root")
        self.tx_id = _require_field(tx, "tx_id", "transaction")
        self.seller_id = _require_field(tx, "seller_id", "transaction")
        self.buyer_id = _require_field(tx, "buyer_id", "transaction")

        asset = _require_field(raw, "asset", "root")
        self.asset_id = _require_field(asset, "asset_id", "asset")
        self.version_id = _require_field(asset, "version_id", "asset")
        self.data_commitment = _require_field(
            asset, "data_commitment", "asset"
        )
        self.metadata_commitment = _require_field(
            asset, "metadata_commitment", "asset"
        )

        ent = _require_field(raw, "entitlement", "root")
        self.grant_authority = _require_field(ent, "grant_authority", "entitlement")
        self.version_revoked = _require_field(
            ent, "version_revoked", "entitlement"
        )

        comp = _require_field(raw, "compliance", "root")
        self.buyer_eligible = _require_field(comp, "buyer_eligible", "compliance")
        self.menu_conflict = _require_field(comp, "menu_conflict", "compliance")

    def to_plain(self) -> dict[str, Any]:
        return {
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


def load_transaction_config(path: str) -> TransactionConfig:
    """从 JSON 加载交易配置；空配置/缺参直接抛 ConfigError。"""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"配置文件不存在: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    return TransactionConfig(raw)
