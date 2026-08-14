"""确定性 canonical JSON 序列化。

对齐规范：
- §4 对象绑定 / 承诺哈希（H(D), H(M_D), H(R_τ)）需跨平台一致
- §33 lineage hash chain：h_t = H(h_{t-1} ∥ Canonical(e_t))
- §54.5 UsageReceipt 可 canonicalize、hash、签名
- §5 参数哈希可复现

保证：key 排序稳定、ASCII 编码稳定、无多余空白，从而任意两次序列化结果一致。
"""

from __future__ import annotations

import dataclasses
import enum
import json
from typing import Any


def _sort_key(item: tuple[str, Any]) -> str:
    """dict 排序键：始终按 str(key) 排序，保证确定性。"""
    return str(item[0])


def canonicalize(obj: Any) -> Any:
    """把任意对象递归转换为「可确定性 JSON 化的原生结构」。

    支持：dataclass、enum、dict、list/tuple、标量。numpy 等第三方对象
    若实现了 tolist/round 等，可在上层自定义 to_plain() 后再传入。
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        # dataclass 优先调用自身 to_plain()（可自定义裁剪/单位），否则逐字段转换
        if hasattr(obj, "to_plain") and callable(getattr(obj, "to_plain")):
            return canonicalize(obj.to_plain())
        return {
            f.name: canonicalize(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
            if f.init  # 仅序列化构造参数，避免冗余
        }
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): canonicalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [canonicalize(x) for x in obj]
    if isinstance(obj, float):
        # 保证 -0.0 与 0.0、nan/inf 的可确定性处理
        return float(obj)
    if isinstance(obj, (int, str, bool)) or obj is None:
        return obj
    # 兜底：其他类型（如 UUID、Path）转字符串
    return str(obj)


def canonical_dumps(obj: Any, *, indent: int | None = None) -> str:
    """生成确定性 canonical JSON 字符串。

    - sort_keys=True：key 顺序无关
    - ensure_ascii=True：编码稳定
    - separators 固定：紧凑输出（无多余空白）
    """
    return json.dumps(
        canonicalize(obj),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        indent=indent,
        allow_nan=False,  # 禁止 nan/inf 进入承诺/哈希
    )
