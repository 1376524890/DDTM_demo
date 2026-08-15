"""P0 RunArtifacts / StageResult / FormulaTrace 测试。"""

from __future__ import annotations

from valor.engine.artifacts import RunArtifacts
from valor.engine.stage import FormulaTrace, StageResult


def test_artifacts_dir(tmp_path):
    a = RunArtifacts(tmp_path / "runs" / "run-x", run_id="run-x")
    a.write_manifest({"run_id": "run-x"})
    a.write_trace([{"seq": 1}])
    a.write_formula_trace([{"formula_id": "F1"}])
    a.write_money_ledger([{"from": "seller", "to": "auditor"}])
    a.write_state_trace([{"state": "TRADE"}])
    a.write_report({"decision": "TRADE"}, "# report")
    for f in ["manifest.json", "transaction_trace.jsonl",
              "formula_trace.jsonl", "money_ledger.jsonl",
              "state_trace.jsonl", "report.json", "report.md"]:
        assert (a.root / f).exists(), f


def test_stage_result_downstream_reads_output():
    s = StageResult(stage="DATA_VOI", output={"v_gross_lower": 42.0})
    assert s.get("v_gross_lower") == 42.0
    assert s.get("missing", 0) == 0


def test_formula_trace_reconcile():
    def recompute(inp):
        return inp["x"] + inp["y"], 1e-6

    ft = FormulaTrace("SUM", {"x": 1, "y": 2}, computed=3.0)
    ft.recompute_fn = recompute
    ft.reconcile()
    assert ft.passed is True

    ft2 = FormulaTrace("SUM", {"x": 1, "y": 2}, computed=99.0)
    ft2.recompute_fn = recompute
    ft2.reconcile()
    assert ft2.passed is False
