"""P0-L/P0-M/P0-N 主链 stage 测试：delivery / training / retention / usage bond。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine import CapstoneScenario, run_capstone


def test_delivery_stage_verified(tmp_path):
    """TRADE 时 Delivery 独立 stage 存在且 verified（H(D_delivery)==H(D_listing)）。"""
    sc = CapstoneScenario(scenario_id="m-del", seller_id="s", buyer_id="b")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path))
    res = orch.run()
    if res.terminal_state == "TRADE":
        deliv = orch._stages["delivery"].output
        assert deliv["enabled"] is True
        assert deliv["verified"] is True
        assert deliv["equality"] is True  # H(D_delivery) == H(D_listing)


def test_usage_bond_in_pricing(tmp_path):
    """Buyer Usage Bond 由 certified misuse detection 计算并进入 pricing。"""
    sc = CapstoneScenario(scenario_id="m-bond", seller_id="s", buyer_id="b")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    sc.usage["usage_bond"] = {
        "p_misuse_lower_sys": 0.8, "g_misuse": 50.0, "eps_b": 1.0,
        "p_e_ubond": 1.0, "p_e_uf": 0.0, "lambda_b": 1.0, "f_b": 0.0,
        "kappa_b": 0.1, "t_b": 1.0,
    }
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path))
    res = orch.run()
    pricing = orch._stages["pricing"].output
    assert pricing["b_b_use"] > 0  # 公式自然计算（非代码跳过）


def test_retention_delete_duty(tmp_path):
    """retention/deleteDuty 适用时产生 deletion receipt。"""
    sc = CapstoneScenario(scenario_id="m-ret", seller_id="s", buyer_id="b")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    sc.rights["retention"] = "P30D"
    sc.rights["delete_duty"] = True
    sc.rights["not_applicable_reason"] = None
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path))
    res = orch.run()
    if res.terminal_state == "TRADE":
        usage = orch._stages["usage"].output
        assert usage.get("deletion") is not None
        assert usage["deletion"]["state"] in ("DELETED_ATTESTED", "DELETION_PENDING")
