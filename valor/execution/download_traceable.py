"""DOWNLOAD_TRACEABLE 交付（规范 §36.1）。

买方获得可用副本，系统无法可靠阻止离线复制，因此只声明 PreventionStrength <
API/Compute。采取：接收方指纹、交付回执、hash/version 绑定、合同用途约束、
泄露追踪、买方 usage liability。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from valor.core.hashing import content_hash

from .fingerprint import embed_fingerprint, recipient_fingerprint


@dataclass
class DownloadTraceableDelivery:
    """可追溯下载交付。"""

    def deliver(self, df: pd.DataFrame, buyer_id: str, salt: str) -> dict:
        """生成带指纹的副本与交付回执。"""
        fp = recipient_fingerprint(buyer_id, salt)
        # 序列化 + 指纹嵌入
        data_bytes = df.to_csv(index=False).encode("utf-8")
        watermarked = embed_fingerprint(data_bytes, fp)
        receipt = {
            "delivery_mode": "DOWNLOAD_TRACEABLE",
            "buyer_id": buyer_id,
            "fingerprint": fp,
            "content_hash": content_hash(df.to_dict("list")),
            "prevention_strength": "traceable-not-blockable",  # 不虚假声称
        }
        return {"payload": watermarked, "receipt": receipt}
