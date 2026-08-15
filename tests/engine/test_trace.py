"""P0 TraceLedger hash-chain 测试。"""

from __future__ import annotations

from valor.engine.trace import TraceLedger


def _ledger():
    return TraceLedger(
        run_id="run-1", tx_id="tx-1",
        config_hash="c" * 64, dataset_hash="d" * 64, seed=7,
    )


def test_append_and_verify():
    l = _ledger()
    l.append(stage="DATA_VOI", event_type="VALUATION", formula_id="F1",
             formula_inputs={"x": 1}, formula_output={"u": 5.0})
    l.append(stage="AUDIT_VOI", event_type="DECISION", formula_id="F2",
             formula_output={"a": 2}, evidence_refs=["1"])
    ok, bad = l.verify()
    assert ok and bad is None
    assert len(l.events) == 2
    assert l.events[1].prev_event_hash == l.events[0].event_hash


def test_chain_broken_detected():
    l = _ledger()
    l.append(stage="S1", event_type="E1", formula_output={"a": 1})
    l.append(stage="S2", event_type="E2", formula_output={"a": 2})
    # 篡改第一条输出 → 链断裂
    l._events[0].formula_output["a"] = 999
    ok, bad = l.verify()
    assert not ok and bad == 1


def test_roundtrip_jsonl():
    l = _ledger()
    l.append(stage="S1", event_type="E1", formula_output={"a": 1})
    l.append(stage="S2", event_type="E2", formula_output={"a": 2})
    plain = l.to_plain()
    l2 = _ledger().load(plain)
    ok, _ = l2.verify()
    assert ok
    assert l2.to_plain() == plain
