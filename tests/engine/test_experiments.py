"""P13 RQ 实验框架测试（Level 1 对账 + Level 4 统计）。"""

from __future__ import annotations

from valor.engine.experiments import (
    ExperimentRunner,
    level1_reconciliation,
)


def test_level1_reconciliation_all_pass():
    results = level1_reconciliation()
    assert len(results) >= 4
    assert all(r["passed"] for r in results), [
        r["name"] for r in results if not r["passed"]]


def test_level4_runner_and_group(tmp_path):
    def factory(_over):
        from valor.engine import CapstoneScenario

        sc = CapstoneScenario(scenario_id="exp", seller_id="seller-1",
                              buyer_id="buyer-1")
        sc.trainer.update({"epochs": 1, "batch_size": 128})
        sc.buyer_task["deployment_scale"] = 2000
        return sc

    runner = ExperimentRunner(scenario_factory=factory, n_seeds=2,
                              run_dir=str(tmp_path))
    g = runner.run_group("base")
    assert len(g.trials) == 2
    summ = g.summarize("clearing_price")
    assert summ["n"] >= 0
