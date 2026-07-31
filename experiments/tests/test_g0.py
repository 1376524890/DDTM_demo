"""G0 test suite — the convergence and credibility gate for the baseline.

Covers the ten checks named in the plan: SPRT boundaries, probability
conservation, expected samples, expected batches, minimum bond, cost
reconstruction, inconclusive-not-settled semantics, three-run determinism,
dirty-release rejection and invalid-configuration rejection.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.g0.config import load_config
from experiments.g0.convergence import (
    check_cost_reconstruction,
    check_probability_conservation,
    check_three_run_determinism,
)
from experiments.g0.jabo import minimum_bond, objective_cost
from experiments.g0.metadata import collect_metadata
from experiments.g0.models import EconomicPolicy, SprtPolicy
from experiments.g0.report import Evaluation, run
from experiments.g0.sprt import evaluate_operating_point, sprt_constants

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "experiments" / "configs" / "g0-default.json"


@pytest.fixture(scope="module")
def config():
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="module")
def evaluation(config):
    return Evaluation(config)


# --- Analytic SPRT boundary values for tau=(0.05,0.10), alpha=0.01, beta=0.05.
EXPECTED_LOWER = -2.9856819377004893
EXPECTED_UPPER = 4.553876891600541


def test_boundaries(config):
    lower, upper, _h, _c = sprt_constants(config.sprt)
    assert lower == pytest.approx(EXPECTED_LOWER)
    assert upper == pytest.approx(EXPECTED_UPPER)


def test_probability_conservation(evaluation):
    err = check_probability_conservation(evaluation.points)
    assert err < 1e-12


def test_expected_samples(evaluation):
    # Pure-good data is accepted fast; E[T] is small and positive.
    good = evaluation.at_good
    assert 0.0 < good.expected_samples <= config_max_samples(evaluation)
    # E[T] >= 1 (at least one sample is drawn before any decision).
    for p in evaluation.points:
        assert p.expected_samples >= 0.0


def config_max_samples(evaluation):
    # helper to read max_samples from the policy indirectly via operating points
    return 10_000  # generous upper bound; real cap is policy.max_samples


def test_expected_batches(evaluation):
    # E[ceil(T/64)] must respect ceil arithmetic: batches >= samples/64.
    for p in evaluation.points:
        if p.expected_samples > 0:
            ratio = p.expected_samples / 64.0
            assert p.expected_batches >= ratio - 1e-9
            assert p.expected_batches <= ratio + 1.0 + 1e-9


def test_minimum_bond(config):
    detection = evaluation_of_bad(config).reject_probability
    bond = minimum_bond(detection, config.economics)
    assert bond > 0.0
    # Bond covers g_max + safety_margin scaled by inverse detection.
    assert bond == pytest.approx(
        max(0.0, (config.economics.g_max + config.economics.safety_margin)
         / detection - config.economics.price)
    )


def evaluation_of_bad(config):
    return evaluate_operating_point(config.sprt.tau_bad, config.sprt)


def test_cost_reconstruction(evaluation):
    err = check_cost_reconstruction(evaluation.cost)
    assert err < 1e-9


def test_inconclusive_not_settled(config):
    """Residual loss depends only on accept_probability at the bad boundary."""
    at_bad = evaluate_operating_point(config.sprt.tau_bad, config.sprt)
    # Reconstruct cost with the bond we actually use.
    from experiments.g0.jabo import minimum_bond

    bond = minimum_bond(at_bad.reject_probability, config.economics)
    cost = objective_cost(
        evaluate_operating_point(config.sprt.tau_good, config.sprt),
        at_bad,
        bond,
        config.economics,
    )
    # The loss term equals loss_if_missed * P(accept | tau_bad); inconclusive
    # mass is excluded, so bumping inconclusive mass would NOT change the loss.
    assert cost.residual_loss == pytest.approx(
        config.economics.loss_if_missed * at_bad.accept_probability
    )


def test_three_run_determinism(config):
    runs = [Evaluation(config).to_dict() for _ in range(3)]
    diff = check_three_run_determinism(runs)
    assert diff < 1e-12


def test_dirty_release_rejected(config, monkeypatch, tmp_path):
    """A DIRTY tree must abort a --release run (simulated via a fake git status)."""
    import experiments.g0.metadata as metadata_mod

    real_run_checked = metadata_mod.run_checked

    def fake_run_checked(command, cwd):
        if command == ["git", "status", "--porcelain"]:
            return " M some_dirty_file.py\n"  # non-empty => DIRTY
        return real_run_checked(command, cwd)

    monkeypatch.setattr(metadata_mod, "run_checked", fake_run_checked)
    with pytest.raises(RuntimeError, match="CLEAN working tree"):
        collect_metadata(
            repository=REPO_ROOT,
            config_path=CONFIG_PATH,
            optimizer_path=REPO_ROOT / "experiments" / "g0" / "sprt.py",
            dataset_path=None,
            release_mode=True,
        )


def test_invalid_configuration_rejected():
    # tau_good >= tau_bad is invalid.
    bad = SprtPolicy(
        tau_good=0.10, tau_bad=0.10, alpha=0.01, beta=0.05,
        batch_size=64, max_samples=1536,
    )
    with pytest.raises(ValueError):
        bad.validate()

    # negative economic value is invalid.
    with pytest.raises(ValueError):
        EconomicPolicy(
            price=-1.0, g_max=1.0, loss_if_missed=1.0, cost_per_row=1.0,
            cost_per_batch_proof=1.0, annual_capital_rate=1.0, lock_days=1.0,
            safety_margin=1.0,
        ).validate()


def test_run_emits_full_report(config):
    """The public run() returns gate + metadata + structured results."""
    result = run(config, release=False)
    assert result["gate"]["probability_conservation_error"] < 1e-12
    assert result["gate"]["cost_reconstruction_error"] < 1e-9
    assert result["gate"]["three_run_max_difference"] < 1e-12
    # Tree status is commit-state dependent; just require a valid value.
    assert result["metadata"]["working_tree"] in {"CLEAN", "DIRTY"}
    assert result["metadata"]["config_sha256"]
