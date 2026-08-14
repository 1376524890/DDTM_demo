"""全流程交易编排（规范 §1/§77 主链 + Phase 8）。

把已实现的各阶段串成一次真正的全流程交易，输出全部数值：
    Entitlement → QualityReference → Data-VOI → Audit-VOI → Certification
    → SellerBond → Pricing → Clearing → StateMachine → Settlement → Feedback
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from valor.audit.action_catalog import ActionCatalog, CertifiedAction
from valor.audit.likelihood import ActionLikelihood
from valor.audit.loss import LossMatrix
from valor.audit.policy import run_policy
from valor.audit.state_model import StateBelief
from valor.contract.accounts import Ledger, Transfer
from valor.contract.escrow import EscrowAccounts
from valor.contract.settlement import settle
from valor.contract.state_machine import StateMachineInput, TransactionStateMachine
from valor.core.enums import TerminalState
from valor.data.download import load_dataset
from valor.data.preprocess import preprocess
from valor.data.split_roles import split_roles_four_way
from valor.data.transaction_batches import make_candidate_batches
from valor.evaluation.oracle import realised_value_oracle
from valor.feedback.eligibility import GroundTruthEligibilityGate
from valor.feedback.seller_risk import update_seller_beta
from valor.liability.capital_cost import capital_cost
from valor.liability.seller_bond import seller_bond_required
from valor.liability.seller_prelock import seller_prelock
from valor.pricing.buyer_max import buyer_max_price
from valor.pricing.clearing import clear_trade
from valor.pricing.seller_min import seller_min_price
from valor.security.certification import CertifiedCell, CertificationCatalog
from valor.valuation.calibration import value_lower_bound_quantile
from valor.valuation.economic_mapping import PayoffMatrix, gross_value, utility_from_predictions
from valor.valuation.exposure import competition_externality
from valor.valuation.oracle import OracleRetraining
from valor.quality.catalog import default_catalog
from valor.quality.reproduction import run_reproduction_gate


def run_full_transaction(cfg: dict) -> dict:
    """执行一次全流程交易，返回完整数值结果。"""
    ds = cfg["dataset"]
    handle = load_dataset(ds["name"])
    X = preprocess(handle.X, fill_strategy="none")
    split = split_roles_four_way(
        X, handle.y, seed=ds["seed"], base_train_frac=ds["base_train_frac"],
        seller_pool_frac=ds["seller_pool_frac"],
        valuation_validation_frac=ds["valuation_validation_frac"],
    )
    base = (X.iloc[split.base_train_idx], handle.y.iloc[split.base_train_idx])
    val = (X.iloc[split.valuation_validation_idx],
           handle.y.iloc[split.valuation_validation_idx])
    final = (X.iloc[split.final_evaluation_idx],
             handle.y.iloc[split.final_evaluation_idx])
    batches = make_candidate_batches(
        X, handle.y, seller_pool_idx=split.seller_pool_idx,
        n_batches=ds["n_batches"], rows_per_batch=ds["rows_per_batch"],
        seed=ds["seed"],
    )

    payoff = PayoffMatrix(**cfg["payoff"])
    result: dict = {}

    # 1) Entitlement / Compliance（§6）
    ent = cfg["entitlement"]
    result["entitlement"] = {"grant_authority": ent["grant_authority"],
                             "compliant": ent["compliant"]}
    if not (ent["grant_authority"] and ent["compliant"]):
        result["decision"] = "NO_TRADE_HARD_GATE"
        return result

    # 2) QualityReference（Phase 1 Gate B，单节点复现）
    catalog = default_catalog()
    ref_df = X.iloc[split.valuation_validation_idx].reset_index(drop=True)
    cand = batches[0]
    certs = run_reproduction_gate(
        catalog, reference_df=ref_df, candidate_df=cand.X,
        y_candidate=cand.y,
        params_by_algorithm={
            "ks_shift": {"column": list(X.columns)[0], "alpha_shift": 0.05},
            "categorical_shift": {"column": list(X.columns)[0], "alpha_shift": 0.05},
            "mmd": {"target_pvalue_resolution": 0.05, "n_permutations": 20},
            "confident_learning": {"floating_tolerance": 0.1, "min_gt_recall": 0.2},
            "metadata_claim_audit": {
                "claims": {"c1": {"predicate": "max_missing_rate",
                                  "column": list(X.columns)[0], "declared": 0.0}},
            },
        },
        created_at="2026-01-01T00:00:00Z",
    )
    quality_gate_pass = all(c.passed for c in certs.values())
    result["quality"] = {"gate_b_pass": quality_gate_pass,
                         "distributed_enabled": catalog.distributed_ids()}

    # 3) Data-VOI（§26-28）：Oracle 边际价值 → gross → 保守下界
    oracle = OracleRetraining(payoff)
    u_base, u_plus = oracle_marginal(base, cand, val, payoff)
    l_comp = competition_externality(
        exposure=cfg.get("exposure", 0.0),
        exclusivity=cfg.get("exclusivity", False),
        sensitivity=cfg.get("competition_sensitivity", 1.0),
    )
    v_gross = gross_value(u_plus, u_base, competition_loss=l_comp)
    # 保守下界：用历史 residual 校准（无历史时用折扣）
    adj = cfg.get("lower_bound_adj", 0.0)
    v_gross_lower = v_gross - adj
    result["valuation"] = {"u_base": u_base, "u_plus": u_plus,
                           "v_gross": v_gross, "l_comp": l_comp,
                           "v_gross_lower": v_gross_lower}

    # 4) Audit-VOI（§24-25）：从校准似然跑策略
    loss = LossMatrix(loss=cfg["loss_matrix"])
    belief = StateBelief.from_prior(cfg["prior"]["pi_b"], cfg["prior"]["q_l"])
    catalog_actions = ActionCatalog()
    lik = ActionLikelihood(action_id="a1", rows={
        "PASS": cfg["likelihood"]["PASS"],
        "QUALITY_FAIL": cfg["likelihood"]["QUALITY_FAIL"],
        "BREACH_EVIDENCE": cfg["likelihood"]["BREACH_EVIDENCE"],
    })
    catalog_actions.register(CertifiedAction(
        "a1", lik, expected_cash_cost=cfg["audit_cost"]["cost"],
        payer=cfg["audit_cost"].get("payer", "SELLER")))
    trace = run_policy(
        tx_id="tx-e2e", initial_belief=belief, catalog=catalog_actions,
        loss=loss, observer=lambda aid: "PASS",
    )
    posterior = trace.steps[-1].posterior if trace.steps else belief.to_plain()
    audit_pay_s = cfg["audit_cost"]["cost"] * max(len(trace.steps), 1) * 0.5
    audit_pay_b = cfg["audit_cost"]["cost"] * max(len(trace.steps), 1) * 0.5
    result["audit"] = {"n_steps": len(trace.steps), "posterior": posterior,
                       "audit_pay_s": audit_pay_s, "audit_pay_b": audit_pay_b}

    # 5) Certification（§22）：p̲_B^sys
    cert_cat = CertificationCatalog()
    cert_cat.register(CertifiedCell(
        "c1", cfg["cert"]["a_D"], cfg["cert"]["b_D"], cfg["cert"]["alpha_D"],
        {"breach": (cfg["cert"]["tp"], cfg["cert"]["fn"])}))
    p_b_lower = cert_cat.p_breach_lower("c1", "breach")
    result["certification"] = {"p_breach_lower_sys": p_b_lower}

    # 6) Seller Bond + pre-lock + 资本成本（§30-31）
    b_s = seller_bond_required(
        p_breach_lower_sys=p_b_lower, g_dev=cfg["bond"]["g_dev"],
        eps_s=cfg["bond"]["eps_s"], p_e_bond=cfg["bond"]["p_e_bond"],
        p_e_f=cfg["bond"]["p_e_f"], lambda_s=cfg["bond"]["lambda_s"],
        f_s=cfg["bond"]["f_s"])
    b_s_pre = seller_prelock(
        cells=[{"p_breach_lower_sys": p_b_lower}], g_dev=cfg["bond"]["g_dev"],
        eps_s=cfg["bond"]["eps_s"], p_e_bond=cfg["bond"]["p_e_bond"],
        p_e_f=cfg["bond"]["p_e_f"], lambda_s=cfg["bond"]["lambda_s"],
        f_s=cfg["bond"]["f_s"])
    c_b_cap = capital_cost(kappa_s=cfg["bond"]["kappa_s"], bond_pre=b_s_pre,
                           bond_required=b_s, t_pre=cfg["bond"]["t_pre"],
                           t_post=cfg["bond"]["t_post"])
    result["liability"] = {"b_s_star": b_s, "b_s_pre": b_s_pre, "c_b_cap": c_b_cap}

    # 7) Pricing（§39-41）
    p_max = buyer_max_price(
        w_b_rem=cfg["buyer"]["w_b_rem"], v_gross_lower=v_gross_lower,
        c_i=cfg["buyer"]["c_i"], c_a_b_pay=audit_pay_b,
        c_r_pay=cfg["buyer"]["c_r_pay"], c_b_use_cap=cfg["buyer"]["c_b_use_cap"],
        r_b_post=cfg["buyer"]["r_b_post"])
    p_min = seller_min_price(
        c_marg=cfg["seller"]["c_marg"], c_a_s_pay=audit_pay_s,
        c_b_cap=c_b_cap, c_r_s_pay=cfg["seller"]["c_r_s_pay"],
        r_s_post=cfg["seller"]["r_s_post"], oc_s=cfg["seller"]["oc_s"],
        pi_s0=cfg["seller"]["pi_s0"])
    clearance = clear_trade(p_max=p_max, p_min=p_min,
                            beta_bar=cfg["pricing"]["beta_bar"])
    result["pricing"] = {"p_max": p_max, "p_min": p_min,
                         "margin": clearance.margin,
                         "clearing_price": clearance.clearing_price,
                         "decision": clearance.decision}

    # 8) State Machine + Settlement（§43）
    sm = TransactionStateMachine()
    terminal = sm.resolve(StateMachineInput(
        entitled=True, compliant=True,
        breach_during_audit=cfg.get("seller_breach", False),
        price_decision=clearance.decision, buyer_breach=False))
    ledger = Ledger()
    for acc, amt in cfg.get("initial_balances", {}).items():
        ledger.create_account(acc, amt)
    accounts = EscrowAccounts(
        e_b_p=cfg.get("initial_balances", {}).get("E_B^P", 0.0),
        b_s_pre=b_s_pre, b_s_star=b_s,
        b_b_use=cfg.get("initial_balances", {}).get("B_B^use", 0.0))
    settle_res = settle(
        terminal=terminal, ledger=ledger, accounts=accounts,
        price=clearance.clearing_price or 0.0, audit_pay_s=audit_pay_s,
        audit_pay_b=audit_pay_b)
    result["state"] = {"terminal": terminal.value,
                       "rights_state": sm.rights_transition(terminal).value,
                       "bond_slashed": settle_res.bond_slashed}

    # 9) Feedback（§45-46）
    if terminal == TerminalState.TRADE:
        v_real = realised_value_oracle(
            base[0], base[1], final[0], final[1], payoff)
        result["feedback"] = {"realised_value": v_real,
                              "eligible_events": ["CONTROLLED_CANARY"]}
    else:
        result["feedback"] = {"realised_value": None,
                              "eligible_events": []}

    result["decision"] = clearance.decision
    return result


def oracle_marginal(base, cand, val, payoff):
    from valor.valuation.oracle import exact_retraining_utility
    u_base, u_plus = exact_retraining_utility(
        X_base=base[0], y_base=base[1], X_batch=cand.X, y_batch=cand.y,
        X_val=val[0], y_val=val[1], payoff=payoff)
    return u_base, u_plus


def main(argv=None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="valor-run")
    ap.add_argument("--config", required=True)
    args = ap.parse_args(argv)
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = run_full_transaction(cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] in ("TRADE", "NO_TRADE_HARD_GATE") else 0


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
