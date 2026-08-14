"""检测能力认证（规范 §22/§67 / Phase 3）。

对 breach family h、certified cell c：
    p_{B,h,c} ~ Beta(a_D + TP_{h,c}, b_D + FN_{h,c})
    p̲_{B,h,c} = Q_{α_D}[p_{B,h,c}]（保守下界）
合同保护多个 breach family 时 p̲_B^sys = min_{h} p̲_{B,h,c}。
输入不属于任何认证 cell → PROFILE_OUT_OF_CERTIFIED_RANGE。
certification_sample_size 按 §67 搜索满足目标的最小样本数。
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy.stats import beta

from valor.core.errors import ProfileOutOfCertifiedRangeError


@dataclass(frozen=True)
class CertifiedCell:
    """一个认证检测 cell（连续参数空间的有限离散化，§22）。"""

    cell_id: str
    a_D: float
    b_D: float
    alpha_D: float  # 下界置信分位数
    # 每 breach family 的检测样本（TP/FN）
    families: dict[str, tuple[int, int]]


class CertificationCatalog:
    """认证 cell 目录。"""

    def __init__(self) -> None:
        self._cells: dict[str, CertifiedCell] = {}

    def register(self, cell: CertifiedCell) -> None:
        self._cells[cell.cell_id] = cell

    def get(self, cell_id: str) -> CertifiedCell:
        if cell_id not in self._cells:
            raise ProfileOutOfCertifiedRangeError(
                f"cell {cell_id} 不在认证目录（PROFILE_OUT_OF_CERTIFIED_RANGE）"
            )
        return self._cells[cell_id]

    def p_breach_lower(self, cell_id: str, family: str) -> float:
        """Q_{α_D}[Beta(a_D+TP, b_D+FN)]（§22 保守下界）。"""
        cell = self.get(cell_id)
        if family not in cell.families:
            raise KeyError(f"cell {cell_id} 无 breach family {family}")
        tp, fn = cell.families[family]
        return float(beta.ppf(cell.alpha_D, cell.a_D + tp, cell.b_D + fn))

    def certified_pB_sys(self, cell_id: str, contract_families: list[str]) -> float:
        """p̲_B^sys = min_{h∈H_contract} p̲_{B,h,c}（§22）。"""
        lows = [self.p_breach_lower(cell_id, h) for h in contract_families]
        return min(lows)


def certification_sample_size(
    *,
    a_D: float,
    b_D: float,
    alpha_D: float,
    p_target: float,
    fn_allow: int,
    max_scan: int = 100000,
) -> int:
    """搜索满足 Q_{α_D}[Beta(a_D+TP, b_D+FN)] ≥ p_target 的最小 TP 样本数（§67）。"""
    for tp in range(1, max_scan + 1):
        q = beta.ppf(alpha_D, a_D + tp, b_D + fn_allow)
        if q >= p_target:
            return tp
    raise RuntimeError(f"在 {max_scan} 内未找到满足目标的样本数")
