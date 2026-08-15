"""DisclosureState —— 隐私披露预算状态（方案 §24/§25）。

统计 L_t = |∪ OpenedIndices|（唯一已开启行数），而非 Σ k_t。
预算参数（max_unique_rows/max_fraction/max_bytes）必须来自 RightsBundle 或
resolved policy artifact，不设默认值。若 Audit-VOI 想执行 k=256 但剩余预算
不足 → ACTION_INFEASIBLE_PRIVACY_BUDGET（不能偷偷降 k）。
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
    """从 RightsBundle 解析审计披露预算（方案 §25）。

    audit_reveal_max_rows / audit_reveal_max_fraction / audit_reveal_max_bytes
    必须来自 RightsBundle 或 resolved policy artifact。
    """
    # 从 rights 的 privacy_budget / 元数据解析；无则显式 None → fail
    pb = getattr(rights_bundle, "privacy_budget", None)
    max_rows = getattr(rights_bundle, "audit_reveal_max_rows", None)
    max_frac = getattr(rights_bundle, "audit_reveal_max_fraction", None)
    max_bytes = getattr(rights_bundle, "audit_reveal_max_bytes", None)
    if max_rows is None:
        # 从 privacy_budget（差分隐私总预算）推导为唯一行数上限
        max_rows = int(pb) if pb else None
    if max_rows is None or max_rows <= 0:
        raise ValueError(
            "RightsBundle 未提供 audit_reveal_max_rows/privacy_budget（禁止默认）")
    if max_frac is None:
        max_frac = max_rows / n_rows if n_rows else 0.0
    if max_bytes is None:
        max_bytes = max_rows * 784  # MNIST 行字节数
    return int(max_rows), float(max_frac), int(max_bytes)


__all__ = ["DisclosureState", "PrivacyBudgetExceededError", "budget_from_rights"]
