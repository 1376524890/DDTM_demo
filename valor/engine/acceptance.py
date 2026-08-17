"""五场景验收组（P12，交接文档第二十节）。

    C0 Normal Trade                  → TRADE（论文完整 MNIST 交易示例）
    C1 Economically infeasible       → NO_TRADE
    C2 Seller data/version tamper    → SELLER_BREACH
    C3 Buyer misuse after trade      → BUYER_BREACH
    C4 Audit disagreement/offline    → replacement / challenge / NO_QUORUM

只有 C0 作为"论文完整 MNIST 交易示例"；C1–C4 属于 mechanism branch validation，
证明四终态与安全机制确实工作。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from valor.engine.calibration import CalibrationBundle
from valor.engine.orchestrator import OrchestrationResult, run_capstone
from valor.engine.scenario import CapstoneScenario


@dataclass
class AcceptanceResult:
    """一次验收场景的结果。"""

    scenario_id: str
    expected_terminal: str
    terminal: str
    decision: str
    passed: bool
    detail: str = ""
    run_id: str = ""

    def to_plain(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "expected_terminal": self.expected_terminal,
            "terminal": self.terminal,
            "decision": self.decision,
            "passed": self.passed,
            "detail": self.detail,
            "run_id": self.run_id,
        }


def _base_scenario(scenario_id: str) -> CapstoneScenario:
    """构造一个轻量 MNIST 场景（供验收快速运行）。"""
    sc = CapstoneScenario(scenario_id=scenario_id, seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    return sc


def scenario_c1_no_trade() -> CapstoneScenario:
    """经济不可行 → NO_TRADE（提高卖方保留效用）。"""
    sc = _base_scenario("C1")
    sc.seller["pi_s0"] = 500.0  # 卖方保留效用极高 → P_min > P_max
    return sc


def scenario_c2_seller_breach() -> CapstoneScenario:
    """卖方数据/版本篡改 → SELLER_BREACH。"""
    sc = _base_scenario("C2")
    sc.seller_breach = True
    return sc


def scenario_c3_buyer_misuse() -> CapstoneScenario:
    """买方交易后违规使用 → BUYER_BREACH。

    P0-K：buyer breach 由真实 misuse 注入派生（重复未经授权用途/越权），
    Mechanism 观察 UsageViolationEvidence 后产生 BUYER_BREACH（不读标准答案）。
    """
    sc = _base_scenario("C3")
    sc.buyer_misuse = True
    # 重复越权用途请求 → BuyerBreachResolver 判定 breach（repeated_threshold=3）
    sc.usage_requests = [
        {"actor": "buyer_org_A", "purpose": "marketing",
         "environment": "approved_compute", "timestamp": "2026-03-01T00:00:00Z",
         "action": "compute", "expect": "DENY"},
        {"actor": "buyer_org_A", "purpose": "marketing",
         "environment": "approved_compute", "timestamp": "2026-03-02T00:00:00Z",
         "action": "compute", "expect": "DENY"},
        {"actor": "buyer_org_A", "purpose": "marketing",
         "environment": "approved_compute", "timestamp": "2026-03-03T00:00:00Z",
         "action": "compute", "expect": "DENY"},
    ]
    return sc


def scenario_c4_audit_disagreement() -> CapstoneScenario:
    """审计结果分散/离线 → replacement/challenge/NO_QUORUM。"""
    sc = _base_scenario("C4")
    sc.audit["n_nodes"] = 8
    sc.audit["f"] = 2
    return sc


def scenario_c0_normal() -> CapstoneScenario:
    """正常交易 → TRADE。"""
    sc = _base_scenario("C0")
    return sc


def run_acceptance(
    *,
    run_dir: str | Path = "runs/acceptance",
    calibration: CalibrationBundle | None = None,
) -> list[AcceptanceResult]:
    """运行 C0–C4 五场景验收，返回结果列表。"""
    scenarios = [
        ("C0", "TRADE", scenario_c0_normal()),
        ("C1", "NO_TRADE", scenario_c1_no_trade()),
        ("C2", "SELLER_BREACH", scenario_c2_seller_breach()),
        ("C3", "BUYER_BREACH", scenario_c3_buyer_misuse()),
        ("C4", "TRADE", scenario_c4_audit_disagreement()),
    ]
    out: list[AcceptanceResult] = []
    for sid, expected, sc in scenarios:
        res = run_capstone(sc, run_dir=run_dir, calibration=calibration)
        # 注意：C0/C4 可能因参数变成 NO_TRADE；C1 期望 NO_TRADE
        actual_terminal = res.terminal_state
        passed = actual_terminal == expected
        detail = ("" if passed else
                  f"期望 {expected}，实际 {actual_terminal}（decision={res.decision}）")
        out.append(AcceptanceResult(
            scenario_id=sid, expected_terminal=expected, terminal=actual_terminal,
            decision=res.decision, passed=passed, detail=detail,
            run_id=res.run_id,
        ))
    return out


def acceptance_all_pass(results: list[AcceptanceResult]) -> bool:
    return all(r.passed for r in results)


__all__ = [
    "AcceptanceResult", "run_acceptance", "acceptance_all_pass",
    "scenario_c0_normal", "scenario_c1_no_trade", "scenario_c2_seller_breach",
    "scenario_c3_buyer_misuse", "scenario_c4_audit_disagreement",
]
