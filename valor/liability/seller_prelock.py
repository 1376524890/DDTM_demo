"""卖方保证金预锁（规范 §31）。

为了让 audit-stage SELLER_BREACH 确实存在可罚没资金，在进入需要卖方责任覆盖的
审计前：B_S^pre = max_{ω∈Ω_allowed} B_S^*(ω)。审计完成后按实际 certified
profile 得 B_S^*，释放差额。
"""

from __future__ import annotations

from .seller_bond import seller_bond_required


def seller_prelock(
    *,
    cells: list[dict],  # 各允许 cell 的 p̲_B^sys（Ω_allowed）
    g_dev: float,
    eps_s: float,
    p_e_bond: float,
    p_e_f: float,
    lambda_s: float,
    f_s: float,
) -> float:
    """B_S^pre = max_ω B_S^*(ω)（§31）。"""
    pre = max(
        seller_bond_required(
            p_breach_lower_sys=cell["p_breach_lower_sys"],
            g_dev=g_dev, eps_s=eps_s, p_e_bond=p_e_bond,
            p_e_f=p_e_f, lambda_s=lambda_s, f_s=f_s,
        )
        for cell in cells
    )
    return pre
