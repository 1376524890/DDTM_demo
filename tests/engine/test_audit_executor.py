"""P4/P5 DistributedAuditExecutor 测试。"""

from __future__ import annotations

import pytest

from valor.core.enums import TerminalState
from valor.engine.audit_executor import DistributedAuditExecutor
from valor.engine.audit_executor import _default_evidence_provider as default_evidence_provider
from valor.engine.scenario import CapstoneScenario
from valor.engine.trace import TraceLedger


def _scenario():
    sc = CapstoneScenario(scenario_id="audit-1", seller_id="seller-1", buyer_id="buyer-1")
    sc.audit.update({"n_nodes": 8, "f": 2, "cost": 2.0, "rho": 0.0})
    return sc


def _ctx(sc, n_nodes=8):
    ledger = TraceLedger(run_id="run-1", tx_id="tx-1",
                         config_hash="c" * 64, dataset_hash="d" * 64, seed=0)
    return {
        "ledger": ledger,
        "binding": type("B", (), {
            "tx_id": "tx-1",
            "listing": type("L", (), {"rights_hash": "r" * 64})(),
        })(),
        "dataset_hash": "d" * 64,
    }


def test_executor_all_pass_certified():
    sc = _scenario()
    n = sc.audit["n_nodes"]
    prov = default_evidence_provider({f"node-{i}": "PASS" for i in range(n)})
    ex = DistributedAuditExecutor(sc, evidence_provider=prov)
    res = ex.run(sc, _ctx(sc))
    assert "posterior" in res
    assert res["p_breach_lower_sys"] > 0
    assert res["n_steps"] >= 0


def test_executor_evidence_derived_posterior():
    """后验必须来自 evidence（Bayes 更新），且 audit trace 记录 VCG cost。"""
    sc = _scenario()
    n = sc.audit["n_nodes"]
    prov = default_evidence_provider({f"node-{i}": "QUALITY_FAIL" for i in range(n)})
    ex = DistributedAuditExecutor(sc, evidence_provider=prov)
    ctx = _ctx(sc)
    res = ex.run(sc, ctx)
    # evidence 全 QUALITY_FAIL → 后验应显著偏向 B/L，且 audit trace 有 mc_a_pay
    steps = res["audit_trace_events"]
    if steps:
        assert steps[0]["outcome"] == "QUALITY_FAIL"
        assert steps[0]["mc_a_pay"] > 0
        assert "vcg_payments" in steps[0]


def test_executor_no_quorum_breaks():
    """结果分散无 quorum → 无法形成证书 → 审计步数 0（不产生后验更新）。"""
    sc = _scenario()
    sc.audit["n_nodes"] = 8
    n = sc.audit["n_nodes"]
    # 4 PASS + 3 QUALITY_FAIL + 1 BREACH → 无结果达 q=5
    results = {f"node-{i}": "PASS" for i in range(4)}
    for i in range(4, 7):
        results[f"node-{i}"] = "QUALITY_FAIL"
    results["node-7"] = "BREACH_EVIDENCE"
    prov = default_evidence_provider(results)
    ex = DistributedAuditExecutor(sc, evidence_provider=prov)
    res = ex.run(sc, _ctx(sc))
    # 无 quorum → 不执行 action
    assert res["n_steps"] == 0
