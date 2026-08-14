"""VALOR 核心基础工具。

包含枚举、货币单位、哈希、canonical JSON 序列化、错误层级与 ID 工具。
本层为纯标准库实现，供所有其他子包复用（Phase 0 交付）。
"""

from .enums import (
    DeliveryMode,
    MigrationClass,
    ParamSource,
    QualityImplementationKind,
    RightsState,
    TerminalState,
    TradeState,
)
from .errors import (
    COUNTERFACTUAL_INFEASIBLE,
    INFEASIBLE_SECURITY,
    MISSING_EVIDENCE_REF,
    OUT_OF_CERTIFIED_RANGE,
    PROFILE_OUT_OF_CERTIFIED_RANGE,
    UNIT_MISMATCH,
    UNRESOLVED_PARAMETER,
    VALORError,
    CommitBindingError,
    EntitlementError,
)
from .money import CURRENCY_UNIT, assert_unit, Money, to_cu
from .hashing import content_hash, sha256_hex, stable_hash
from .canonical_json import canonical_dumps, canonicalize

__all__ = [
    "DeliveryMode",
    "MigrationClass",
    "ParamSource",
    "QualityImplementationKind",
    "RightsState",
    "TerminalState",
    "TradeState",
    "COUNTERFACTUAL_INFEASIBLE",
    "INFEASIBLE_SECURITY",
    "MISSING_EVIDENCE_REF",
    "OUT_OF_CERTIFIED_RANGE",
    "PROFILE_OUT_OF_CERTIFIED_RANGE",
    "UNIT_MISMATCH",
    "UNRESOLVED_PARAMETER",
    "VALORError",
    "CommitBindingError",
    "EntitlementError",
    "CURRENCY_UNIT",
    "assert_unit",
    "Money",
    "to_cu",
    "content_hash",
    "sha256_hex",
    "stable_hash",
    "canonical_dumps",
    "canonicalize",
]
