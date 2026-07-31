"""G0 实验的类型化配置与结果数据类。

唯一的 :class:`ExperimentConfig` 是 SPRT 评估器、JABO 目标函数、可复现性元数据
与报告生成器共同读取的参数来源。这里不存在第二个可以读取 ``tau_good`` 或
``cost_per_row`` 的地方——这正是实验可复现、报告可审计的根本原因。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class InconclusiveAction(str, Enum):
    """SPRT 无法决断时结算层的处理方式。

    唯一支持的策略是阻止结算：一个 INCONCLUSIVE 批次既不被接受、也不被结算，
    因此它永远不会被计为一次成功交付，也就永远不会计入漏检损失项。
    """

    BLOCK_SETTLEMENT = "block_settlement"


@dataclass(frozen=True)
class SprtPolicy:
    """截断 Wald SPRT 的参数。"""

    tau_good: float
    tau_bad: float
    alpha: float
    beta: float
    batch_size: int
    max_samples: int

    def validate(self) -> None:
        if not 0.0 < self.tau_good < self.tau_bad < 1.0:
            raise ValueError("Expected 0 < tau_good < tau_bad < 1")
        if not 0.0 < self.alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        if not 0.0 < self.beta < 1.0:
            raise ValueError("beta must be in (0, 1)")
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.max_samples <= 0:
            raise ValueError("max_samples must be positive")


@dataclass(frozen=True)
class EconomicPolicy:
    """JABO 经济常量。"""

    price: float
    g_max: float
    loss_if_missed: float
    cost_per_row: float
    cost_per_batch_proof: float
    annual_capital_rate: float
    lock_days: float
    safety_margin: float

    def validate(self) -> None:
        values = asdict(self)
        for name, value in values.items():
            if value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class ExperimentConfig:
    """G0 各阶段共同消费的唯一、经过校验的配置对象。"""

    sprt: SprtPolicy
    economics: EconomicPolicy
    inconclusive_action: InconclusiveAction
    evaluation_grid: tuple[float, ...]

    def validate(self) -> None:
        self.sprt.validate()
        self.economics.validate()
        for contamination in self.evaluation_grid:
            if not 0.0 <= contamination <= 1.0:
                raise ValueError(f"Invalid contamination: {contamination}")


@dataclass(frozen=True)
class OperatingPoint:
    """某个污染水平下的 SPRT 行为。

    ``expected_batches`` 是直接由停止分布算出的
    :math:`E[\\lceil T/\\mathrm{batch\\_size}\\rceil]`，而不是 ``E[T]`` 除以
    批大小。
    """

    contamination: float
    accept_probability: float
    reject_probability: float
    inconclusive_probability: float
    expected_samples: float
    expected_batches: float


@dataclass(frozen=True)
class CostBreakdown:
    """JABO 目标成本及其每一个可加分量。

    ``objective_cost`` 必须等于四个可加分量（行 + 证明 + 资本 + 残差）之和；
    这一点由 G0 gate 断言。
    """

    honest_boundary_contamination: float
    bad_boundary_contamination: float
    row_audit_cost: float
    proof_batch_cost: float
    audit_cost: float
    bond_capital_cost: float
    residual_loss: float
    objective_cost: float


def to_plain(obj: Any) -> Any:
    """把数据类/枚举递归转换为可 JSON 序列化的结构。"""
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_plain(getattr(obj, k)) for k in obj.__dataclass_fields__}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    return obj
