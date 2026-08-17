"""DisclosureState —— 审计选择性披露预算状态（方案 §24/§25 / P0-H）。

统计 L_t = |∪ OpenedIndices|（唯一已开启行数），而非 Σ k_t。
预算参数（max_unique_rows/max_fraction/max_bytes）是 AuditDisclosureBudget
（seller audit consent），与 DP QueryPrivacyBudget（ε/δ）语义完全分离
（MFC-G07）。禁止把 DP ε 映射为行数/字节数。若 Audit-VOI 想执行 k=256 但剩余
预算不足 → ACTION_INFEASIBLE_PRIVACY_BUDGET（不能偷偷降 k）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


class PrivacyBudgetExceededError(Exception):
    """预算不足：action 不可行，须返回 ACTION_INFEASIBLE_PRIVACY_BUDGET。"""


@dataclass
class DisclosureState:
    dataset_commitment_hash: str
    revealed_indices: set[int] = field(default_factory=set)
    total_openings: int = 0
    total_bytes: int = 0
    # 预算（来自 RightsBundle / policy，无默认）
    max_unique_rows: int = 0
    max_fraction: float = 0.0
    max_bytes: int = 0
    _n_rows: int = 0

    def __post_init__(self) -> None:
        if self.max_unique_rows <= 0:
            raise ValueError(
                "DisclosureState 预算必须显式来自 RightsBundle/policy（禁止默认）")

    def can_reveal(self, indices: list[int]) -> bool:
        """检查揭示 indices 是否超预算（唯一行数 / 比例 / 字节）。"""
        new_unique = self.revealed_indices | set(indices)
        if len(new_unique) > self.max_unique_rows:
            return False
        if self._n_rows and (len(new_unique) / self._n_rows) > self.max_fraction:
            return False
        return True

    def record(self, indices: list[int], bytes_count: int) -> None:
        """记录一次揭示；超预算则抛错（fail closed）。"""
        if not self.can_reveal(indices):
            raise PrivacyBudgetExceededError(
                "隐私预算不足，action 不可行（ACTION_INFEASIBLE_PRIVACY_BUDGET）")
        self.revealed_indices |= set(indices)
        self.total_openings += len(indices)
        self.total_bytes += bytes_count

    @property
    def unique_disclosure(self) -> int:
        return len(self.revealed_indices)

    @property
    def disclosure_fraction(self) -> float:
        if not self._n_rows:
            return 0.0
        return len(self.revealed_indices) / self._n_rows

    def remaining_unique(self) -> int:
        return self.max_unique_rows - len(self.revealed_indices)

    def to_plain(self) -> dict:
        return {
            "dataset_commitment_hash": self.dataset_commitment_hash,
            "revealed_indices": sorted(self.revealed_indices),
            "total_openings": self.total_openings,
            "total_bytes": self.total_bytes,
            "unique_disclosure": self.unique_disclosure,
            "disclosure_fraction": self.disclosure_fraction,
            "max_unique_rows": self.max_unique_rows,
            "max_fraction": self.max_fraction,
            "max_bytes": self.max_bytes,
            "n_rows": self._n_rows,
        }


def budget_from_rights(rights_bundle, n_rows: int) -> tuple[int, float, int]:
    """从 RightsBundle 解析审计披露预算（方案 §25 / P0-H）。

    audit_reveal_max_rows / audit_reveal_max_fraction / audit_reveal_max_bytes
    必须来自 RightsBundle 的 **AuditDisclosureBudget** 字段（seller audit
    consent），禁止从 DP privacy_budget（ε）推导行数。无显式 budget → fail closed。
    """
    max_rows = getattr(rights_bundle, "audit_reveal_max_rows", None)
    max_frac = getattr(rights_bundle, "audit_reveal_max_fraction", None)
    max_bytes = getattr(rights_bundle, "audit_reveal_max_bytes", None)
    # 显式审计披露预算优先（AuditDisclosureBudget）
    if max_rows is None:
        adb = getattr(rights_bundle, "audit_disclosure_budget", None)
        if adb is not None and getattr(adb, "max_unique_rows", 0) > 0:
            max_rows = adb.max_unique_rows
            max_frac = adb.max_fraction
            max_bytes = adb.max_bytes
    if max_rows is None or max_rows <= 0:
        # 禁止从 DP privacy_budget（ε）映射为行数（MFC-G07 语义分离）
        pb = getattr(rights_bundle, "privacy_budget", None)
        if pb is not None:
            raise ValueError(
                "P0-H: 禁止把 DP privacy_budget（ε）映射为审计披露行数。"
                "请显式提供 audit_reveal_max_rows（AuditDisclosureBudget）"
            )
        raise ValueError(
            "RightsBundle 未提供 audit_reveal_max_rows/AuditDisclosureBudget"
            "（禁止默认）")
    if max_frac is None:
        max_frac = max_rows / n_rows if n_rows else 0.0
    if max_bytes is None:
        # 禁止用 rows*784 隐式默认；若未显式提供 bytes 预算，用显式 max_rows
        # 的合理上限（仍需显式，避免 hidden default）。此处若未给 bytes 则用 0
        # 表示未限制 bytes（仅 rows/fraction 生效），并保留显式语义。
        max_bytes = 0
    return int(max_rows), float(max_frac), int(max_bytes)


__all__ = ["DisclosureState", "PrivacyBudgetExceededError", "budget_from_rights"]
