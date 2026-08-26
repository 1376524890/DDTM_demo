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


def test_mutation_vcg_value_fails_g03(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    if events:
        stages["audit"].output["audit_trace_events"][0]["mc_a_pay"] += 1.0
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G03_QUOTE_MATCHES_REVERSE_VCG"] is False


def test_mutation_quote_binding_fails_g04(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    if events:
        stages["audit"].output["audit_trace_events"][0]["action_profile_hash"] = ""
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G04_EXECUTION_BINDS_QUOTE"] is False


def test_mutation_payer_fails_g08(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    if events:
        stages["audit"].output["audit_trace_events"][0]["payer"] = "AUDITOR"
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G08_AUDIT_PAYER_SEMANTICS"] is False


def test_mutation_per_node_settlement_fails_g09(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    if stages.get("settlement_phase1"):
        stages["settlement_phase1"].output["audit_obligations"] = []
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G09_PER_NODE_VCG_SETTLEMENT"] is False


def test_mutation_prelock_envelope_fails_g15(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages["prelock"].output["n_cells"] = 0
    stages["prelock"].output["envelope_cells"] = []
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G15_PRELOCK_USES_ENTIRE_ENVELOPE"] is False


def test_mutation_prelock_order_fails_g16(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages["prelock"].output = {}
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G16_PRELOCK_BEFORE_AUDIT"] is False


def test_mutation_phase1_fails_g24(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages.pop("settlement_phase1", None)
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G24_SETTLEMENT_PHASE1"] is False


def test_mutation_legal_training_fails_g45(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    if stages["training"].output.get("legal_trained"):
        stages["training"].output["results"][0]["outcome"]["worker_pid"] = None
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G45_LEGAL_CONTROLLED_TRAINING_RUNS"] is False


def test_mutation_illegal_training_fails_g46(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    if stages["training"].output.get("results"):
        for r in stages["training"].output["results"]:
            out = r["outcome"]
            if out.get("decision") == "DENY":
                out["key_released"] = True
                break
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G46_ILLEGAL_TRAINING_NO_ACCESS"] is False


def test_mutation_seller_breach_evidence_fails_g31(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages["state"].output["terminal"] = "SELLER_BREACH"
    stages["settlement"].output["terminal"] = "SELLER_BREACH"
    for e in stages["audit"].output.get("audit_trace_events", []):
        e["outcome"] = "PASS"
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G31_SELLER_BREACH_FROM_EVIDENCE"] is False


def test_mutation_buyer_breach_evidence_fails_g30(base):
    sc, stages, manifest, ledger, _ = base
    stages = copy.deepcopy(stages)
    stages["state"].output["terminal"] = "BUYER_BREACH"
    stages["settlement"].output["terminal"] = "BUYER_BREACH"
    stages["usage"].output["buyer_breach"] = True
    stages["usage"].output["usage_violation_evidence"] = []
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G30_BUYER_BREACH_FROM_EVIDENCE"] is False


def test_mutation_market_bid_fails_g03(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    snap = stages["audit"].output.get("market_snapshot")
    if snap and snap.get("bids"):
        first = next(iter(snap["bids"]))
        snap["bids"][first] = float(snap["bids"][first]) + 1.0
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G03_QUOTE_MATCHES_REVERSE_VCG"] is False


def test_mutation_winner_committee_fails_g03(base):
    sc, stages, manifest, ledger, events = base
    stages = copy.deepcopy(stages)
    if events:
        e = stages["audit"].output["audit_trace_events"][0]
        if e.get("committee"):
            e["committee"][0] = "mutated-node"
    gate = _eval(sc, stages, manifest, ledger)
    assert gate["checks"]["MFC-G03_QUOTE_MATCHES_REVERSE_VCG"] is False
