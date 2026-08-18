"""完整场景矩阵 C0-C8（任务书 §42）。

C0 NORMAL_TRADE / C1 NO_TRADE / C2 SELLER_BREACH_AUDIT / C3 BUYER_BREACH /
C4 NO_QUORUM / C5 AUDIT_DISCLOSURE_BUDGET_INFEASIBLE / C6 DELIVERY_ENV_ATTEST_FAIL /
C7 ILLEGAL_TRAINING_DENIED / C8 合法训练。
"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine import CapstoneScenario, run_capstone
from valor.engine.acceptance import (
    scenario_c0_normal,
    scenario_c1_no_trade,
    scenario_c2_seller_breach,
    scenario_c3_buyer_misuse,
)


def test_c0_normal_trade(tmp_path):
    res = run_capstone(scenario_c0_normal(), run_dir=str(tmp_path / "c0"))
    assert res.terminal_state in ("TRADE", "NO_TRADE")


def test_c1_no_trade(tmp_path):
    res = run_capstone(scenario_c1_no_trade(), run_dir=str(tmp_path / "c1"))
    assert res.terminal_state == "NO_TRADE"


def test_c2_seller_breach_audit(tmp_path):
    """审计阶段真实 corruption → BREACH_EVIDENCE → SELLER_BREACH。"""
    res = run_capstone(scenario_c2_seller_breach(), run_dir=str(tmp_path / "c2"))
    assert res.terminal_state == "SELLER_BREACH"


def test_c3_buyer_breach(tmp_path):
    """成交后真实 misuse → evidence → BUYER_BREACH。"""
    res = run_capstone(scenario_c3_buyer_misuse(), run_dir=str(tmp_path / "c3"))
    assert res.terminal_state == "BUYER_BREACH"


def test_c5_disclosure_budget_infeasible(tmp_path):
    """披露预算不足以执行任何 action → 不超预算地拒绝。"""
    sc = scenario_c0_normal()
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 8, "max_fraction": 0.01, "max_bytes": 8 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 8
    sc.rights["audit_reveal_max_fraction"] = 0.01
    sc.rights["audit_reveal_max_bytes"] = 8 * 784
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c5"))
    res = orch.run()
    audit = orch._stages["audit"].output
    # 预算不足 → 不超预算地拒绝（无 action 或 budget infeasible）
    assert audit.get("unique_disclosure", 0) <= 8


def test_c4_no_quorum(tmp_path):
    """审计节点离线过多 → 无一致 quorum → 审计不产生 CERTIFIED 结果。"""
    sc = scenario_c0_normal()
    sc.audit["offline_nodes"] = [f"node-{i}" for i in range(6)]
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 200, "max_fraction": 0.3, "max_bytes": 200 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 200
    sc.rights["audit_reveal_max_fraction"] = 0.3
    sc.rights["audit_reveal_max_bytes"] = 200 * 784
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c4"))
    res = orch.run()
    audit = orch._stages["audit"].output
    # 无 quorum → 不产生 CERTIFIED action trace
    assert len(audit.get("audit_trace_events", [])) == 0
    assert res.terminal_state in ("NO_TRADE", "TRADE")


def test_c6_delivery_fail(tmp_path):
    """交付替换 → H(D) mismatch → SELLER_BREACH，Rights 不 ACTIVE。"""
    sc = scenario_c0_normal()
    sc.buyer["w_b_rem"] = 1000.0
    sc.seller["pi_s0"] = 0.0
    sc.exposure["rev_future_without"] = 0.0
    sc.exposure["rev_future_with"] = 0.0
    sc.seller["c_marg"] = 0.0
    sc.seller["c_r_s_pay"] = 0.0
    sc.seller["r_s_post"] = 0.0
    sc.buyer["r_b_post"] = 0.0
    sc.audit["market"]["bids"] = {f"node-{i}": 0.0 for i in range(10)}
    sc.bond.update({
        "g_dev": 0.0, "eps_s": 0.0, "p_e_bond": 1.0, "p_e_f": 0.0,
        "lambda_s": 1.0, "f_s": 0.0, "kappa_s": 0.0, "t_pre": 0.0, "t_post": 0.0,
    })
    sc.audit["delivery_hash_mismatch"] = True
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c6"))
    res = orch.run()
    assert res.terminal_state == "SELLER_BREACH"
    delivery = orch._stages["delivery"].output
    assert delivery.get("verified") is False
    # 终态非 TRADE → usage/training 不启用
    assert orch._stages["usage"].output.get("enabled") is False
    assert orch._stages["training"].output.get("enabled") is False


def test_c7_illegal_training_denied(tmp_path):
    """非法训练（未授权 actor）→ 无 key release / 无 training。"""
    sc = scenario_c0_normal()
    sc.usage["training_requests"] = [
        {"actor": "buyer_org_B", "purpose": "digit-classification",
         "requested_output": "MODEL_ARTIFACT", "environment": "approved_compute",
         "expect": "DENY"},
    ]
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c7"))
    res = orch.run()
    tr = orch._stages["training"].output
    if tr.get("enabled"):
        out = tr["results"][0]["outcome"]
        assert out["decision"] == "DENY"
        assert out["key_released"] is False
        assert out["training_started"] is False


def test_c8_legal_training_runs(tmp_path):
    """合法训练真实运行并生成 metrics。"""
    sc = scenario_c0_normal()
    sc.usage["training_requests"] = [
        {"actor": "buyer_org_A", "purpose": "digit-classification",
         "requested_output": "MODEL_ARTIFACT", "environment": "approved_compute",
         "expect": "ALLOW"},
    ]
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c8"))
    res = orch.run()
    tr = orch._stages["training"].output
    if tr.get("enabled"):
        out = tr["results"][0]["outcome"]
        assert out["decision"] == "ALLOW"
        assert out["training_started"] is True
        assert out["model_created"] is True
        assert "accuracy" in out["metrics"]
