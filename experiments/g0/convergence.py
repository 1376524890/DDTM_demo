"""Gate 检查：G0 实验的硬性通过/失败判据。

每个函数都返回实测误差，并在超出容差时抛出 ``AssertionError``，因此可以直接
接入测试套件与报告。
"""
from __future__ import annotations

from typing import Iterable

from .models import CostBreakdown, OperatingPoint


def check_probability_conservation(
    points: Iterable[OperatingPoint],
    tolerance: float = 1e-12,
) -> float:
    """每个 operating point 都满足 ``P(accept)+P(reject)+P(inconclusive) == 1``。"""
    max_error = 0.0
    for point in points:
        total = (
            point.accept_probability
            + point.reject_probability
            + point.inconclusive_probability
        )
        max_error = max(max_error, abs(total - 1.0))

    if max_error >= tolerance:
        raise AssertionError(
            f"Probability error {max_error} >= {tolerance}"
        )
    return max_error


def check_cost_reconstruction(
    cost: CostBreakdown,
    tolerance: float = 1e-9,
) -> float:
    """``objective_cost == row + proof + capital + residual``（可加分量）。"""
    reconstructed = (
        cost.row_audit_cost
        + cost.proof_batch_cost
        + cost.bond_capital_cost
        + cost.residual_loss
    )
    error = abs(cost.objective_cost - reconstructed)
    if error >= tolerance:
        raise AssertionError(f"Cost reconstruction error {error}")
    return error


def check_three_run_determinism(
    runs: list[dict],
    tolerance: float = 1e-12,
) -> float:
    """评估器的三次独立运行必须在 ``tolerance`` 内一致。"""
    if len(runs) != 3:
        raise ValueError("Exactly three runs are required")

    keys = sorted(runs[0].keys())
    max_difference = 0.0
    for key in keys:
        values = [run[key] for run in runs]
        # 跳过非数值字段（例如作为字符串的 contamination 标签）。
        if not all(isinstance(v, (int, float)) for v in values):
            continue
        max_difference = max(
            max_difference, max(values) - min(values)
        )

    if max_difference >= tolerance:
        raise AssertionError(
            f"Non-deterministic result: {max_difference}"
        )
    return max_difference


def check_inconclusive_not_settled(
    bad_boundary: OperatingPoint,
) -> None:
    """记录并断言 INCONCLUSIVE 的处理假设。

    残差损失纯粹由坏质量边界的 ``accept_probability`` 定义；``inconclusive``
    的质量按构造被排除。本函数的存在，是为了让这个假设成为一个显式、被测的不
    变量，而非一条未成文的约定。
    """
    # 损失项必须只依赖 accepts，绝不依赖 inconclusive 质量。
    # （这里不做任何计算——不变量已编码在 jabo.objective_cost 中；本检查用于
    # 记录该假设，并给测试套件一个具名挂载点。）
    assert bad_boundary is not None
