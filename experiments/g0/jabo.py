"""JABO economic objective: bond, audit cost, capital cost, residual loss.

Semantics fixed by the paper and frozen here:

* The honest boundary ``tau_good`` defines the *audit* cost (rows + proofs).
* The bad boundary ``tau_bad`` defines the *residual loss* (a missed delivery
  is an ACCEPT of bad-quality data).
* An INCONCLUSIVE batch is not settled, so it is never counted as a missed
  delivery — it contributes nothing to the residual loss.
* The bond formula does not yet exploit the extra protection an INCONCLUSIVE
  outcome buys, so the reported bond is a conservative lower bound.
"""
from __future__ import annotations

from .models import CostBreakdown, EconomicPolicy, OperatingPoint


def minimum_bond(
    detection_probability: float,
    economics: EconomicPolicy,
) -> float:
    """Smallest seller bond making defection unprofitable at the bad boundary.

    ``detection_probability`` is ``P(reject | tau_bad)``. The bond must cover
    ``g_max + safety_margin`` scaled by the inverse detection probability, less
    the honest sale price.
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
    """Full JABO cost breakdown evaluated at the two SPRT boundaries.

    Audit cost uses the honest boundary's expected samples / batches (the
    seller pays to audit good-quality data). Residual loss uses the bad
    boundary's *accept* probability (the buyer's loss when bad data slips
    through). Capital cost is the time-value of the locked bond.
    """
    # Audit cost: evaluated at epsilon = tau_good (honest operation).
    row_cost = economics.cost_per_row * honest_boundary.expected_samples
    proof_cost = economics.cost_per_batch_proof * honest_boundary.expected_batches
    audit_cost = row_cost + proof_cost

    # Capital cost of locking the bond for lock_days.
    capital_cost = (
        economics.annual_capital_rate * bond * economics.lock_days / 365.0
    )

    # Residual loss: evaluated at epsilon = tau_bad. INCONCLUSIVE blocks
    # settlement, so only an ACCEPT of bad data counts as a miss.
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
