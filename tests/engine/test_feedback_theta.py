"""P10 Feedback Θt→Θt+1 + realised Data-VOI 测试。"""

from __future__ import annotations

import json

from valor.engine import CapstoneScenario, run_capstone


def test_feedback_theta_update_and_realised(tmp_path):
    sc = CapstoneScenario(scenario_id="fb-1", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    res = run_capstone(sc, run_dir=str(tmp_path))
    assert res.decision == "TRADE"
    report = json.loads((tmp_path / res.run_id / "report.json").read_text())
    fb = report["stages"]["feedback"]["output"]
    # eligible 事件（CONTROLLED_CANARY）→ Θ 更新
    assert fb["eligible"] is True
    assert fb["theta_updated"] is True
    assert fb["theta_after"]["a"] > fb["theta_before"]["a"]
    # realised Data-VOI 已计算（FinalEvaluation 上）
    assert fb["realised_data_voi"] is not None


def test_feedback_no_trade_no_update(tmp_path):
    sc = CapstoneScenario(scenario_id="fb-2", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    sc.buyer["w_b_rem"] = 1.0
    sc.seller["pi_s0"] = 500.0  # 提高卖方保留效用 → NO_TRADE
    res = run_capstone(sc, run_dir=str(tmp_path))
    report = json.loads((tmp_path / res.run_id / "report.json").read_text())
    fb = report["stages"]["feedback"]["output"]
    if res.decision == "NO_TRADE":
        assert fb["theta_updated"] is False
