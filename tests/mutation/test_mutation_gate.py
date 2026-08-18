"""Mutation tests for FullChainGate: mutating a mechanism fact must fail a gate."""

from __future__ import annotations

import copy
import json

import pytest

from valor.engine import CapstoneScenario, TransactionOrchestrator
from valor.engine.full_chain_gate import evaluate_full_chain
from valor.engine.manifest import RunManifest
from valor.engine.trace import TraceLedger


@pytest.fixture(scope="module")
def base():
    sc = CapstoneScenario(scenario_id="mut-base", seller_id="s", buyer_id="b")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    sc.buyer["w_b_rem"] = 1000.0
    sc.seller["pi_s0"] = 0.0
    sc.exposure["rev_future_with"] = 0.0
    sc.exposure["rev_future_without"] = 0.0
    sc.seller["c_marg"] = 0.0
    sc.seller["c_r_s_pay"] = 0.0
    sc.seller["r_s_post"] = 0.0
    sc.buyer["r_b_post"] = 0.0
    sc.audit["market"]["bids"] = {f"node-{i}": 0.0 for i in range(10)}
    sc.bond.update({
        "g_dev": 0.0, "eps_s": 0.0, "p_e_bond": 1.0, "p_e_f": 0.0,
        "lambda_s": 1.0, "f_s": 0.0, "kappa_s": 0.0, "t_pre": 0.0, "t_post": 0.0,
    })
    orch = TransactionOrchestrator(sc, run_dir="/tmp/mut-runs")
    res = orch.run()
    manifest = RunManifest.from_plain(
        json.loads((orch.artifacts.root / "manifest.json").read_text())
    )
    trace_rows = [json.loads(l) for l in
                  (orch.artifacts.root / "transaction_trace.jsonl").read_text().splitlines()]
    ledger = TraceLedger(
        run_id=manifest.run_id or "", tx_id=manifest.tx_id or "",
        config_hash=manifest.config_hash or "", dataset_hash=manifest.dataset_hash or "",
        seed=manifest.seed or 0,
    ).load(trace_rows)
    return sc, orch._stages, manifest, ledger, orch._stages["audit"].output.get("audit_trace_events", [])


def _eval(sc, stages, manifest, ledger, replay=True, final_eval_leak=False):
    return evaluate_full_chain(
        scenario=sc, manifest=manifest, ledger=ledger,
        stages=stages, replay_consistent=replay,
        final_eval_accessed_before_decision=final_eval_leak,
    )


def test_mutation_commitment_fails_g01(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages["listing"].output["commitment_hash"] = "mutated"
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G01_SINGLE_DATASET_COMMITMENT"] is False


def test_mutation_quote_order_fails_g02(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    if events:
        stages["audit"].output["audit_trace_events"][0]["quote_seq"] = 999
        stages["audit"].output["audit_trace_events"][0]["execution_seq"] = 1
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G02_VCG_QUOTED_BEFORE_VOI"] is False


def test_mutation_unsigned_evidence_fails_g05(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    if events:
        stages["audit"].output["audit_trace_events"][0]["evidence_signed"] = False
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G05_SIGNED_EVIDENCE_ONLY"] is False


def test_mutation_delivery_verified_fails_g26(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages["delivery"].output["verified"] = False
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G26_DELIVERY_HASH_MATCHES_TRANSACTION"] is False


def test_mutation_price_fails_g19(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages["pricing"].output["p_max"] += 1.0
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G19_PMAX_RECONCILES"] is False


def test_mutation_final_eval_leak_fails_g37(base):
    sc, stages, manifest, ledger, _ = base
    gate = _eval(sc, copy.deepcopy(stages), manifest, ledger,
                 replay=True, final_eval_leak=True)
    assert gate["checks"]["MFC-G37_FINALEVAL_UNREADABLE_PRE_TERMINAL"] is False


def test_mutation_replay_fails_g50(base):
    sc, stages, manifest, ledger, _ = base
    gate = _eval(sc, copy.deepcopy(stages), manifest, ledger, replay=False)
    assert gate["checks"]["MFC-G50_DETERMINISTIC_REPLAY"] is False
