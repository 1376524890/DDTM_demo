"""类型化 ID 系统（检查单 E，Phase 0 一次性冻结）。

对齐规范：§3.1 assetID/versionID、§4 txID/sellerID/buyerID、§33 eventID。

规则：
- 每个业务 ID 用独立类型（AssetID / TransactionID / ...），类型不同不可混用，
  避免"拿 AssetID 当 TransactionID 而类型检查仍通过"。
- 随机 ID 用 secrets.token_hex（密码学随机，非 Python hash()）；内容寻址 ID
  用 content_hash。两者语义分离，不混用。
- ID 可序列化（to_plain）且可严格解析（parse）；无效 ID fail closed（INVALID_ID）。
- 禁止空字符串 ID（sellerID="" 拒绝）。
"""

from __future__ import annotations

import re
import secrets
from typing import Type

from .errors import InvalidIDError

# 允许的 ID 字符集（小写字母 + 数字 + 连接符），保证可用于 URL/文件名/哈希
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,127}$")


def validate_id(value: str, *, name: str = "ID") -> None:
    """校验 ID 格式；非法（含空串）抛 INVALID_ID。"""
    if not isinstance(value, str) or not value or not _ID_RE.match(value):
        raise InvalidIDError(f"[{name}] 非法 ID: {value!r}（禁止空串/非法字符）")


class ValorID:
    """类型化 ID 基类（不可变）。

    子类定义 id_type 与默认 prefix。value 在构造时严格校验；实例不可修改。
    """

    __slots__ = ("value",)

    id_type: str = "id"
    prefix: str = "id"

    def __init__(self, value: str) -> None:
        validate_id(value, name=self.id_type)
        # 不可变：__slots__ 且不再提供 setter
        self.value = value

    # ---- 生成 ----
    @classmethod
    def new(cls, entropy: int = 16) -> "ValorID":
        """生成随机 ID（secrets.token_hex，非 Python hash()）。"""
        return cls(f"{cls.prefix}-{secrets.token_hex(entropy)}")

    @classmethod
    def of(cls, value: str) -> "ValorID":
        """严格解析：格式非法抛 INVALID_ID。"""
        return cls(value)

    # ---- 表示 ----
    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.id_type}({self.value!r})"

    def __eq__(self, other: object) -> bool:
        # 类型必须一致（同类比较）；不同 ID 类型即使 value 相同也不相等
        return isinstance(other, self.__class__) and self.value == other.value

    def __hash__(self) -> int:
        return hash((self.id_type, self.value))

    def to_plain(self) -> str:
        """可序列化表示（字符串）。"""
        return self.value

    # ---- 兼容旧 validate_id 的便捷方法 ----
    @property
    def raw(self) -> str:
        return self.value


# 业务 ID 类型（检查单 E 至少要求下列类型）
class AssetID(ValorID):
    id_type = "AssetID"
    prefix = "asset"


class VersionID(ValorID):
    id_type = "VersionID"
    prefix = "version"


class TransactionID(ValorID):
    id_type = "TransactionID"
    prefix = "tx"


class SellerID(ValorID):
    id_type = "SellerID"
    prefix = "seller"


class BuyerID(ValorID):
    id_type = "BuyerID"
    prefix = "buyer"


class AuditorID(ValorID):
    id_type = "AuditorID"
    prefix = "auditor"


class PolicyID(ValorID):
    id_type = "PolicyID"
    prefix = "policy"


class CalibrationID(ValorID):
    id_type = "CalibrationID"
    prefix = "calib"


class RightsID(ValorID):
    id_type = "RightsID"
    prefix = "rights"


class EventID(ValorID):
    id_type = "EventID"
    prefix = "evt"


def new_id(prefix: str, *, entropy: int = 16) -> str:
    """通用随机 ID（返回字符串）；业务对象应优先使用类型化 ID。"""
    if not re.match(r"^[a-z0-9]{2,16}$", prefix):
        raise InvalidIDError(f"非法前缀: {prefix!r}（须 2-16 位小写字母/数字）")
    return f"{prefix}-{secrets.token_hex(entropy)}"
