"""Round 4 Phase 2: complete AuditMarketQuote fields + per-action cost."""

from __future__ import annotations

from valor.audit.market_quote import AuditMarketSnapshot, build_quote


def _snapshot() -> AuditMarketSnapshot:
    return AuditMarketSnapshot(
        snapshot_id="snap-1",
        family="quality",
        qualified_nodes=[f"node-{i}" for i in range(10)],
        bids={f"node-{i}": 10.0 + i for i in range(10)},
        min_stake=1.0,
        source_kind="MARKET_DISCOVERED",
        source_ref="market://snap-1",
        version="2",
        capability={f"node-{i}": ["quality"] for i in range(10)},
        stake={f"node-{i}": 100.0 + i for i in range(10)},
        availability={f"node-{i}": 1.0 for i in range(10)},
        reliability={f"node-{i}": 0.99 for i in range(10)},
        public_key_fingerprint={f"node-{i}": f"fp-{i}" for i in range(10)},
    )


def test_quote_contains_round4_fields():
    q = build_quote(
        action_id="a-64",
        action_profile_hash="p" * 64,
        snapshot=_snapshot(),
        m=7,
        min_stake=1.0,
        expected_chain_fee=0.5,
        expected_challenge_cost=1.25,
        expected_dispute_cost=0.75,
        quote_time="2026-01-01T00:00:00+00:00",
        quote_seq=3,
        source_kind="MARKET_DISCOVERED",
        source_ref="market://snap-1",
        version="2",
    )
    plain = q.to_plain()
    assert plain["quote_seq"] == 3
    assert plain["expected_vcg_payments_by_node"]
    assert abs(plain["expected_vcg_payment_total"] - q.expected_vcg_payment) < 1e-9
    assert abs(q.expected_cash_cost -
               (q.expected_vcg_payment + 0.5 + 1.25 + 0.75)) < 1e-9
    assert plain["payer"] == "SELLER"
    assert plain["trigger"] == "BASE_LISTING"
    assert plain["source_kind"] == "MARKET_DISCOVERED"
    assert plain["source_ref"] == "market://snap-1"
    assert plain["version"] == "2"
    assert q.quote_hash


def test_quote_seq_binds_into_hash():
    base = dict(
        action_id="a-64", action_profile_hash="p" * 64, snapshot=_snapshot(),
        m=7, min_stake=1.0,
        expected_chain_fee=0.0, expected_challenge_cost=0.0,
        expected_dispute_cost=0.0,
    )
    q1 = build_quote(**base, quote_seq=1)
    q2 = build_quote(**base, quote_seq=2)
    assert q1.quote_hash != q2.quote_hash


def test_per_action_cost_changes_quote():
    snap = _snapshot()
    q_cheap = build_quote(
        action_id="a-32", action_profile_hash="p32" * 16, snapshot=snap,
        m=7, min_stake=1.0,
        expected_chain_fee=0.0, expected_challenge_cost=1.0,
        expected_dispute_cost=0.0, quote_seq=0,
    )
    q_expensive = build_quote(
        action_id="a-64", action_profile_hash="p64" * 16, snapshot=snap,
        m=7, min_stake=1.0,
        expected_chain_fee=0.0, expected_challenge_cost=5.0,
        expected_dispute_cost=0.0, quote_seq=0,
    )
    assert q_expensive.expected_challenge_cost > q_cheap.expected_challenge_cost
    assert q_expensive.expected_cash_cost > q_cheap.expected_cash_cost
