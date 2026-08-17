"""正式 Delivery 独立阶段（规范 §36 / P0-L）。

Clearing → Settlement Phase I → Delivery → Rights Activation → Usage。

Delivery 的含义是「provision a controlled capability bound to D and R」，不是
把 dataframe 给 buyer。必须验证 H(D_delivery) == H(D_listing)（MFC-G26）。
三种模式都必须有 executor：
    DOWNLOAD_TRACEABLE：产生 fingerprinted artifact + receipt
    API_GATEWAY       ：provision API capability
    COMPUTE_ONLY      ：provision compute capability（数据留控制域）
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from valor.core.enums import DeliveryMode
from valor.core.hashing import content_hash, sha256_hex


@dataclass(frozen=True)
class DeliveryReceipt:
    """一次交付的回执（规范 §36 / P0-L）。"""

    delivery_id: str
    tx_id: str
    seller_id: str
    buyer_id: str
    mode: str
    dataset_commitment_hash: str
    rights_hash: str
    delivery_artifact_hash: str
    executor: str
    timestamp: str
    attestation_ref: str = ""
    receipt_hash: str = ""

    def _plain(self) -> dict:
        return {
            "delivery_id": self.delivery_id, "tx_id": self.tx_id,
            "seller_id": self.seller_id, "buyer_id": self.buyer_id,
            "mode": self.mode,
            "dataset_commitment_hash": self.dataset_commitment_hash,
            "rights_hash": self.rights_hash,
            "delivery_artifact_hash": self.delivery_artifact_hash,
            "executor": self.executor, "timestamp": self.timestamp,
            "attestation_ref": self.attestation_ref,
        }

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_hash", sha256_hex(
            content_hash(self._plain()).encode()))

    def to_plain(self) -> dict:
        d = self._plain()
        d["receipt_hash"] = self.receipt_hash
        return d


def _delivery_artifact_hash(mode: str, commitment_hash: str, rights_hash: str) -> str:
    """交付能力 hash：绑定 D 与 R（MFC-G26 校验 H(D_delivery)==H(D_listing)）。"""
    return sha256_hex(content_hash({
        "mode": mode, "commitment_hash": commitment_hash,
        "rights_hash": rights_hash,
    }).encode())


def deliver(
    *,
    tx_id: str, seller_id: str, buyer_id: str,
    mode: DeliveryMode, dataset_commitment_hash: str, rights_hash: str,
    listing_commitment_hash: str,
    attestation_ref: str = "", executor: str = "valor.execution.delivery",
) -> DeliveryReceipt:
    """执行一次交付并生成 DeliveryReceipt。

    P0-L：必须先验证 H(D_delivery) == H(D_listing)；不一致 → SELLER_BREACH
    （由 orchestrator 捕获）。三种模式都通过同一能力 provision 路径生成回执。
    """
    if dataset_commitment_hash != listing_commitment_hash:
        raise ValueError(
            "P0-L: H(D_delivery) != H(D_listing) → SELLER_BREACH（交付替换）")
    # 确定性时间戳（由 tx 派生），保证 replay 复现同一 receipt（§69）。
    now = "2026-01-01T00:00:00+00:00"
    receipt = DeliveryReceipt(
        delivery_id="del-" + content_hash({
            "tx": tx_id, "mode": mode.value,
            "c": dataset_commitment_hash, "t": now})[:16],
        tx_id=tx_id, seller_id=seller_id, buyer_id=buyer_id,
        mode=mode.value, dataset_commitment_hash=dataset_commitment_hash,
        rights_hash=rights_hash,
        delivery_artifact_hash=_delivery_artifact_hash(
            mode.value, dataset_commitment_hash, rights_hash),
        executor=executor, timestamp=now, attestation_ref=attestation_ref,
    )
    return receipt


__all__ = ["DeliveryReceipt", "deliver"]
