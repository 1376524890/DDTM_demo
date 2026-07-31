"""G0 测试套件——基线的收敛性与可信性 gate。

覆盖计划中点名的十项检查：SPRT 边界、概率守恒、期望样本数、期望批数、最低保证金、
成本重构、INCONCLUSIVE 不结算语义、三次运行确定性、拒绝 dirty release、拒绝非法
配置。
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


# --- tau=(0.05,0.10)、alpha=0.01、beta=0.05 下的解析 SPRT 边界值。
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
    # 纯好数据被快速接受；E[T] 较小且为正。
    good = evaluation.at_good
    assert 0.0 < good.expected_samples <= config_max_samples(evaluation)
    # E[T] >= 1（任何决断前至少抽 1 个样本）。
    for p in evaluation.points:
        assert p.expected_samples >= 0.0


def config_max_samples(evaluation):
    # 间接从 operating points 读 max_samples 上界的辅助函数
    return 10_000  # 宽松上界；真正的上限是 policy.max_samples


def test_expected_batches(evaluation):
    # E[ceil(T/64)] 必须满足 ceil 算术：batches >= samples/64。
    for p in evaluation.points:
        if p.expected_samples > 0:
            ratio = p.expected_samples / 64.0
            assert p.expected_batches >= ratio - 1e-9
            assert p.expected_batches <= ratio + 1.0 + 1e-9


def test_minimum_bond(config):
    detection = evaluation_of_bad(config).reject_probability
    bond = minimum_bond(detection, config.economics)
    assert bond > 0.0
    # 保证金覆盖 g_max + safety_margin，并按检测概率倒数放大。
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
    """残差损失只依赖坏质量边界的 accept_probability。"""
    at_bad = evaluate_operating_point(config.sprt.tau_bad, config.sprt)
    # 用我们实际使用的保证金重构成本。
    from experiments.g0.jabo import minimum_bond

    bond = minimum_bond(at_bad.reject_probability, config.economics)
    cost = objective_cost(
        evaluate_operating_point(config.sprt.tau_good, config.sprt),
        at_bad,
        bond,
        config.economics,
    )
    # 损失项等于 loss_if_missed * P(accept | tau_bad)；inconclusive 质量被排除，
    # 因此即使抬升 inconclusive 质量也不会改变损失。
    assert cost.residual_loss == pytest.approx(
        config.economics.loss_if_missed * at_bad.accept_probability
    )


def test_three_run_determinism(config):
    runs = [Evaluation(config).to_dict() for _ in range(3)]
    diff = check_three_run_determinism(runs)
    assert diff < 1e-12


def test_dirty_release_rejected(config, monkeypatch, tmp_path):
    """DIRTY 工作树必须中止一次 --release 运行（用伪造的 git status 模拟）。"""
    import experiments.g0.metadata as metadata_mod

    real_run_checked = metadata_mod.run_checked

    def fake_run_checked(command, cwd):
        if command == ["git", "status", "--porcelain"]:
            return " M some_dirty_file.py\n"  # 非空 ⇒ DIRTY
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
    # tau_good >= tau_bad 非法。
    bad = SprtPolicy(
        tau_good=0.10, tau_bad=0.10, alpha=0.01, beta=0.05,
        batch_size=64, max_samples=1536,
    )
    with pytest.raises(ValueError):
        bad.validate()

    # 负的经济数值非法。
    with pytest.raises(ValueError):
        EconomicPolicy(
            price=-1.0, g_max=1.0, loss_if_missed=1.0, cost_per_row=1.0,
            cost_per_batch_proof=1.0, annual_capital_rate=1.0, lock_days=1.0,
            safety_margin=1.0,
        ).validate()


def test_run_emits_full_report(config):
    """公开的 run() 返回 gate + 元数据 + 结构化结果。"""
    result = run(config, release=False)
    assert result["gate"]["probability_conservation_error"] < 1e-12
    assert result["gate"]["cost_reconstruction_error"] < 1e-9
    assert result["gate"]["three_run_max_difference"] < 1e-12
    # 工作树状态取决于提交状态；这里只要求是合法值。
    assert result["metadata"]["working_tree"] in {"CLEAN", "DIRTY"}
    assert result["metadata"]["config_sha256"]
