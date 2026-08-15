"""P11 FullChainGate (G1-G33) 测试。"""

from __future__ import annotations

import json

from valor.engine import CapstoneScenario, run_capstone


def test_full_chain_gate_runs(tmp_path):
    sc = CapstoneScenario(scenario_id="gate-1", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    res = run_capstone(sc, run_dir=str(tmp_path))
    assert res.decision in ("TRADE", "NO_TRADE")
    gate = res.full_chain_gate
    assert "paper_closure_gate" in gate
    assert gate["n_checks"] >= 30  # G1-G33 大部分实现


def test_full_chain_gate_with_calibration(tmp_path):
    """带 calibration 时 G4/G5/G10 应通过（无手工 likelihood/TP-FN）。"""
    from valor.data.download import load_dataset
    from valor.engine.calibration_runner import CalibrationConfig, run_offline_calibration

    handle = load_dataset("breast_cancer")
    cfg = CalibrationConfig(historical_pool=handle.X.iloc[:300],
                            dataset_hash="d" * 64, trainer_hash="t" * 64)
    bundle = run_offline_calibration(cfg, run_dir=str(tmp_path / "cal"))
    sc = CapstoneScenario(scenario_id="gate-2", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    res = run_capstone(sc, run_dir=str(tmp_path / "runs"), calibration=bundle)
    checks = res.full_chain_gate["checks"]
    assert checks["G4_no_manual_likelihood"] is True
    assert checks["G5_no_manual_tp_fn"] is True
    assert checks["G10_independent_value_calibration_used"] is True
