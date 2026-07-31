"""JABO 经济目标：保证金、审计成本、资本成本、残差损失。

语义由论文固定并在此冻结：

* 诚实边界 ``tau_good`` 定义*审计*成本（行 + 证明）。
* 不合格边界 ``tau_bad`` 定义*残差损失*（漏检 = 接受了不合格数据）。
* INCONCLUSIVE 批次不予结算，因此永远不计为漏检——它对残差损失无贡献。
* 保证金公式尚未利用 INCONCLUSIVE 带来的额外保护，因此报告的保证金是保守下界。
"""
from __future__ import annotations

from .models import CostBreakdown, EconomicPolicy, OperatingPoint


def minimum_bond(
    detection_probability: float,
    economics: EconomicPolicy,
) -> float:
    """使坏质量边界下违约无利可图的最小卖方保证金。

    ``detection_probability`` 即 ``P(reject | tau_bad)``。保证金须覆盖
    ``g_max + safety_margin`` 并按检测概率的倒数放大，再减去诚实售价。
    """
    if not 0.0 < detection_probability <= 1.0:
        raise ValueError("detection_probability must be in (0, 1]")

    required = (
        economics.g_max + economics.safety_margin
    ) / detection_probability - economics.price
    return max(0.0, required)


def objective_cost(
    honest_boundary: OperatingPoint,
    bad_boundary: OperatingPoint,
    bond: float,
    economics: EconomicPolicy,
) -> CostBreakdown:
    """在两个 SPRT 边界处评估的完整 JABO 成本分解。

    审计成本用诚实边界的期望样本数 / 批数（卖方为审计好质量数据付费）。残差损失
    用坏质量边界的*接受*概率（买方在坏数据蒙混过关时的损失）。资本成本是锁定
    保证金的时间价值。
    """
    # 审计成本：在 epsilon = tau_good（诚实运营）处评估。
    row_cost = economics.cost_per_row * honest_boundary.expected_samples
    proof_cost = economics.cost_per_batch_proof * honest_boundary.expected_batches
    audit_cost = row_cost + proof_cost

    # 锁定保证金 lock_days 的资本成本。
    capital_cost = (
        economics.annual_capital_rate * bond * economics.lock_days / 365.0
    )

    # 残差损失：在 epsilon = tau_bad 处评估。INCONCLUSIVE 阻止结算，
    # 因此只有对坏数据的 ACCEPT 才计为漏检。
    residual_loss = economics.loss_if_missed * bad_boundary.accept_probability

    total = audit_cost + capital_cost + residual_loss

    return CostBreakdown(
        honest_boundary_contamination=honest_boundary.contamination,
        bad_boundary_contamination=bad_boundary.contamination,
        row_audit_cost=row_cost,
        proof_batch_cost=proof_cost,
        audit_cost=audit_cost,
        bond_capital_cost=capital_cost,
        residual_loss=residual_loss,
        objective_cost=total,
    )
