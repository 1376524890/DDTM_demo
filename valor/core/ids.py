"""ID 生成与校验。

对齐规范：
- §3.1 DataAsset=(assetID,versionID,...)
- §4 交易承诺 τ=(txID, sellerID, buyerID, assetID, versionID, ...)
- §33 事件 e_t=(eventID, txID, ...)
"""

from __future__ import annotations

import re
import secrets

from .errors import VALORError

# 允许的 ID 字符集（小写字母 + 数字 + 连接符），保证可用于 URL/文件名/哈希
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,127}$")


class InvalidIDError(VALORError):
    """ID 格式非法。"""

    code = "INVALID_ID"


def new_id(prefix: str, *, entropy: int = 16) -> str:
    """生成带前缀的随机 ID。prefix 用于标识对象类型（如 'tx','asset','evt'）。"""
    if not re.match(r"^[a-z0-9]{2,16}$", prefix):
        raise InvalidIDError(f"非法前缀: {prefix!r}（须 2-16 位小写字母/数字）")
    return f"{prefix}-{secrets.token_hex(entropy)}"


def validate_id(value: str, *, name: str = "ID") -> None:
    """校验 ID 格式；非法则抛 InvalidIDError。"""
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise InvalidIDError(f"[{name}] 非法 ID: {value!r}")
