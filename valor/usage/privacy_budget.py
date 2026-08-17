"""QueryPrivacyBudget vs AuditDisclosureBudget（规范 §34 / P0-H）。

禁止把 DP 预算 ε 映射为行数/字节数。两个语义完全不同的预算结构：

    QueryPrivacyBudget   —— 属于 usage/query rights（DP 预算 ε/δ + accountant）
    AuditDisclosureBudget —— 属于 PrivacyAuditPolicy / seller audit consent
                             （max_unique_rows / max_fraction / max_bytes）

禁止自动转换（MFC-G07）。隐私审计用 AuditDisclosureBudget；API/DP query 用
QueryPrivacyBudget。Selective disclosure 指标只统计 unique rows/fraction/bytes，
禁止表述 "4.1% disclosure = 95.9% privacy"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PrivacyBudgetSemanticsError(Exception):
    """两种预算被错误混用。"""

    code = "PRIVACY_BUDGET_SEMANTIC_MISMATCH"


@dataclass(frozen=True)
class QueryPrivacyBudget:
    """DP 查询隐私预算（usage/query rights，§34 ε 语义）。"""

    epsilon: float
    delta: float
    accountant_id: str
    purpose: str = ""

    def __post_init__(self) -> None:
        if self.epsilon <= 0 or self.delta < 0 or self.delta >= 1:
            raise ValueError("QueryPrivacyBudget 必须 epsilon>0, 0<=delta<1")

    def to_plain(self) -> dict:
        return {
            "epsilon": self.epsilon, "delta": self.delta,
            "accountant_id": self.accountant_id, "purpose": self.purpose,
        }


@dataclass
class AuditDisclosureBudget:
    """审计选择性披露预算（PrivacyAuditPolicy / seller audit consent）。

    以 unique rows / fraction / bytes 度量，与 DP ε 无关。禁止从 QueryPrivacyBudget
    自动转换（MFC-G07）。
    """

    max_unique_rows: int
    max_fraction: float
    max_bytes: int
    policy_ref: str = ""
    source_kind: str = "AUDIT_CONSENT"

    def __post_init__(self) -> None:
        if self.max_unique_rows <= 0:
            raise ValueError(
                "AuditDisclosureBudget 必须显式来自 audit consent/policy（禁止默认）")
        if not (0.0 < self.max_fraction <= 1.0):
            raise ValueError("max_fraction 必须在 (0,1]")

    def to_plain(self) -> dict:
        return {
            "max_unique_rows": self.max_unique_rows,
            "max_fraction": self.max_fraction, "max_bytes": self.max_bytes,
            "policy_ref": self.policy_ref, "source_kind": self.source_kind,
        }


def forbid_conversion(*, dp_budget: QueryPrivacyBudget,
                      disclosure: AuditDisclosureBudget) -> None:
    """显式禁止把 DP ε 映射为行数/字节数（MFC-G07 语义分离）。"""
    raise PrivacyBudgetSemanticsError(
        "QueryPrivacyBudget（DP ε）与 AuditDisclosureBudget（行/字节）语义不同，"
        "禁止自动转换。隐私审计必须使用 AuditDisclosureBudget，API/DP query 使用 "
        "QueryPrivacyBudget。"
    )


__all__ = [
    "QueryPrivacyBudget", "AuditDisclosureBudget",
    "PrivacyBudgetSemanticsError", "forbid_conversion",
]
