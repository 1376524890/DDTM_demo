"""Typed configuration and result dataclasses for the G0 experiment.

A single :class:`ExperimentConfig` is the unique source of parameters for the
SPRT evaluator, the JABO objective, the reproducibility metadata and the report
generator. There is no second place where ``tau_good`` or ``cost_per_row`` may
be read from — this is what makes the experiment reproducible and the report
auditable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class InconclusiveAction(str, Enum):
    """What the settlement layer does when the SPRT cannot decide.

    The only supported policy is to block settlement: an inconclusive batch is
    neither accepted nor settled, so it never counts as a successful delivery
    and therefore never counts as a missed delivery in the loss term.
    """

    BLOCK_SETTLEMENT = "block_settlement"


@dataclass(frozen=True)
class SprtPolicy:
    """Truncated Wald SPRT parameters."""

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
    """JABO economic constants."""

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
    """The single, validated configuration object consumed by all G0 stages."""

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
    """SPRT behaviour at a single contamination level.

    ``expected_batches`` is :math:`E[\\lceil T/\\mathrm{batch\\_size}\\rceil]`
    computed directly from the stopping distribution — not ``E[T]`` divided by
    the batch size.
    """

    contamination: float
    accept_probability: float
    reject_probability: float
    inconclusive_probability: float
    expected_samples: float
    expected_batches: float


@dataclass(frozen=True)
class CostBreakdown:
    """JABO objective cost and every additive component.

    ``objective_cost`` MUST equal the sum of the four additive components
    (row + proof + capital + residual); this is asserted by the G0 gate.
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
    """Recursively convert dataclasses/enums to JSON-serialisable structures."""
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_plain(getattr(obj, k)) for k in obj.__dataclass_fields__}
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    return obj
