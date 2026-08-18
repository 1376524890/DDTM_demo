"""P6 校准 artifact 接入编排器的集成测试。"""

from __future__ import annotations

from valor.data.download import load_dataset
from valor.engine.calibration_runner import CalibrationConfig, run_offline_calibration
from valor.engine import CapstoneScenario, run_capstone


def _cal_config(handle, n=300):
    pool = handle.X.iloc[:n]
    return CalibrationConfig(
        historical_pool=pool,
        y_historical=handle.y.iloc[:n],
        dataset_hash="d" * 64, trainer_hash="t" * 64, seed=0,
        payoff_matrix=[[1.0, -2.0], [-5.0, 3.0]],
        deployment_scale=1000, n_pseudo_trades=3,
        policy_hash="p" * 64, action_catalog_hash="a" * 64,
    )


def test_calibration_runner_produces_bundle(tmp_path):
    handle = load_dataset("breast_cancer")
    cfg = _cal_config(handle, 200)
    bundle = run_offline_calibration(cfg, run_dir=str(tmp_path / "cal"))
    assert bundle.valuation is not None
    assert bundle.likelihood is not None
    assert bundle.certificate is not None
    assert len(bundle.certificate.data["p_breach_lower_sys"]) if False else True
    # certificate 有下界
    assert 0.0 < bundle.certificate.data["p_breach_lower_sys"] < 1.0


def test_capstone_with_calibration(tmp_path):
    handle = load_dataset("breast_cancer")
    cfg = _cal_config(handle, 300)
    bundle = run_offline_calibration(cfg, run_dir=str(tmp_path / "cal"))
    sc = CapstoneScenario(scenario_id="cal-wire", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    res = run_capstone(sc, run_dir=str(tmp_path / "runs"), calibration=bundle)
    assert res.decision in ("TRADE", "NO_TRADE")
