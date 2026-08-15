"""P9 Rights/Usage/Lineage 全流程接入测试。"""

from __future__ import annotations

import json

from valor.engine import CapstoneScenario, run_capstone


def test_usage_enforcement_and_lineage(tmp_path):
    """TRADE 后执行使用请求：前 3 次 ALLOW，第 4 次超上限 DENY；lineage 链有效。"""
    sc = CapstoneScenario(scenario_id="usage-1", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    sc.rights["q"] = 3  # max 3 uses
    res = run_capstone(sc, run_dir=str(tmp_path))
    assert res.decision == "TRADE"
    run_dir = tmp_path / res.run_id
    # lineage artifact 存在
    assert (run_dir / "lineage.jsonl").exists()
    report = json.loads((run_dir / "report.json").read_text())
    usage = report["stages"]["usage"]["output"]
    assert usage["enabled"] is True
    assert usage["chain_valid"] is True
    decisions = [r["decision"] for r in usage["results"]]
    # 3 次正确用途 ALLOW，之后超限/错误主体/错误用途 DENY
    assert decisions[:3] == ["ALLOW", "ALLOW", "ALLOW"]
    assert "DENY" in decisions[3:]
    # 每个请求的 decision 与预期一致
    for r in usage["results"]:
        assert r["decision"] == r["expected"]


def test_usage_disabled_when_no_trade(tmp_path):
    """NO_TRADE 场景不启用使用控制。"""
    sc = CapstoneScenario(scenario_id="usage-2", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    sc.buyer["w_b_rem"] = 1.0  # 极小预算 → 可能 NO_TRADE
    res = run_capstone(sc, run_dir=str(tmp_path))
    report = json.loads((tmp_path / res.run_id / "report.json").read_text())
    usage = report["stages"]["usage"]["output"]
    assert usage["enabled"] is False or res.decision == "TRADE"
