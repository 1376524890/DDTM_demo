"""接收方特定指纹（规范 §36.1 DOWNLOAD_TRACEABLE）。

系统不声称技术上阻止离线复制，只通过接收方特定指纹、事件日志、合同责任与
事后证据提高可追责性（§36.1 / §73 禁止虚假声称阻止所有离线复制）。
"""

from __future__ import annotations

import hashlib

from valor.core.hashing import sha256_hex


def recipient_fingerprint(buyer_id: str, salt: str) -> str:
    """为接收方生成确定性指纹（买家 ID + 盐）。"""
    return sha256_hex(f"{buyer_id}:{salt}".encode("utf-8"))


def embed_fingerprint(data_bytes: bytes, fingerprint: str, *, column: str = "__fp__") -> bytes:
    """把指纹嵌入数据（示例：追加标记列）。"""
    return data_bytes + f"\n{fingerprint}".encode("utf-8")


def trace_origin(leaked: bytes, candidates: dict[str, str]) -> str | None:
    """从泄露数据中匹配接收方指纹，定位来源买家。"""
    text = leaked.decode(errors="ignore")
    for buyer_id, fp in candidates.items():
        if fp in text:
            return buyer_id
    return None
