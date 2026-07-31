"""Exact SPRT evaluation by integer-state dynamic programming.

The log-likelihood ratio after ``samples`` observations with ``failures``
anomalies is a deterministic function of the *integer* pair ``(samples,
failures)`` — so we use that pair as the DP state key instead of a noisy
floating LLR. This simultaneously yields the exact stopping distribution,
``E[T]``, and ``E[ceil(T / batch_size)]`` from the same pass.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .models import OperatingPoint, SprtPolicy


def sprt_constants(policy: SprtPolicy) -> tuple[float, float, float, float]:
    """Return (lower, upper, hit_increment, clean_increment) for the policy.

    ``lower``/``upper`` are the Wald accept/reject log boundaries; the two
    increments are the per-sample LLR contributions of an anomaly and a clean
    observation respectively.
    """
    policy.validate()

    lower = math.log(policy.beta / (1.0 - policy.alpha))
    upper = math.log((1.0 - policy.beta) / policy.alpha)
    hit_increment = math.log(policy.tau_bad / policy.tau_good)
    clean_increment = math.log((1.0 - policy.tau_bad) / (1.0 - policy.tau_good))
    return lower, upper, hit_increment, clean_increment


def state_llr(
    samples: int,
    failures: int,
    hit_increment: float,
    clean_increment: float,
) -> float:
    """LLR of state ``(samples, failures)`` under H1 vs H0."""
    clean = samples - failures
    return failures * hit_increment + clean * clean_increment


def evaluate_operating_point(
    contamination: float,
    policy: SprtPolicy,
) -> OperatingPoint:
    """Evaluate the SPRT at one contamination level via exact DP.

    Probability mass flows over integer ``(samples, failures)`` states. A state
    that crosses a boundary (or hits ``max_samples``) is removed from the
    active set and its mass is added to the appropriate outcome and to the
    expected-sample / expected-batch accumulators.
    """
    if not 0.0 <= contamination <= 1.0:
        raise ValueError("contamination must be in [0, 1]")

    lower, upper, hit_increment, clean_increment = sprt_constants(policy)

    # Active (not-yet-stopped) state mass: (samples, failures) -> probability.
    active: dict[tuple[int, int], float] = {(0, 0): 1.0}

    accept_probability = 0.0
    reject_probability = 0.0
    inconclusive_probability = 0.0
    expected_samples = 0.0
    expected_batches = 0.0

    def record_stop(samples: int, mass: float) -> None:
        """Account a stopped trajectory of length ``samples`` with weight."""
        nonlocal expected_samples, expected_batches
        expected_samples += samples * mass
        # E[ceil(T/batch)] comes straight from the stopping distribution —
        # NOT from ceil(E[T]/batch). This is why we DP over stopping times.
        expected_batches += math.ceil(samples / policy.batch_size) * mass

    for _ in range(policy.max_samples):
        next_active: dict[tuple[int, int], float] = defaultdict(float)

        for (samples, failures), state_mass in active.items():
            # Bernoulli transition: clean (outcome 0) vs anomaly (outcome 1).
            transitions = (
                (0, 1.0 - contamination),
                (1, contamination),
            )
            for outcome, outcome_probability in transitions:
                mass = state_mass * outcome_probability
                if mass == 0.0:
                    continue

                new_samples = samples + 1
                new_failures = failures + outcome
                llr = state_llr(
                    new_samples, new_failures, hit_increment, clean_increment
                )

                if llr <= lower:
                    accept_probability += mass
                    record_stop(new_samples, mass)
                elif llr >= upper:
                    reject_probability += mass
                    record_stop(new_samples, mass)
                elif new_samples == policy.max_samples:
                    # Reached the truncation budget without a decision.
                    inconclusive_probability += mass
                    record_stop(new_samples, mass)
                else:
                    next_active[(new_samples, new_failures)] += mass

        active = next_active
        if not active:
            break

    # Any residual mass is, by construction, the inconclusive outcome.
    inconclusive_probability += sum(active.values())

    total = (
        accept_probability + reject_probability + inconclusive_probability
    )
    if abs(total - 1.0) >= 1e-12:
        raise ArithmeticError(f"Probability conservation failed: {total}")

    return OperatingPoint(
        contamination=contamination,
        accept_probability=accept_probability,
        reject_probability=reject_probability,
        inconclusive_probability=inconclusive_probability,
        expected_samples=expected_samples,
        expected_batches=expected_batches,
    )
