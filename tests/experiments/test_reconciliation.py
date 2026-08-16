"""Level 1 数学对账测试（experiments/reconciliation.py）。"""

from __future__ import annotations

from valor.experiments.reconciliation import level1_reconciliation


def test_level1_reconciliation_all_pass():
    results = level1_reconciliation()
    assert len(results) >= 4
    assert all(r["passed"] for r in results), [
        r["name"] for r in results if not r["passed"]]
