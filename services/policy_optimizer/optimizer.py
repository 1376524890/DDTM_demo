#!/usr/bin/env python3
"""JABO policy optimizer.

The program evaluates a truncated Wald SPRT exactly by dynamic programming.
It reports acceptance/rejection/inconclusive probabilities, expected samples,
and the minimum seller bond required by the incentive constraint.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


@dataclass(frozen=True)
class Policy:
    tau_good: float
    tau_bad: float
    alpha: float
    beta: float
    batch_size: int
    max_samples: int

    @property
    def upper(self) -> float:
        return math.log((1.0 - self.beta) / self.alpha)

    @property
    def lower(self) -> float:
        return math.log(self.beta / (1.0 - self.alpha))

    @property
    def hit_increment(self) -> float:
        return math.log(self.tau_bad / self.tau_good)

    @property
    def clean_increment(self) -> float:
        return math.log((1.0 - self.tau_bad) / (1.0 - self.tau_good))


@dataclass
class OperatingPoint:
    contamination: float
    accept_probability: float
    reject_probability: float
    inconclusive_probability: float
    expected_samples: float
    expected_batches: float


def _llr(policy: Policy, n: int, failures: int) -> float:
    return failures * policy.hit_increment + (n - failures) * policy.clean_increment


def evaluate_policy(policy: Policy, contamination: float) -> OperatingPoint:
    if not (0.0 <= contamination <= 1.0):
        raise ValueError("contamination must be in [0,1]")

    # State mass after n observations, indexed by failure count.
    active: Dict[int, float] = {0: 1.0}
    accept = reject = 0.0
    expected_stop = 0.0
    expected_batches = 0.0

    for n in range(0, policy.max_samples):
        nxt: Dict[int, float] = {}
        for failures, mass in active.items():
            for is_failure, probability in ((0, 1.0 - contamination), (1, contamination)):
                f2 = failures + is_failure
                n2 = n + 1
                m2 = mass * probability
                value = _llr(policy, n2, f2)
                if value <= policy.lower:
                    accept += m2
                    expected_stop += n2 * m2
                    expected_batches += math.ceil(n2 / policy.batch_size) * m2
                elif value >= policy.upper:
                    reject += m2
                    expected_stop += n2 * m2
                    expected_batches += math.ceil(n2 / policy.batch_size) * m2
                else:
                    nxt[f2] = nxt.get(f2, 0.0) + m2
        active = nxt
        if not active:
            break

    inconclusive = sum(active.values())
    expected_stop += policy.max_samples * inconclusive
    expected_batches += math.ceil(policy.max_samples / policy.batch_size) * inconclusive
    total = accept + reject + inconclusive
    if abs(total - 1.0) > 1e-9:
        raise RuntimeError(f"probability mass error: {total}")

    return OperatingPoint(
        contamination=contamination,
        accept_probability=accept,
        reject_probability=reject,
        inconclusive_probability=inconclusive,
        expected_samples=expected_stop,
        expected_batches=expected_batches,
    )


def minimum_bond(price: float, g_max: float, safety_margin: float, detection_probability: float) -> float:
    if detection_probability <= 0.0:
        return math.inf
    return max(0.0, (g_max + safety_margin) / detection_probability - price)


def total_cost(config: dict, op_good: OperatingPoint, op_bad: OperatingPoint, bond: float) -> dict:
    row_audit_cost = config["cost_per_row"] * op_good.expected_samples
    proof_batch_cost = config["cost_per_batch_proof"] * op_good.expected_batches
    audit_cost = row_audit_cost + proof_batch_cost
    capital_cost = (
        config["annual_capital_rate"] * bond * config["lock_days"] / 365.0
    )
    residual_loss = config["loss_if_missed"] * op_bad.accept_probability
    return {
        "row_audit_cost": row_audit_cost,
        "proof_batch_cost": proof_batch_cost,
        "audit_cost": audit_cost,
        "bond_capital_cost": capital_cost,
        "residual_loss": residual_loss,
        "objective_cost": audit_cost + capital_cost + residual_loss,
    }


def run(config: dict) -> dict:
    policy = Policy(
        tau_good=config["tau_good"],
        tau_bad=config["tau_bad"],
        alpha=config["alpha"],
        beta=config["beta"],
        batch_size=config["batch_size"],
        max_samples=config["max_samples"],
    )
    points = [evaluate_policy(policy, x) for x in config["evaluation_grid"]]
    at_good = evaluate_policy(policy, policy.tau_good)
    at_bad = evaluate_policy(policy, policy.tau_bad)
    detection = at_bad.reject_probability
    bond = minimum_bond(
        config["price"], config["g_max"], config["safety_margin"], detection
    )
    cost = total_cost(config, at_good, at_bad, bond)
    return {
        "policy": policy.__dict__,
        "sprt_boundaries": {"lower": policy.lower, "upper": policy.upper},
        "minimum_bond": bond,
        "bad_quality_detection_probability": detection,
        "cost_breakdown": cost,
        "operating_points": [p.__dict__ for p in points],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = run(config)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
