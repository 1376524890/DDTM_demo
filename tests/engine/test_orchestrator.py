"""P3 TransactionOrchestrator 测试（小规模 MNIST 快速跑通）。"""

from __future__ import annotations

import json

from valor.engine import CapstoneScenario, run_capstone


def _scenario(tmp_path, **over):
    sc = CapstoneScenario(
        scenario_id="test-1", seller_id="seller-1", buyer_id="buyer-1",
    )
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 5000
    sc.audit["cost"] = 2.0
    sc.role_fracs = {"historical": 0.2, "buyer_base": 0.2,
                     "seller_candidate": 0.05, "transaction_eval": 0.10}
    return sc


def test_run_capstone_produces_result(tmp_path):
    sc = _scenario(tmp_path)
    res = run_capstone(sc, run_dir=str(tmp_path))
    assert res.decision in ("TRADE", "NO_TRADE")
    assert res.terminal_state in ("TRADE", "NO_TRADE")
    assert res.run_id


def test_run_capstone_writes_artifacts(tmp_path):
    sc = _scenario(tmp_path)
    res = run_capstone(sc, run_dir=str(tmp_path))
    run_dir = tmp_path / res.run_id
    for f in ["manifest.json", "transaction_trace.jsonl", "scenario.json",
              "formula_trace.jsonl", "state_trace.jsonl", "report.json"]:
        assert (run_dir / f).exists(), f


def test_run_capstone_trace_chain_valid(tmp_path):
    sc = _scenario(tmp_path)
    res = run_capstone(sc, run_dir=str(tmp_path))
    run_dir = tmp_path / res.run_id
    rows = [json.loads(l) for l in
            (run_dir / "transaction_trace.jsonl").read_text().strip().splitlines()]
    assert len(rows) > 5
    prev = None
    for r in rows:
        assert r["prev_event_hash"] == prev
        prev = r["event_hash"]
