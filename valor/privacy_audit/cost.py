"""AuditCostBreakdown —— 审计动作成本分解（方案 §26）。

Audit-VOI 正式公式仍用 MC_A^pay = 真实 VCG payment。
资源成本（compute/communication/rows_disclosed/privacy）不直接加进 CU，
用于 RQ2/RQ3/RQ5。若需把 privacy cost 货币化，须另行 calibration/provenance。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuditCostBreakdown:
    action_id: str
    vcg_payment: float  # MC_A^pay（正式进 Audit-VOI）
    seller_compute_ms: float
    auditor_compute_ms: float
    bytes_seller_to_auditor: int
    bytes_auditor_to_scheduler: int
    rows_disclosed_unique: int
    privacy_cost: float
    total_pay_cost: float
    total_resource_cost: float

    def to_plain(self) -> dict:
        return {
            "action_id": self.action_id,
            "vcg_payment": self.vcg_payment,
            "seller_compute_ms": self.seller_compute_ms,
            "auditor_compute_ms": self.auditor_compute_ms,
            "bytes_seller_to_auditor": self.bytes_seller_to_auditor,
            "bytes_auditor_to_scheduler": self.bytes_auditor_to_scheduler,
            "rows_disclosed_unique": self.rows_disclosed_unique,
            "privacy_cost": self.privacy_cost,
            "total_pay_cost": self.total_pay_cost,
            "total_resource_cost": self.total_resource_cost,
        }


def cost_breakdown(
    *,
    action_id: str,
    vcg_payment: float,
    seller_compute_ms: float = 0.0,
    auditor_compute_ms: float = 0.0,
    bytes_seller_to_auditor: int = 0,
    bytes_auditor_to_scheduler: int = 0,
    rows_disclosed_unique: int = 0,
    privacy_cost: float = 0.0,
    resource_weight: float = 0.0,  # 资源成本→CU 换算（须显式来源，无默认）
) -> AuditCostBreakdown:
    return AuditCostBreakdown(
        action_id=action_id, vcg_payment=vcg_payment,
        seller_compute_ms=seller_compute_ms,
        auditor_compute_ms=auditor_compute_ms,
        bytes_seller_to_auditor=bytes_seller_to_auditor,
        bytes_auditor_to_scheduler=bytes_auditor_to_scheduler,
        rows_disclosed_unique=rows_disclosed_unique,
        privacy_cost=privacy_cost,
        total_pay_cost=vcg_payment,
        total_resource_cost=(
            resource_weight * (
                (seller_compute_ms + auditor_compute_ms) / 1000.0
                + bytes_seller_to_auditor / 1024.0
                + rows_disclosed_unique
            )
        ),
    )


__all__ = ["AuditCostBreakdown", "cost_breakdown"]
