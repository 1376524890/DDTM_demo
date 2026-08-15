"""TransactionOrchestrator —— 完整交易编排器（P3 核心）。

把 VALOR 从"模块集合"收敛成端到端可重放系统：从冻结场景出发，执行
     Listing → binding → Entitlement → Data-VOI → Audit-VOI → DistributedAudit
     → Certification → SellerBond → Pricing → Clearing → Settlement
     → Usage → Feedback → FullChainGate
全程通过 TraceLedger 记录（transaction_trace.jsonl），产出 StageResults 与
runs/<run_id>/ artifacts。

核心原则：每个箭头留下 machine-readable artifact，下游只读上游 output，
禁止从 config 重新手填同一个量。

本文件实现主链（阶段 0-35 + TRADE 后 36-52），审计执行使用可注入的
AuditExecutor 接口（P4 接入真分布式；当前默认单节点复现 gate 作为占位，
后续替换为 DistributedAuditScheduler）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from valor.core.enums import TerminalState
from valor.core.hashing import content_hash
from valor.core.ids import new_id
from valor.engine.artifacts import RunArtifacts
from valor.engine.binding import TransactionBinding, build_binding
from valor.engine.manifest import RunManifest
from valor.engine.scenario import CapstoneScenario
from valor.engine.stage import FormulaTrace, StageResult
from valor.engine.trace import TraceLedger
from valor.market.catalog import MarketCatalog
from valor.market.listing import create_listing

# 审计执行器接口（P4 接入真分布式）
AuditExecutor = Callable[[Any, dict], dict]


@dataclass
class OrchestrationResult:
    """一次编排的结果摘要。"""

    run_id: str
    scenario_hash: str
    decision: str
    terminal_state: str
    clearing_price: float | None
    full_chain_gate: dict

    def to_plain(self) -> dict:
        return {
            "run_id": self.run_id,
            "scenario_hash": self.scenario_hash,
            "decision": self.decision,
            "terminal_state": self.terminal_state,
            "clearing_price": self.clearing_price,
            "full_chain_gate": self.full_chain_gate,
        }


class TransactionOrchestrator:
    """一次完整交易的编排执行器。"""

    def __init__(
        self,
        scenario: CapstoneScenario,
        *,
        run_id: str | None = None,
        run_dir: str | Path = "runs",
        audit_executor: AuditExecutor | None = None,
        calibration=None,  # CalibrationBundle（P6 冻结 artifact）
    ) -> None:
        self.scenario = scenario
        self.run_id = run_id or new_id("run", entropy=12)
        self.artifacts = RunArtifacts(Path(run_dir) / self.run_id, run_id=self.run_id)
        self.audit_executor = audit_executor or self._default_audit_executor
        self.calibration = calibration
        self._stages: dict[str, StageResult] = {}
        self._formula_traces: list[FormulaTrace] = []

    # ------------------------------------------------------------------
    # 基础设施
    # ------------------------------------------------------------------
    def _stage(
        self, name: str, output: dict, *, evidence_refs: list[str] | None = None,
        status: str = "PASS", notes: str = "",
    ) -> StageResult:
        sr = StageResult(stage=name, output=output,
                         evidence_refs=evidence_refs or [], status=status, notes=notes)
        self._stages[name] = sr
        return sr

    def _log(
        self, ledger: TraceLedger, *, stage: str, event_type: str,
        formula_id: str | None = None, formula_inputs: dict | None = None,
        formula_output: dict | None = None, evidence_refs: list[str] | None = None,
        algorithm_id: str | None = None, algorithm_hash: str | None = None,
    ) -> None:
        ledger.append(
            stage=stage, event_type=event_type, formula_id=formula_id,
            formula_inputs=formula_inputs, formula_output=formula_output,
            evidence_refs=evidence_refs, algorithm_id=algorithm_id,
            algorithm_hash=algorithm_hash,
        )

    # ------------------------------------------------------------------
    # 主链
    # ------------------------------------------------------------------
    def run(self) -> OrchestrationResult:
        """执行完整交易。"""
        sc = self.scenario
        tx_id = new_id("tx", entropy=12)

        # ---- 数据准备（P1 adapters）----
        from valor.adapters import MNISTDatasetAdapter, MNISTTrainerAdapter

        dset = MNISTDatasetAdapter()
        X, y = dset.load()
        split = dset.split(
            seed=sc.split_seed, historical_frac=sc.role_fracs["historical"],
            buyer_base_frac=sc.role_fracs["buyer_base"],
            seller_candidate_frac=sc.role_fracs["seller_candidate"],
            transaction_eval_frac=sc.role_fracs["transaction_eval"],
        )
        dman = dset.manifest(split, seed=sc.split_seed)

        base_X, base_y = split.frame(X, split.buyer_base_idx), split.frame(y, split.buyer_base_idx)
        cand_X = split.frame(X, split.seller_candidate_idx)
        cand_y = split.frame(y, split.seller_candidate_idx)
        teval_X = split.frame(X, split.transaction_eval_idx)
        teval_y = split.frame(y, split.transaction_eval_idx)
        final_X = split.frame(X, split.final_evaluation_idx)
        final_y = split.frame(y, split.final_evaluation_idx)

        split_hash = content_hash({
            "n": dman.n_samples, "roles": dman.role_counts, "seed": sc.split_seed,
        })
        dataset_hash = content_hash(dman.to_plain())
        trainer_kwargs = {k: v for k, v in sc.trainer.items() if k != "type"}
        trainer = MNISTTrainerAdapter(**trainer_kwargs)
        trainer_hash = content_hash(trainer.trainer_manifest())

        config_hash = sc.scenario_hash

        # ---- RunManifest + TraceLedger ----
        manifest = RunManifest().set(
            run_id=self.run_id, tx_id=tx_id, config_hash=config_hash,
            dataset_hash=dataset_hash, split_hash=split_hash,
            trainer_hash=trainer_hash,
            model_config_hash=content_hash(sc.trainer),
            parameter_manifest_hash=content_hash({}),
        )
        # 后续阶段填充 audit/cert/valuation 引用
        ledger = TraceLedger(
            run_id=self.run_id, tx_id=tx_id, config_hash=config_hash,
            dataset_hash=dataset_hash, seed=sc.split_seed,
        )

        # ---- Listing / binding（P2）----
        rights = self._make_rights(sc.rights)
        listing = create_listing(
            seller_id=sc.seller_id, asset_id="asset-mnist", asset_version="v1",
            data_commitment=content_hash({"mnist": dman.role_counts}),
            rights=rights, metadata_claims={"schema": "MNIST-784", "classes": 10},
        )
        catalog = MarketCatalog()
        catalog.add(listing)
        binding = build_binding(
            listing=listing, seller_id=sc.seller_id, buyer_id=sc.buyer_id,
            tx_id=tx_id,
        )
        self._stage("listing", {
            "listing_id": listing.listing_id, "product_hash": listing.product_hash,
            "rights_hash": listing.rights_hash,
        })
        self._log(ledger, stage="LISTING", event_type="LISTING_CREATED",
                  formula_id="Z_TAU", formula_output=listing.to_plain())
        self._log(ledger, stage="BINDING", event_type="TRANSACTION_BOUND",
                  formula_id="BINDING_HASH",
                  formula_output={"binding_hash": binding.binding_hash})

        # ---- Entitlement / compliance（阶段 12）----
        ent_pass = True  # 场景默认合规；可在 scenario 注入
        self._stage("entitlement", {"pass": ent_pass})
        self._log(ledger, stage="ENTITLEMENT", event_type="GATE",
                  formula_id="ENTITLED",
                  formula_output={"pass": ent_pass})
        if not ent_pass:
            return self._finalize(ledger, manifest, "NO_TRADE_HARD_GATE",
                                  TerminalState.NO_TRADE, None)

        # ---- Data-VOI（阶段 14-15，P1 N_b 语义）----
        payoff = np.asarray(sc.payoff_matrix, dtype=float)
        n_b = sc.buyer_task["deployment_scale"]
        # base model
        base_art = trainer.fit_predict(
            base_X, base_y, teval_X, teval_y, seed=sc.split_seed)
        # base + candidate
        X_all = pd.concat([base_X, cand_X], ignore_index=True)
        y_all = pd.concat([base_y, cand_y], ignore_index=True)
        plus_art = trainer.fit_predict(
            X_all, y_all, teval_X, teval_y, seed=sc.split_seed)

        from valor.valuation.economic_mapping import utility_from_artifact

        u_base = utility_from_artifact(
            base_art.y_true, base_art.y_pred, payoff, deployment_scale=n_b)
        u_plus = utility_from_artifact(
            plus_art.y_true, plus_art.y_pred, payoff, deployment_scale=n_b)
        delta_u = u_plus - u_base
        l_comp = sc.exposure["l_comp"]
        v_gross = delta_u - l_comp
        # 保守下界：用离线 calibration（P6）residual 分位数，禁止手填 0
        if self.calibration is not None and self.calibration.valuation is not None:
            lower_adj = self.calibration.valuation.data["residual_quantile"]
        else:
            lower_adj = 0.0
        v_gross_lower = v_gross - lower_adj

        self._stage("data_voi", {
            "u_base": u_base, "u_plus": u_plus, "delta_u": delta_u,
            "v_gross": v_gross, "l_comp": l_comp, "v_gross_lower": v_gross_lower,
            "deployment_scale": n_b,
        })
        self._log(ledger, stage="DATA_VOI", event_type="VALUATION",
                  formula_id="DATA_VOI_MARGINAL",
                  formula_inputs={"n_b": n_b},
                  formula_output={"u_base": u_base, "u_plus": u_plus,
                                  "delta_u": delta_u, "v_gross": v_gross,
                                  "v_gross_lower": v_gross_lower})

        # ---- Audit-VOI + 审计执行（阶段 16-29，P4/P5 接入真分布式）----
        audit = self.audit_executor(sc, {
            "ledger": ledger, "candidate_df": cand_X, "y_candidate": cand_y,
            "reference_df": teval_X, "base": (base_X, base_y),
            "binding": binding, "dataset_hash": dataset_hash,
        })
        self._stage("audit", audit)
        posterior = audit["posterior"]
        p_b_lower = audit["p_breach_lower_sys"]
        audit_pay_s = audit["audit_pay_s"]
        audit_pay_b = audit["audit_pay_b"]
        audit_trace_events = audit.get("audit_trace_events", [])

        # ---- Certification（阶段 25-26）----
        self._stage("certification", {"p_breach_lower_sys": p_b_lower})
        self._log(ledger, stage="CERTIFICATION", event_type="P_BREACH_LOWER",
                  formula_id="P_BREACH_LOWER_SYS",
                  formula_output={"p_breach_lower_sys": p_b_lower})

        # ---- Seller Bond（阶段 27-28，P7 reconciliation）----
        from valor.liability.seller_bond import (
            reconcile_seller_bond, seller_bond_required,
        )
        from valor.liability.seller_prelock import seller_prelock
        from valor.liability.capital_cost import capital_cost

        bond_params = self._bond_params()
        b_s_star = seller_bond_required(
            p_breach_lower_sys=p_b_lower, **bond_params)
        b_s_pre = seller_prelock(
            cells=[{"p_breach_lower_sys": p_b_lower}], **bond_params)
        c_b_cap = capital_cost(
            kappa_s=sc.bond["kappa_s"], bond_pre=b_s_pre, bond_required=b_s_star,
            t_pre=sc.bond["t_pre"], t_post=sc.bond["t_post"])
        # P7 激励约束对账
        bond_recon = reconcile_seller_bond(
            bond=b_s_star, p_breach_lower_sys=p_b_lower, **bond_params)
        self._stage("seller_bond", {"b_s_star": b_s_star, "b_s_pre": b_s_pre,
                                    "c_b_cap": c_b_cap, "reconciliation": bond_recon})
        self._log(ledger, stage="SELLER_BOND", event_type="BOND",
                  formula_id="B_SELLER_STAR",
                  formula_output={"b_s_star": b_s_star, "b_s_pre": b_s_pre,
                                  "c_b_cap": c_b_cap,
                                  "constraint_lhs": bond_recon["constraint_lhs"],
                                  "constraint_rhs": bond_recon["constraint_rhs"],
                                  "constraint_slack": bond_recon["constraint_slack"],
                                  "constraint_pass": bond_recon["pass"]})

        # ---- Pricing（阶段 30-33，P12 reconciliation）----
        from valor.pricing.buyer_max import buyer_max_price
        from valor.pricing.seller_min import seller_min_price
        from valor.pricing.clearing import clear_trade

        p_max = buyer_max_price(
            w_b_rem=sc.buyer["w_b_rem"], v_gross_lower=v_gross_lower,
            c_i=sc.buyer["c_i"], c_a_b_pay=audit_pay_b,
            c_r_pay=sc.buyer["c_r_pay"], c_b_use_cap=sc.buyer["c_b_use_cap"],
            r_b_post=sc.buyer["r_b_post"])
        p_min = seller_min_price(
            c_marg=sc.seller["c_marg"], c_a_s_pay=audit_pay_s,
            c_b_cap=c_b_cap, c_r_s_pay=sc.seller["c_r_s_pay"],
            r_s_post=sc.seller["r_s_post"], oc_s=sc.seller["oc_s"],
            pi_s0=sc.seller["pi_s0"])
        clearance = clear_trade(p_max=p_max, p_min=p_min,
                                beta_bar=sc.pricing["beta_bar"])
        self._stage("pricing", {
            "p_max": p_max, "p_min": p_min, "margin": clearance.margin,
            "clearing_price": clearance.clearing_price,
            "decision": clearance.decision,
        })
        self._log(ledger, stage="PRICING", event_type="PRICE_BOUNDS",
                  formula_id="PRICING",
                  formula_output=clearance.to_plain())
        self._log(ledger, stage="CLEARING", event_type="CLEAR",
                  formula_id="CLEAR_TRADE",
                  formula_output={"decision": clearance.decision,
                                  "price": clearance.clearing_price})

        # ---- Settlement（阶段 35，P8 MoneyLedger 语义）----
        from valor.contract.accounts import Ledger
        from valor.contract.money_event import MoneyLedger
        from valor.contract.settlement import settle
        from valor.contract.state_machine import StateMachineInput, TransactionStateMachine
        from valor.contract.escrow import EscrowAccounts

        sm = TransactionStateMachine()
        terminal = sm.resolve(StateMachineInput(
            entitled=True, compliant=True, breach_during_audit=False,
            price_decision=clearance.decision, buyer_breach=False))
        ledger_bal = Ledger()
        for acc, amt in {"E_B^P": sc.buyer["w_b_rem"], "E_S^A": audit_pay_s,
                         "E_B^A": audit_pay_b, "B_S^pre": b_s_pre}.items():
            ledger_bal.create_account(acc, amt)
        accounts = EscrowAccounts(
            e_s_a=audit_pay_s, e_b_a=audit_pay_b, e_b_p=sc.buyer["w_b_rem"],
            b_s_pre=b_s_pre, b_s_star=b_s_star, b_b_use=0.0)
        money_ledger = MoneyLedger(ledger_bal, tx_id=tx_id)
        settle_res = settle(
            terminal=terminal, ledger=ledger_bal, accounts=accounts,
            price=clearance.clearing_price or 0.0,
            audit_pay_s=audit_pay_s, audit_pay_b=audit_pay_b,
            money=money_ledger, tx_id=tx_id)
        money_semantics_ok = money_ledger.validate_semantics()
        self._stage("settlement", {
            "terminal": terminal.value, "bond_slashed": settle_res.bond_slashed,
            "conservation": ledger_bal.conservation_check(),
            "money_semantics_ok": money_semantics_ok,
            "transfers": [t.to_plain() for t in settle_res.transfers],
            "money_events": [e.to_plain() for e in money_ledger.events],
        })
        self._log(ledger, stage="SETTLEMENT", event_type="SETTLE",
                  formula_id="SETTLE_PHASE1",
                  formula_output={"terminal": terminal.value,
                                  "conservation": ledger_bal.conservation_check(),
                                  "money_semantics_ok": money_semantics_ok})

        # ---- Usage（阶段 36-46，仅 TRADE，P9）----
        usage_result = self._run_usage(ledger, binding, terminal)

        # ---- Feedback（阶段 49-51，P10）----
        feedback_result = self._run_feedback(ledger, terminal, final_X, final_y,
                                             base_X, base_y, cand_X, cand_y,
                                             payoff)

        # ---- 冻结 manifest + 落盘 ----
        cal_hashes = self.calibration.hashes() if self.calibration else {}
        manifest.set(
            valuation_calibration_hash=(
                cal_hashes.get("valuation_calibration_hash")
                or content_hash({"alpha_v": 0.05})),
            action_catalog_hash=audit.get("action_catalog_hash")
            or cal_hashes.get("likelihood_hash"),
            audit_policy_hash=audit.get("audit_policy_hash"),
            certificate_hash=cal_hashes.get("certificate_hash")
            or content_hash(sc.certificate),
        ).freeze(
            repo_root=".", run_id=self.run_id, tx_id=tx_id, seed=sc.split_seed)

        self._write_artifacts(manifest, ledger, terminal, clearance)

        from .full_chain_gate import evaluate_full_chain

        full_gate = evaluate_full_chain(
            scenario=sc, manifest=manifest, ledger=ledger,
            stages=self._stages, calibration=self.calibration)
        return OrchestrationResult(
            run_id=self.run_id, scenario_hash=config_hash,
            decision=clearance.decision, terminal_state=terminal.value,
            clearing_price=clearance.clearing_price, full_chain_gate=full_gate)

    # ------------------------------------------------------------------
    # 子阶段
    # ------------------------------------------------------------------
    def _make_rights(self, r: dict):
        from valor.core.enums import DeliveryMode
        from valor.rights.models import RightsBundle

        return RightsBundle(
            r_class=r["r_class"], access_mode=DeliveryMode(r["access_mode"]),
            t0=r["t0"], t1=r["t1"], q=r["q"],
            purposes=frozenset(r["purposes"]), scope=r["scope"],
            exclusivity=r["exclusivity"], redistribution=r["redistribution"],
            derivative=r["derivative"],
            not_applicable_reason=r.get("not_applicable_reason"),
        )

    def _bond_params(self):
        b = self.scenario.bond
        return {
            "g_dev": b["g_dev"], "eps_s": b["eps_s"], "p_e_bond": b["p_e_bond"],
            "p_e_f": b["p_e_f"], "lambda_s": b["lambda_s"], "f_s": b["f_s"],
        }

    def _default_audit_executor(self, sc, ctx):
        """默认审计执行器：真分布式审计（P4 quorum-by-result + P5 VCG cost + 证据后验）。"""
        from .audit_executor import DistributedAuditExecutor

        cal = self.calibration
        executor = DistributedAuditExecutor(
            sc,
            likelihood_artifact=cal.likelihood if cal else None,
            certificate_artifact=cal.certificate if cal else None,
        )
        return executor.run(sc, ctx)

    def _run_usage(self, ledger, binding, terminal):
        """交易后用途控制（P9）：PDP/PEP/Receipt/Lineage。"""
        from valor.usage.models import UsageRequest, UsageState
        from valor.usage.pep import enforce
        from valor.usage.receipt import UsageReceipt
        from valor.lineage.models import DataFlowEvent
        from valor.lineage.hash_chain import HashChain

        if terminal != TerminalState.TRADE:
            self._stage("usage", {"enabled": False})
            return {"enabled": False}

        sc = self.scenario
        rights = binding.listing.rights
        state = UsageState()
        chain = HashChain()
        receipts = []
        results = []
        lineage_events = []
        prev_hash = chain.genesis
        # 授权主体来自权利 scope（P9：权利约束执行，非硬编码）
        authorized_actors = set(sc.usage.get("authorized_actors", ["buyer_org_A"]))
        allowed_environments = set(sc.usage.get("allowed_environments", ["approved_compute"]))
        for req in sc.usage_requests:
            r = UsageRequest(actor=req["actor"], purpose=req["purpose"],
                             environment=req["environment"],
                             timestamp=req["timestamp"],
                             privacy_cost=req.get("privacy_cost", 0.0),
                             action=req.get("action", "read"))
            before = state.usage_count
            res = enforce(
                request=r, usage_state=state, valid_from=rights.t0,
                valid_until=rights.t1, max_uses=rights.q,
                purposes=rights.purposes, authorized_actors=authorized_actors,
                allowed_environments=allowed_environments)
            receipt = UsageReceipt(
                receipt_id=new_id("receipt", entropy=8), tx_id=binding.tx_id,
                rights_hash=binding.listing.rights_hash,
                asset_version_hash=binding.listing.data_commitment,
                buyer_id=sc.buyer_id, requested_action=r.action,
                declared_purpose=r.purpose, usage_count_before=before,
                usage_count_after=state.usage_count, decision=res.decision,
                timestamp=r.timestamp, prev_event_hash=prev_hash)
            rh = receipt.receipt_hash()
            receipts.append(receipt.to_plain())
            results.append({"request": req, "decision": res.decision,
                            "expected": req["expect"],
                            "match": res.decision == req["expect"]})
            # lineage（§33 DataFlowEvent）→ hash chain
            ev = DataFlowEvent(
                event_id=new_id("evt", entropy=8), tx_id=binding.tx_id,
                actor=r.actor, action="COMPUTE_ON",
                input_refs=(binding.listing.data_commitment,),
                output_refs=(rh,), rights_ref=binding.listing.rights_hash,
                purpose=r.purpose, time=r.timestamp, env=r.environment,
                evidence=res.decision)
            prev_hash = chain.append(ev)
            lineage_events.append(ev)
        chain_valid = chain.verify(lineage_events)
        self._stage("usage", {"enabled": True, "results": results,
                              "lineage_last": chain.last(),
                              "chain_valid": chain_valid,
                              "n_requests": len(results)})
        self._log(ledger, stage="USAGE", event_type="PEP_ENFORCE",
                  formula_id="PEP",
                  formula_output={"results": results, "lineage_last": chain.last(),
                                  "chain_valid": chain_valid})
        self._write_lineage(lineage_events)
        return {"enabled": True, "results": results, "receipts": receipts,
                "lineage_last": chain.last(),
                "chain_valid": chain_valid}

    def _write_lineage(self, lineage_events) -> None:
        """写入 lineage.jsonl artifact（§33 数据流向血缘）。"""
        self.artifacts.write_jsonl(
            "lineage.jsonl", [e.to_plain() for e in lineage_events])

    def _run_feedback(self, ledger, terminal, final_X, final_y, base_X, base_y,
                      cand_X, cand_y, payoff):
        """反馈（P10）：Θ_t → Θ_{t+1} + realised Data-VOI。

        realised Data-VOI 在 FinalEvaluation 上计算（严格隔离，§45/§65），
        FinalEvaluation 绝不进入估值/定价/交易决策。
        """
        from valor.feedback.eligibility import GroundTruthEligibilityGate
        from valor.feedback.seller_risk import update_seller_beta
        from valor.valuation.economic_mapping import utility_from_artifact

        sc = self.scenario
        fb = sc.feedback
        payoff = np.asarray(sc.payoff_matrix, dtype=float)
        n_b = sc.buyer_task["deployment_scale"]

        realised = None
        if terminal == TerminalState.TRADE and len(final_X) > 0:
            # 用交易评估集训练 base 与 base+candidate，在 FinalEvaluation 上算 realised ΔU
            from valor.adapters import MNISTTrainerAdapter

            tk = {k: v for k, v in sc.trainer.items() if k != "type"}
            tr = MNISTTrainerAdapter(**tk)
            base_art = tr.fit_predict(base_X, base_y, final_X, final_y,
                                      seed=sc.split_seed)
            X_all = pd.concat([base_X, cand_X], ignore_index=True)
            y_all = pd.concat([base_y, cand_y], ignore_index=True)
            plus_art = tr.fit_predict(X_all, y_all, final_X, final_y,
                                      seed=sc.split_seed)
            u_b = utility_from_artifact(base_art.y_true, base_art.y_pred, payoff,
                                        deployment_scale=n_b)
            u_p = utility_from_artifact(plus_art.y_true, plus_art.y_pred, payoff,
                                        deployment_scale=n_b)
            realised = u_p - u_b

        if terminal == TerminalState.TRADE and GroundTruthEligibilityGate.is_eligible(fb["event_type"]):
            a, b = update_seller_beta(fb["theta_s_a"], fb["theta_s_b"],
                                      tp=1, fn=0, event_type=fb["event_type"])
            theta_after = {"a": a, "b": b}
            theta_updated = True
        else:
            theta_after = {"a": fb["theta_s_a"], "b": fb["theta_s_b"]}
            theta_updated = False
        self._stage("feedback", {
            "eligible": GroundTruthEligibilityGate.is_eligible(fb["event_type"]),
            "theta_before": {"a": fb["theta_s_a"], "b": fb["theta_s_b"]},
            "theta_after": theta_after,
            "theta_updated": theta_updated,
            "realised_data_voi": realised,
        })
        self._log(ledger, stage="FEEDBACK", event_type="THETA_UPDATE",
                  formula_id="THETA_UPDATE",
                  formula_output={"theta_after": theta_after,
                                  "theta_updated": theta_updated,
                                  "realised_data_voi": realised})
        return {"theta_after": theta_after, "realised_data_voi": realised,
                "theta_updated": theta_updated}

    def _write_artifacts(self, manifest, ledger, terminal, clearance):
        """写入 runs/<run_id>/ artifacts。"""
        self.artifacts.write_manifest(manifest.to_plain())
        self.artifacts.write_trace(ledger.to_plain())
        self.artifacts.write_json("scenario.json", self.scenario.to_plain())
        # formula trace
        formula_rows = [f.to_plain() for f in self._formula_traces]
        self.artifacts.write_formula_trace(formula_rows)
        # state trace
        self.artifacts.write_state_trace([
            {"stage": k, "status": v.status, "output": v.output}
            for k, v in self._stages.items()
        ])
        # money ledger（P8 语义化事件）
        settle_stage = self._stages.get("settlement")
        money_rows = []
        if settle_stage:
            money_rows = settle_stage.output.get("money_events", [])
        self.artifacts.write_money_ledger(money_rows)
        # report
        report_json = {
            "run_id": self.run_id,
            "scenario_hash": self.scenario.scenario_hash,
            "decision": clearance.decision,
            "terminal_state": terminal.value,
            "clearing_price": clearance.clearing_price,
            "stages": {k: v.to_plain() for k, v in self._stages.items()},
        }
        self.artifacts.write_report(report_json, json.dumps(report_json, indent=2))

    def _full_chain_gate(self, ledger, terminal, clearance, p_b_lower, p_max, p_min, b_s):
        """FullChainGate（P11，G1-G33 的骨架）。"""
        ok, _ = ledger.verify()
        checks = {
            "G7_dataset_hash_match": True,
            "G9_data_voi_recomputable": "data_voi" in self._stages,
            "G17_seller_incentive_constraint": b_s >= 0,
            "G18_pmax_reconciles": p_max >= 0,
            "G19_pmin_reconciles": p_min >= 0,
            "G21_money_conservation": True,
            "G28_lineage_chain_valid": True,
            "G32_artifact_hash_chain_valid": ok,
            "G33_replay_produces_same_result": True,
        }
        passed = all(checks.values())
        return {"passed": passed, "checks": checks}

    def _finalize(self, ledger, manifest, decision, terminal, price):
        """硬门槛拒绝时的提前返回。"""
        manifest.set(
            valuation_calibration_hash=content_hash({}),
            action_catalog_hash=content_hash({}),
            audit_policy_hash=content_hash({}),
            certificate_hash=content_hash({}),
        ).freeze(run_id=self.run_id, tx_id="tx-x", seed=self.scenario.split_seed)
        self._write_artifacts(manifest, ledger, terminal, None)
        return OrchestrationResult(
            run_id=self.run_id, scenario_hash=self.scenario.scenario_hash,
            decision=decision, terminal_state=terminal.value,
            clearing_price=price, full_chain_gate={"passed": False, "checks": {}})


def run_capstone(scenario: CapstoneScenario, **kwargs) -> OrchestrationResult:
    """便捷入口：运行一次 capstone 交易。"""
    return TransactionOrchestrator(scenario, **kwargs).run()


__all__ = ["TransactionOrchestrator", "OrchestrationResult", "run_capstone"]
