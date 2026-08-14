"""SHA-256 哈希工具（承诺 / 绑定 / 证书 / lineage 用）。

对齐规范：
- §4 对象绑定：H(D), H(M_D), H(R_τ)
- §16 节点承诺：H(D_node)=H(D)_τ, H(AlgorithmSpec_node)=H(AlgorithmSpec)_{T_a}
- §33 lineage hash chain：h_t = H(h_{t-1} ∥ Canonical(e_t))
- §15.1 deterministic primitive：H(Output_native)=H(Output_reference)

SHA-256 属 STANDARD_CONSTANT 来源（规范 §5.2）。
"""

from __future__ import annotations

import hashlib
from typing import Any

from .canonical_json import canonical_dumps


def sha256_hex(data: bytes) -> str:
    """对字节串计算 SHA-256 十六进制摘要。"""
    return hashlib.sha256(data).hexdigest()


def content_hash(obj: Any) -> str:
    """对任意对象（可 canonicalize）计算确定性内容哈希。

    先做 canonical JSON 序列化，再取 SHA-256，保证跨平台一致。
    """
    blob = canonical_dumps(obj).encode("utf-8")
    return sha256_hex(blob)


def stable_hash(*parts: Any) -> str:
    """对多个部分拼接后取哈希；用于哈希链 h_t = H(h_prev ∥ canonical(e_t))。

    参数可为字节、字符串或可 canonicalize 对象。
    """
    buf = b""
    for part in parts:
        if isinstance(part, bytes):
            buf += part
        elif isinstance(part, str):
            buf += part.encode("utf-8")
        else:
            buf += canonical_dumps(part).encode("utf-8")
    return sha256_hex(buf)
