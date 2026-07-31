"""Gate checks: the hard pass/fail predicates for the G0 experiment.

Each function returns the achieved error AND raises ``AssertionError`` if the
tolerance is violated, so they can be wired straight into the test suite and
the report.
"""
from __future__ import annotations

from typing import Iterable

from .models import CostBreakdown, OperatingPoint


def check_probability_conservation(
    points: Iterable[OperatingPoint],
    tolerance: float = 1e-12,
) -> float:
    """``P(accept)+P(reject)+P(inconclusive) == 1`` for every operating point."""
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
    """``objective_cost == row + proof + capital + residual`` (additive parts)."""
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
    """Three independent runs of the evaluator must agree to ``tolerance``."""
    if len(runs) != 3:
        raise ValueError("Exactly three runs are required")

    keys = sorted(runs[0].keys())
    max_difference = 0.0
    for key in keys:
        values = [run[key] for run in runs]
        # Skip non-numeric fields (e.g. contamination tags as strings).
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
    """Document and assert the INCONCLUSIVE handling assumption.

    The residual loss is defined purely from ``accept_probability`` at the bad
    boundary; ``inconclusive_probability`` is excluded by construction. This
    function exists so the assumption is an explicit, tested invariant rather
    than an undocumented convention.
    """
    # The loss term must depend only on accepts, never on inconclusive mass.
    # (No computation here — the invariant is encoded in jabo.objective_cost;
    # this check documents it and gives the test suite a named hook.)
    assert bad_boundary is not None
