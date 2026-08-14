"""确定性 canonical JSON 序列化（Phase 0 一次性冻结，检查单 C 节）。

对齐规范：
- §4 对象绑定 / 承诺哈希（H(D), H(M_D), H(R_τ)）需跨平台一致
- §33 lineage hash chain：h_t = H(h_{t-1} ∥ Canonical(e_t))
- §54.5 UsageReceipt 可 canonicalize、hash、签名
- §5 参数哈希可复现

一次性解决的规则（检查单 C）：
- canonicalize(obj) -> bytes 唯一实现；所有模块复用，禁止各自 json.dumps 后哈希
- dict key 排序稳定（按 str(key)）；UTF-8 编码；Unicode 一律 NFC 归一化
- datetime/date 统一 UTC ISO-8601（'Z' 后缀）；Enum 取 .value
- tuple/list → list；set/frozenset → 确定性排序后的 list
- None → null；bytes → lowercase hex；Decimal → 规范化十进制字符串
- float 禁止 NaN/Infinity（抛 CANONICALIZATION_ERROR）；浮点表示不依赖 locale
- 不纳入 object address / repr / set 迭代顺序
- canonicalization schema 带 version；固定 test vector 见 tests/fixtures

任何规则变更必须递增 CANONICAL_SCHEMA_VERSION，否则会破坏既有承诺哈希。
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import decimal
import enum
import json
import math
import re
from typing import Any

from .errors import CanonicalizationError
from .ids import ValorID

# canonicalization 规则版本（检查单 C：schema 有 version）
CANONICAL_SCHEMA_VERSION = "1"

# Decimal 规范化：去掉指数形式，保留十进制字符串；拒绝 NaN/Infinity
_DECIMAL_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _canonical_str(value: str) -> str:
    """Unicode 一律 NFC 归一化，保证跨平台/跨进程一致。"""
    return _unicodedata_normalize_nfc(value)


def _unicodedata_normalize_nfc(value: str) -> str:
    # 延迟 import，避免模块加载开销
    import unicodedata

    return unicodedata.normalize("NFC", value)


def _canonical_number(value: float) -> float:
    """浮点规范化：拒绝 NaN/Infinity；返回 float（-0.0 与 0.0 归一为 0.0）。"""
    if math.isnan(value) or math.isinf(value):
        raise CanonicalizationError(
            "canonical 序列化禁止 NaN / Infinity"
        )
    if value == 0.0:
        return 0.0
    return float(value)


def _canonical_datetime(value: Any) -> str:
    """datetime/date 统一 UTC ISO-8601（'Z' 后缀），保证时区无关的确定性。"""
    if isinstance(value, _dt.datetime):
        if value.tzinfo is None:
            # naive datetime 按 UTC 解释（统一约定，检查单 C：datetime 规则明确）
            value = value.replace(tzinfo=_dt.timezone.utc)
        else:
            value = value.astimezone(_dt.timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, _dt.date):
        # date 无时区概念，直接 ISO 日期
        return value.isoformat()
    return _canonical_str(str(value))


def _canonical_decimal(value: decimal.Decimal) -> str:
    """Decimal 规范化十进制字符串；拒绝 NaN/Infinity。"""
    if not value.is_finite():
        raise CanonicalizationError(
            "canonical 序列化禁止 Decimal NaN / Infinity"
        )
    s = format(value, "f")  # 定点表示，避免指数
    if not _DECIMAL_RE.match(s):
        raise CanonicalizationError(
            f"无法规范化的 Decimal 表示: {s!r}"
        )
    return s


def _canonicalize_numpy(obj: Any) -> Any | None:
    """numpy 标量/数组 → 确定性原生类型；非 numpy 类型返回 None。"""
    try:
        import numpy as np
    except ImportError:
        return None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return canonicalize(obj.tolist())
    if isinstance(obj, (np.str_, np.bytes_)):
        return str(obj)
    return None


def canonicalize(obj: Any) -> Any:
    """把任意对象递归转换为「可确定性 JSON 化的原生结构」。

    支持：dataclass、enum、dict、list/tuple、set/frozenset、bytes、Decimal、
    datetime/date、numpy 标量/数组、标量。所有不确定性来源（set 迭代、
    object address、repr、locale 浮点、时区）在此处被消除。
    """
    npv = _canonicalize_numpy(obj)
    if npv is not None:
        return npv
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        if hasattr(obj, "to_plain") and callable(getattr(obj, "to_plain")):
            return canonicalize(obj.to_plain())
        return {
            _canonical_str(f.name): canonicalize(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
            if f.init
        }
    if isinstance(obj, enum.Enum):
        return canonicalize(obj.value)
    if isinstance(obj, dict):
        return {
            _canonical_str(str(k)): canonicalize(v) for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [canonicalize(x) for x in obj]
    if isinstance(obj, (set, frozenset)):
        # set 迭代顺序不确定 → 确定性排序（按 str 键，避免混型比较失败）
        return [
            canonicalize(x) for x in sorted(obj, key=lambda e: _canonical_str(str(e)))
        ]
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, bytearray):
        return bytes(obj).hex()
    if isinstance(obj, decimal.Decimal):
        return _canonical_decimal(obj)
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return _canonical_datetime(obj)
    if isinstance(obj, ValorID):
        # 类型化 ID：包含 id_type，确保不同 ID 类型哈希不同（检查单 E）
        return {"id_type": obj.id_type, "value": _canonical_str(obj.value)}
    if isinstance(obj, float):
        return _canonical_number(obj)
    if isinstance(obj, str):
        return _canonical_str(obj)
    if isinstance(obj, (int, bool)) or obj is None:
        return obj
    # 兜底：显式抛错而非 str(obj)（str(obj) 可能含 object address，破坏确定性）
    raise CanonicalizationError(
        f"canonicalize 不支持的类型: {type(obj).__name__!r}（拒绝隐式 str()）"
    )


def canonical_dumps(obj: Any, *, indent: int | None = None) -> str:
    """生成确定性 canonical JSON 字符串（sorted keys、ensure_ascii、紧凑）。"""
    return json.dumps(
        canonicalize(obj),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        indent=indent,
        allow_nan=False,  # 二次保险：禁止 nan/inf 进入承诺/哈希
    )


def canonical_bytes(obj: Any) -> bytes:
    """canonicalize(obj) -> bytes（检查单 C 要求返回 bytes）。"""
    return canonical_dumps(obj).encode("utf-8")
