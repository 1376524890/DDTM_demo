"""用途控制 + 数据流向血缘测试（规范 §33–§38）。"""

from __future__ import annotations

import pytest

from valor.execution.download_traceable import DownloadTraceableDelivery
from valor.execution.fingerprint import (
    embed_fingerprint,
    recipient_fingerprint,
    trace_origin,
)
from valor.lineage.hash_chain import HashChain
from valor.lineage.models import DataFlowEvent
from valor.usage.models import UsageRequest, UsageState
from valor.usage.pdp import authorize
from valor.usage.pep import enforce


def _event(i, action="READ"):
    return DataFlowEvent(
        event_id=f"e{i}", tx_id="tx-1", actor="buyer", action=action,
        input_refs=("d1",), output_refs=("o1",), rights_ref="r1",
        purpose="ml", time="2026-01-01T00:00:00Z", env="sandbox", evidence="x",
    )


def test_hash_chain_and_tamper():
    chain = HashChain()
    events = [_event(i) for i in range(5)]
    for e in events:
        chain.append(e)
    assert chain.verify(events)
    # 篡改一个事件 → 校验失败
    tampered = [_event(i) if i != 2 else _event(2, action="EXPORT") for i in range(5)]
    assert not chain.verify(tampered)


def test_authorize_allow_and_deny():
    req = UsageRequest(actor="buyer", purpose="ml", environment="sandbox",
                       timestamp="2026-06-01", privacy_cost=0.1)
    state = UsageState(usage_count=0)
    ok, violations = authorize(
        request=req, usage_state=state,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=10,
        purposes=frozenset({"ml"}), authorized_actors={"buyer"},
        allowed_environments={"sandbox"}, privacy_budget_max=1.0,
    )
    assert ok and not violations
    # 超次数 → DENY
    state2 = UsageState(usage_count=10)
    ok2, v2 = authorize(
        request=req, usage_state=state2,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=10,
        purposes=frozenset({"ml"}), authorized_actors={"buyer"},
        allowed_environments={"sandbox"}, privacy_budget_max=1.0,
    )
    assert not ok2 and any("次数" in v for v in v2)


def test_enforce_updates_state():
    req = UsageRequest(actor="buyer", purpose="ml", environment="sandbox",
                       timestamp="2026-06-01")
    state = UsageState(usage_count=0)
    res = enforce(
        request=req, usage_state=state,
        valid_from="2026-01-01", valid_until="2026-12-31", max_uses=10,
        purposes=frozenset({"ml"}), authorized_actors={"buyer"},
        allowed_environments={"sandbox"},
    )
    assert res.decision == "ALLOW" and state.usage_count == 1


def test_fingerprint_trace():
    fp = recipient_fingerprint("buyer-1", "salt")
    payload = embed_fingerprint(b"data...", fp)
    candidates = {"buyer-1": fp, "buyer-2": recipient_fingerprint("buyer-2", "salt")}
    assert trace_origin(payload, candidates) == "buyer-1"


def test_download_traceable_no_block_claim():
    import pandas as pd

    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = DownloadTraceableDelivery().deliver(df, "buyer-1", "salt")
    assert out["receipt"]["prevention_strength"] == "traceable-not-blockable"
    assert "fingerprint" in out["receipt"]
