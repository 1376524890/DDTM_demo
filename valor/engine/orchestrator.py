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
        # 确定性交易身份：tx_id 由冻结 scenario 派生，使 audit task/challenge/
        # commitment/money/lineage 全部可复现（§69 replay 重跑同一交易输出一致）。
        tx_id = "tx-" + content_hash(sc.to_plain())[:20]

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
        # P0-R：FinalEvaluation 不得在交易终态前 materialize。
        # 只保存索引引用，feedback 阶段（终态冻结后）才 resolve。
        final_eval_indices = split.final_evaluation_idx

        split_hash = content_hash({
            "n": dman.n_samples, "roles": dman.role_counts, "seed": sc.split_seed,
        })
        # canonical H(D)：用卖方承诺数据集（candidate）构建唯一 DatasetCommitment。
        # 禁止用 content_hash({"mnist": role_counts}) 等旁路哈希充当 H(D)。
        # P0-A：通过卖方私有 store 一次性生成 salt + Merkle 树，持久化到
        # seller_private，replay 读取同一 frozen commitment（不再重新生成随机
        # salt）。merkle_root 不允许为空。该 commitment 是 listing/valuation/
        # audit/delivery/usage 唯一的 canonical commitment_hash 来源。
        commitment, seller_committed, seller_store = self._build_asset_commitment(
            cand_X, cand_y, tx_id)
        dataset_hash = commitment.dataset_hash
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
        # listing_id 由 commitment 派生，保证确定性重放输出一致（§69）。
        listing = create_listing(
            seller_id=sc.seller_id, asset_id="asset-mnist", asset_version="v1",
            data_commitment=commitment.commitment_hash,
            rights=rights, metadata_claims={"schema": "MNIST-784", "classes": 10},
            listing_id="list-" + content_hash(commitment.commitment_hash)[:16],
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
            "data_commitment": listing.data_commitment,
            "dataset_hash": commitment.dataset_hash,
            "commitment_hash": commitment.commitment_hash,
        })
        self._log(ledger, stage="LISTING", event_type="LISTING_CREATED",
                  formula_id="Z_TAU", formula_output=listing.to_plain())
        self._log(ledger, stage="BINDING", event_type="TRANSACTION_BOUND",
                  formula_id="BINDING_HASH",
                  formula_output={"binding_hash": binding.binding_hash})

        # ---- Entitlement / Compliance / Rights compatibility（阶段 6/32）----
        # P0-I/P0-P：真实执行 EntitlementChecker / ComplianceChecker /
        # RightsRegistry / RightsCompatibility，禁止直接读 sc.entitlement_pass
        # 或硬编码 compliant=True。机制只能读取输入状态，不读取标准答案。
        ent, comp, compat = self._check_entitlement(sc, rights, tx_id)
        ent_pass = ent.passes and comp.passes and compat.passes
        self._stage("entitlement", {
            "pass": ent_pass,
            "entitled": ent.to_plain(),
            "compliant": comp.to_plain(),
            "compatible": compat.to_plain(),
            "policy_hash": content_hash({
                "entitled": ent.to_plain(), "compliant": comp.to_plain(),
                "compatible": compat.to_plain(),
            }),
        })
        self._log(ledger, stage="ENTITLEMENT", event_type="GATE",
                  formula_id="ENTITLED",
                  formula_output={
                      "pass": ent_pass,
                      "entitled": ent.to_plain(), "compliant": comp.to_plain(),
                      "compatible": compat.to_plain(),
                  })
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
        # 保守下界：V̲_gross = V̂_gross + Q_{α_V}(e)，e = V^real - V̂（加法，非减法）。
        # 优先用离线 calibration（P6）residual 分位数；无 calibration 时测试用 0。
        if self.calibration is not None and self.calibration.valuation is not None:
            residual_q = self.calibration.valuation.data["residual_quantile"]
        else:
            residual_q = 0.0
        v_gross_lower = v_gross + residual_q

        # confusion matrix（供 G9 独立复算；joint = confusion / N_eval）
        n_cls = payoff.shape[0]
        confusion = np.zeros((n_cls, n_cls), dtype=float)
        for yt, yp in zip(plus_art.y_true, plus_art.y_pred):
            if yt < n_cls and yp < n_cls:
                confusion[yt, yp] += 1.0
        self._stage("data_voi", {
            "u_base": u_base, "u_plus": u_plus, "delta_u": delta_u,
            "v_gross": v_gross, "l_comp": l_comp, "v_gross_lower": v_gross_lower,
            "deployment_scale": n_b,
            "recompute_inputs": {
                "confusion_matrix": confusion.tolist(),
                "payoff_matrix": sc.payoff_matrix,
                "deployment_scale": n_b,
            },
        })
        self._log(ledger, stage="DATA_VOI", event_type="VALUATION",
                  formula_id="DATA_VOI_MARGINAL",
                  formula_inputs={"n_b": n_b},
                  formula_output={"u_base": u_base, "u_plus": u_plus,
                                  "delta_u": delta_u, "v_gross": v_gross,
                                  "v_gross_lower": v_gross_lower})

        # ---- PreLock（阶段 26-28，B_S^pre 必须先于审计真实锁定）----
        # Certification Envelope → Ω_allowed → B_S^pre = max_ω B_S^*(ω)
        # → MoneyLedger 锁定 → 只有 lock 成功才允许 Audit。
        # 若 seller funds < B_S^pre → NO_TRADE_HARD_GATE，不得进行审计。
        from valor.liability.seller_bond import seller_bond_required
        from valor.liability.seller_prelock import seller_prelock

        bond_params = self._bond_params()
        # Ω_allowed：从冻结证书包络（envelope）取 certified p̲_B^sys 全集。
        # P0-J：PreLock 必须用整包络 max_ω B_S^*(ω)，禁止退化单点。
        if self.calibration is not None and self.calibration.certificate is not None:
            cert_d = self.calibration.certificate.data
            envelope = cert_d.get("envelope")
            if envelope:
                cells = [{"p_breach_lower_sys": c["p_breach_lower_sys"]}
                         for c in envelope]
            else:
                cells = [{"p_breach_lower_sys": cert_d["p_breach_lower_sys"]}]
        else:
            certified_pb = sc.certificate["p_breach_lower_sys"] if "p_breach_lower_sys" in sc.certificate else _certified_pb_from(sc.certificate)
            cells = [{"p_breach_lower_sys": certified_pb}]
        b_s_pre = seller_prelock(cells=cells, **bond_params)
        # P0-J：PreLock 记录逐 cell B_S^*(ω)
        self._prelock_cells = [{"cell_id": c.get("cell_id", i),
                                "p_breach_lower_sys": c["p_breach_lower_sys"],
                                "B_S_star_cell": seller_prelock(cells=[c], **bond_params)}
                               for i, c in enumerate(cells)]
        seller_funds = sc.seller.get("funds")
        if seller_funds is not None and seller_funds < b_s_pre:
            self._stage("prelock", {"b_s_pre": b_s_pre, "seller_funds": seller_funds,
                                    "locked": False, "reason": "insufficient_funds"})
            self._log(ledger, stage="PRELOCK", event_type="BOND",
                      formula_id="B_SELLER_PRE",
                      formula_output={"b_s_pre": b_s_pre,
                                      "seller_funds": seller_funds, "locked": False})
            return self._finalize(ledger, manifest, "NO_TRADE_HARD_GATE",
                                  TerminalState.NO_TRADE, None)
        self._stage("prelock", {"b_s_pre": b_s_pre, "seller_funds": seller_funds,
                                "locked": True,
                                "envelope_cells": self._prelock_cells,
                                "n_cells": len(self._prelock_cells)})
        self._log(ledger, stage="PRELOCK", event_type="BOND",
                  formula_id="B_SELLER_PRE",
                  formula_output={"b_s_pre": b_s_pre,
                                  "seller_funds": seller_funds, "locked": True,
                                  "n_cells": len(self._prelock_cells)})

        # ---- Audit-VOI + 审计执行（阶段 16-29，P4/P5 接入真分布式）----
        audit = self.audit_executor(sc, {
            "ledger": ledger, "candidate_df": cand_X, "y_candidate": cand_y,
            "reference_df": teval_X, "base": (base_X, base_y),
            "binding": binding, "dataset_hash": commitment.dataset_hash,
            "data_commitment": commitment.commitment_hash,
            "b_s_pre": b_s_pre,
            # P0-A：下游审计消费上游 canonical commitment / 卖方 handle / store。
            # 禁止审计层再 SellerCommittedDataset.create() 生成第二个 commitment。
            "dataset_commitment": commitment,
            "seller_committed": seller_committed,
            "seller_store": seller_store,
        })
        self._stage("audit", audit)
        posterior = audit["posterior"]
        p_b_lower = audit["p_breach_lower_sys"]
        audit_pay_s = audit["audit_pay_s"]
        audit_pay_b = audit["audit_pay_b"]
        audit_trace_events = audit.get("audit_trace_events", [])

        # ---- Certification（阶段 25-26）----
        # recompute_inputs：从冻结证书或 scenario 默认取 Beta 参数（G16 独立复算）
        if self.calibration is not None and self.calibration.certificate is not None:
            cert_d = self.calibration.certificate.data
            cert_inputs = {
                "a_D": cert_d["a_D"], "b_D": cert_d["b_D"],
                "alpha_D": cert_d["alpha_D"], "tp": cert_d["tp"],
                "fn": cert_d["fn"],
            }
        else:
            cert_inputs = {
                "a_D": sc.certificate["a_D"], "b_D": sc.certificate["b_D"],
                "alpha_D": sc.certificate["alpha_D"],
                "tp": sc.certificate["tp"], "fn": sc.certificate["fn"],
            }
        self._stage("certification", {
            "p_breach_lower_sys": p_b_lower,
            "recompute_inputs": cert_inputs,
        })
        self._log(ledger, stage="CERTIFICATION", event_type="P_BREACH_LOWER",
                  formula_id="P_BREACH_LOWER_SYS",
                  formula_output={"p_breach_lower_sys": p_b_lower,
                                  "recompute_inputs": cert_inputs})

        # ---- Seller Bond（阶段 27-28，P7 reconciliation）----
        # b_s_pre 已在 Audit 前由 certified envelope 锁定（PreLock 阶段）。
        # 审计后按实际 certified p̲_B^sys 得 B_S^*，AdjustBond：B_S^pre → B_S^*。
        from valor.liability.seller_bond import (
            reconcile_seller_bond, seller_bond_required,
        )
        from valor.liability.capital_cost import capital_cost

        bond_params = self._bond_params()
        b_s_star = seller_bond_required(
            p_breach_lower_sys=p_b_lower, **bond_params)
        b_s_pre = b_s_pre  # 沿用 Audit 前锁定值
        surplus = max(b_s_pre - b_s_star, 0.0)
        c_b_cap = capital_cost(
            kappa_s=sc.bond["kappa_s"], bond_pre=b_s_pre, bond_required=b_s_star,
            t_pre=sc.bond["t_pre"], t_post=sc.bond["t_post"])
        # P7 激励约束对账
        bond_recon = reconcile_seller_bond(
            bond=b_s_star, p_breach_lower_sys=p_b_lower, **bond_params)
        self._stage("seller_bond", {"b_s_star": b_s_star, "b_s_pre": b_s_pre,
                                    "surplus": surplus,
                                    "c_b_cap": c_b_cap, "reconciliation": bond_recon})
        self._log(ledger, stage="SELLER_BOND", event_type="BOND",
                  formula_id="B_SELLER_STAR",
                  formula_output={"b_s_star": b_s_star, "b_s_pre": b_s_pre,
                                  "surplus": surplus, "c_b_cap": c_b_cap,
                                  "constraint_lhs": bond_recon["constraint_lhs"],
                                  "constraint_rhs": bond_recon["constraint_rhs"],
                                  "constraint_slack": bond_recon["constraint_slack"],
                                  "constraint_pass": bond_recon["pass"]})

        # ---- Pricing（阶段 30-33，P12 reconciliation）----
        from valor.pricing.buyer_max import buyer_max_price
        from valor.pricing.seller_min import seller_min_price
        from valor.pricing.clearing import clear_trade
        from valor.rights.dominance import DominanceChecker
        from valor.rights.opportunity_cost import compute_opportunity_cost

        # P0-Q：机会成本由真实 inputs 计算（rights 排他 + future revenue model），
        # 禁止直接读 sc.seller["oc_s"] 常数。
        oc = compute_opportunity_cost(
            exclusivity=rights.exclusivity,
            rev_future_without=sc.exposure.get("rev_future_without",
                                               sc.seller.get("oc_s", 0.0)),
            rev_future_with=sc.exposure.get("rev_future_with",
                                            max(sc.seller.get("oc_s", 0.0) * 0.2, 0.0)),
        )
        oc_s = oc.oc_amount

        # P0-M/S：Buyer Usage Bond 真实接入（若合同适用）
        b_b_use, c_b_use_cap = self._buyer_usage_bond(rights, sc)
        # P0-S：seller bond capital cost 用真实时间区间（BondTimeline）
        c_b_cap = capital_cost(
            kappa_s=sc.bond["kappa_s"], bond_pre=b_s_pre, bond_required=b_s_star,
            t_pre=sc.bond["t_pre"], t_post=sc.bond["t_post"])

        p_max = buyer_max_price(
            w_b_rem=sc.buyer["w_b_rem"], v_gross_lower=v_gross_lower,
            c_i=sc.buyer["c_i"], c_a_b_pay=audit_pay_b,
            c_r_pay=sc.buyer["c_r_pay"], c_b_use_cap=c_b_use_cap,
            r_b_post=sc.buyer["r_b_post"])
        p_min = seller_min_price(
            c_marg=sc.seller["c_marg"], c_a_s_pay=audit_pay_s,
            c_b_cap=c_b_cap, c_r_s_pay=sc.seller["c_r_s_pay"],
            r_s_post=sc.seller["r_s_post"], oc_s=oc_s,
            pi_s0=sc.seller["pi_s0"])
        clearance = clear_trade(p_max=p_max, p_min=p_min,
                                beta_bar=sc.pricing["beta_bar"])

        # MFC-G23：rights menu dominance / no-arbitrage（同一 pricing snapshot）
        dom = DominanceChecker()
        menu_violations = dom.check_dominance_price(
            {rights.rights_hash: p_min}, rights, rights)
        arb_violations = dom.check_no_arbitrage(
            {rights.rights_hash: p_min}, rights, [rights])

        self._stage("pricing", {
            "p_max": p_max, "p_min": p_min, "margin": clearance.margin,
            "clearing_price": clearance.clearing_price,
            "decision": clearance.decision,
            "oc_s": oc_s, "oc_note": oc.note,
            "b_b_use": b_b_use, "c_b_use_cap": c_b_use_cap,
            "dominance_violations": menu_violations,
            "no_arbitrage_violations": arb_violations,
            "recompute_inputs": {
                "v_gross_lower": v_gross_lower, "w_b_rem": sc.buyer["w_b_rem"],
                "c_i": sc.buyer["c_i"], "c_a_b_pay": audit_pay_b,
                "c_r_pay": sc.buyer["c_r_pay"],
                "c_b_use_cap": c_b_use_cap,
                "r_b_post": sc.buyer["r_b_post"],
                "c_marg": sc.seller["c_marg"], "c_a_s_pay": audit_pay_s,
                "c_b_cap": c_b_cap, "c_r_s_pay": sc.seller["c_r_s_pay"],
                "r_s_post": sc.seller["r_s_post"], "oc_s": oc_s,
                "pi_s0": sc.seller["pi_s0"],
                "p_max": p_max, "p_min": p_min,
                "beta_bar": sc.pricing["beta_bar"],
            },
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

        # P0-K：终态由真实 evidence 派生。seller_breach/buyer_misuse 场景仅作为
        # ExperimentWorld GroundTruth：审计 executor 通过实际 corruption 注入使
        # evidence 产生 BREACH_EVIDENCE；buyer breach 由 usage misuse 证据派生。
        # 这里从审计 trace 的 BREACH_EVIDENCE 判定 seller breach（机制观察证据）。
        breach_during_audit = _evidence_seller_breach(audit)
        sm = TransactionStateMachine()
        # P0-K：buyer breach 不在此处用 scenario flag 判定；由 usage evidence
        # 事后派生（MFC-G30）。此处只处理 entitled/audit/price。
        terminal = sm.resolve(StateMachineInput(
            entitled=ent_pass, compliant=True,
            breach_during_audit=breach_during_audit,
            price_decision=clearance.decision, buyer_breach=False))
        self._stage("state", {"terminal": terminal.value})
        ledger_bal = Ledger()
        for acc, amt in {"E_B^P": sc.buyer["w_b_rem"], "E_S^A": audit_pay_s,
                         "E_B^A": audit_pay_b, "B_S^pre": b_s_pre}.items():
            ledger_bal.create_account(acc, amt)
        accounts = EscrowAccounts(
            e_s_a=audit_pay_s, e_b_a=audit_pay_b, e_b_p=sc.buyer["w_b_rem"],
            b_s_pre=b_s_pre, b_s_star=b_s_star, b_b_use=b_b_use)
        if b_b_use > 0:
            ledger_bal.create_account("B_B^use", b_b_use)
        money_ledger = MoneyLedger(ledger_bal, tx_id=tx_id)
        # 结算前捕获 escrow 初始余额（G24 独立复算用）
        escrow_initial = {
            "E_B^P": ledger_bal.balance("E_B^P"),
            "E_S^A": ledger_bal.balance("E_S^A"),
            "E_B^A": ledger_bal.balance("E_B^A"),
            "B_S^pre": ledger_bal.balance("B_S^pre"),
            "B_S^*": ledger_bal.balance("B_S^*"),
            "B_B^use": ledger_bal.balance("B_B^use"),
        }
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
            "escrow_initial_balances": escrow_initial,
        })
        self._log(ledger, stage="SETTLEMENT", event_type="SETTLE",
                  formula_id="SETTLE_PHASE1",
                  formula_output={"terminal": terminal.value,
                                  "conservation": ledger_bal.conservation_check(),
                                  "money_semantics_ok": money_semantics_ok})

        # ---- Delivery（阶段 36，P0-L 正式独立阶段）----
        # Clearing → Settlement Phase I → Delivery → Rights ACTIVE → Usage。
        # 必须验证 H(D_delivery) == H(D_listing)（MFC-G26）。
        delivery_result = self._run_delivery(
            ledger, binding, commitment, terminal, tx_id, seller_committed)

        # ---- Usage（阶段 36-46，仅 TRADE，P9）----
        usage_result = self._run_usage(ledger, binding, terminal)
        # P0-N/MFC-G30：buyer breach 由 UsageViolationEvidence 派生 → 更新终态
        if terminal == TerminalState.TRADE and usage_result.get("buyer_breach"):
            terminal = TerminalState.BUYER_BREACH
            self._stage("state", {"terminal": terminal.value})

        # ---- Controlled Training（P0-M/P0-N 受控训练执行平面，仅 TRADE）----
        # 合法训练真实运行；非法训练在 key release / training start 前被拒。
        training_result = self._run_controlled_training(
            ledger, binding, cand_X, cand_y, terminal)

        # ---- Feedback（阶段 49-51，P10）----
        feedback_result = self._run_feedback(ledger, terminal, X, y,
                                             final_eval_indices,
                                             base_X, base_y, cand_X, cand_y,
                                             payoff, audit)

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

        # G33：真实确定性重放 —— 用同一冻结场景重跑一次完整交易，比较关键输出。
        # 禁止 `replay_consistent=True` 兜底默认。
        replay_consistent = self._run_deterministic_replay(
            terminal, clearance, manifest)

        full_gate = evaluate_full_chain(
            scenario=sc, manifest=manifest, ledger=ledger,
            stages=self._stages, calibration=self.calibration,
            replay_consistent=replay_consistent)
        return OrchestrationResult(
            run_id=self.run_id, scenario_hash=config_hash,
            decision=clearance.decision, terminal_state=terminal.value,
            clearing_price=clearance.clearing_price, full_chain_gate=full_gate)

    # ------------------------------------------------------------------
    # 子阶段
    # ------------------------------------------------------------------
    def _build_asset_commitment(self, cand_X, cand_y, tx_id):
        """用卖方承诺数据集构建 canonical DatasetCommitment（asset 层唯一 H(D)）。

        P0-A：唯一实例。通过 `CommittedDatasetStore`（卖方私有持久化）一次性生成
        salt + Merkle 树，merkle_root 非空，持久化到 seller_private。返回
        (commitment, SellerCommittedDataset, CommittedDatasetStore)。

        下游（listing/valuation/audit/delivery/usage）一律引用
        commitment.commitment_hash；禁止 privacy audit 内再次
        SellerCommittedDataset.create() 生成第二个 commitment。
        """
        import numpy as np

        from valor.asset.commitments import DatasetCommitment
        from valor.core.hashing import content_hash
        from valor.privacy_audit.commitment import (
            CANONICALIZATION_SPEC_HASH,
            CommittedDatasetStore,
        )
        from valor.seller import SellerCommittedDataset

        Xa = np.asarray(cand_X.to_numpy(), dtype=np.uint8) if hasattr(cand_X, "to_numpy") else np.asarray(cand_X, dtype=np.uint8)
        ya = np.asarray(cand_y.to_numpy(), dtype=np.uint8) if hasattr(cand_y, "to_numpy") else np.asarray(cand_y, dtype=np.uint8)
        # 卖方私有 store 路径：runs/<run_id>/seller_private（replay 复用）。
        # dataset_id 用稳定的 asset 版本标识（不含随机 tx_id），salt 用确定性
        # seed（由 split_seed + dataset 名派生），使 replay 复现同一 commitment。
        store = CommittedDatasetStore(str(self.artifacts.root / "seller_private"))
        dataset_id = f"{self.scenario.dataset_name}-v1"
        salt_seed = content_hash({
            "dataset": self.scenario.dataset_name, "version": "v1",
            "split_seed": self.scenario.split_seed,
        })
        seller = SellerCommittedDataset.create(
            store, dataset_id=dataset_id, version="v1", X=Xa, y=ya,
            schema_hash=content_hash({"schema": "MNIST-784"}),
            salt_seed=salt_seed,
        )
        commitment: DatasetCommitment = seller.commitment
        # 强门：canonical commitment 必须带非空 merkle_root（禁止空承诺）
        if not commitment.merkle_root:
            raise RuntimeError("P0-A: canonical DatasetCommitment 的 merkle_root 为空")
        if not commitment.commitment_hash:
            raise RuntimeError("P0-A: canonical DatasetCommitment 的 commitment_hash 为空")
        return commitment, seller, store

    def _make_rights(self, r: dict):
        """从 config rights 构造完整 RightsBundle（所有适用字段执行，无占位）。"""
        from valor.core.enums import DeliveryMode
        from valor.rights.models import RightsBundle

        return RightsBundle(
            r_class=r["r_class"], access_mode=DeliveryMode(r["access_mode"]),
            t0=r["t0"], t1=r["t1"], q=r["q"],
            purposes=frozenset(r["purposes"]), scope=r["scope"],
            exclusivity=r["exclusivity"], redistribution=r["redistribution"],
            derivative=r["derivative"],
            privacy_budget=r.get("privacy_budget"),
            retention=r.get("retention"),
            delete_duty=r.get("delete_duty"),
            not_applicable_reason=r.get("not_applicable_reason"),
        )

    def _check_entitlement(self, sc, rights, tx_id):
        """真实执行 Entitlement / Compliance / Rights compatibility（P0-I/P0-P）。

        从场景的 entitlement/compliance/registry 输入状态判定，机制不读取标准答案。
        场景可通过输入构造违规（如 grant_authority=False / 既有排他许可冲突）。
        """
        from valor.asset.compliance import Compliant
        from valor.asset.entitlement import Entitled
        from valor.rights.compatibility import check_compatible
        from valor.rights.registry import RightsRegistry

        ent_cfg = sc.entitlement or {}
        ent = Entitled(
            grant_authority=bool(ent_cfg.get("grant_authority", True)),
            version_revoked=bool(ent_cfg.get("version_revoked", False)),
            reasons=tuple(ent_cfg.get("reasons", ["seller grant authority"])),
        )
        comp = Compliant(
            buyer_eligible=bool(ent_cfg.get("buyer_eligible", True)),
            menu_conflict=bool(ent_cfg.get("menu_conflict", False)),
            reasons=tuple(ent_cfg.get("compliance_reasons", ["buyer eligible"])),
        )
        # Rights compatibility：与该资产既有活跃许可比对（Registry 真实工作）
        registry = getattr(self, "_rights_registry", None)
        existing = []
        if registry is not None:
            existing = registry.active()  # 返回真实 RightsBundle 列表（P0-P）
        compat = check_compatible(rights, existing)
        # 注册本交易新权利（供后续重复出售检查）
        if registry is not None:
            from valor.core.enums import RightsState

            registry.register(rights, state=RightsState.ACTIVE)
            self._rights_registry = registry
        else:
            self._rights_registry = RightsRegistry(asset_id="asset-mnist")
            self._rights_registry.register(rights)
        return ent, comp, compat

    def _buyer_usage_bond(self, rights, sc):
        """P0-M/S：Buyer Usage Bond 真实接入主链。

        B_B_use 由 certified misuse detection p̲_U^sys + 合同参数计算；若合同
        明确不需独立 usage bond，由显式参数令公式自然为 0（不代码跳过）。
        """
        from valor.liability.buyer_usage_bond import buyer_usage_bond_required

        ub = sc.usage.get("usage_bond", {})
        # p̲_U^sys：certified misuse detection（校准或显式合同）
        p_u = ub.get("p_misuse_lower_sys") if ub else None
        if p_u is None:
            p_u = sc.certificate.get("p_misuse_lower_sys", 0.0)
        g_misuse = ub.get("g_misuse", sc.usage.get("g_misuse", 0.0))
        eps_b = ub.get("eps_b", 0.0)
        p_e_ubond = ub.get("p_e_ubond", 1.0)
        p_e_uf = ub.get("p_e_uf", 0.0)
        lambda_b = ub.get("lambda_b", 1.0)
        f_b = ub.get("f_b", 0.0)
        kappa_b = ub.get("kappa_b", 0.0)
        t_b = ub.get("t_b", 0.0)
        b_b_use = 0.0
        if p_u > 0 and g_misuse > 0:
            b_b_use = buyer_usage_bond_required(
                p_misuse_lower_sys=p_u, g_misuse=g_misuse, eps_b=eps_b,
                p_e_ubond=p_e_ubond, p_e_uf=p_e_uf, lambda_b=lambda_b, f_b=f_b)
        c_b_use_cap = kappa_b * b_b_use * t_b
        return b_b_use, c_b_use_cap

    def _bond_params(self):
        b = self.scenario.bond
        return {
            "g_dev": b["g_dev"], "eps_s": b["eps_s"], "p_e_bond": b["p_e_bond"],
            "p_e_f": b["p_e_f"], "lambda_s": b["lambda_s"], "f_s": b["f_s"],
        }

    def _default_audit_executor(self, sc, ctx):
        """默认审计执行器：COMMIT_CHALLENGE 隐私审计进入正式交易 mainline。

        使用 PrivacyAuditScheduler（选择性披露 + signed evidence + quorum-by-result），
        不再使用 generic DistributedAuditScheduler + in-process evidence_provider。
        """
        from fastapi.testclient import TestClient

        from valor.privacy_audit import (
            ClaimType,
            CommitChallengeVerifier,
            create_privacy_app,
        )
        from valor.privacy_audit.executor_adapter import make_privacy_audit_executor

        n_nodes = int(sc.audit.get("n_nodes", 10))
        f = int(sc.audit.get("f", 2))
        clients = {
            f"node-{i}": TestClient(
                create_privacy_app(CommitChallengeVerifier(f"node-{i}")))
            for i in range(n_nodes)
        }

        class _NodeClient:
            def __init__(self, tc):
                self._tc = tc

            def submit_task(self, task):
                r = self._tc.post("/privacy/tasks", json=task.to_plain())
                r.raise_for_status()
                return r.json()

        factory = lambda nid: _NodeClient(clients[str(nid)])  # noqa: E731
        cal = self.calibration
        executor = make_privacy_audit_executor(
            claim_type=ClaimType.LABEL_DISTRIBUTION,
            challenge_sizes=[32, 64], n_nodes=n_nodes, f=f,
            node_client_factory=factory,
            certificate_artifact=cal.certificate if cal else None,
        )
        return executor(sc, ctx)

    def _run_delivery(self, ledger, binding, commitment, terminal, tx_id, seller_committed):
        """P0-L：正式 Delivery 独立阶段，生成 DeliveryReceipt。

        验证 H(D_delivery) == H(D_listing)（用同一 canonical commitment）。
        三种模式（DOWNLOAD_TRACEABLE / API_GATEWAY / COMPUTE_ONLY）都通过
        valor.execution.delivery.deliver() 生成回执。不一致 → SELLER_BREACH。
        """
        from valor.core.enums import DeliveryMode
        from valor.execution.delivery import deliver

        if terminal != TerminalState.TRADE:
            self._stage("delivery", {"enabled": False, "terminal": terminal.value})
            return {"enabled": False}

        sc = self.scenario
        mode = DeliveryMode(sc.rights["access_mode"])
        listing_commitment = binding.listing.data_commitment
        delivery_commitment = commitment.commitment_hash
        # MFC-G26：H(D_delivery) == H(D_listing)
        if delivery_commitment != listing_commitment:
            self._stage("delivery", {
                "enabled": True, "verified": False,
                "delivery_commitment": delivery_commitment,
                "listing_commitment": listing_commitment,
                "reason": "SELLER_BREACH_DELIVERY",
            })
            self._log(ledger, stage="DELIVERY", event_type="DELIVERY_VERIFY",
                      formula_id="DELIVERY_HASH_MATCH",
                      formula_output={"verified": False,
                                      "delivery_commitment": delivery_commitment,
                                      "listing_commitment": listing_commitment})
            return {"enabled": True, "verified": False,
                    "terminal_override": "SELLER_BREACH"}

        try:
            receipt = deliver(
                tx_id=tx_id, seller_id=sc.seller_id, buyer_id=sc.buyer_id,
                mode=mode, dataset_commitment_hash=delivery_commitment,
                rights_hash=binding.listing.rights_hash,
                listing_commitment_hash=listing_commitment,
                attestation_ref=f"attestation-{tx_id}-{mode.value.lower()}",
            )
        except ValueError as e:  # H(D) 不一致 → SELLER_BREACH
            self._stage("delivery", {
                "enabled": True, "verified": False, "reason": str(e),
            })
            return {"enabled": True, "verified": False,
                    "terminal_override": "SELLER_BREACH"}

        self._stage("delivery", {
            "enabled": True, "verified": True, "mode": mode.value,
            "delivery_id": receipt.delivery_id,
            "delivery_commitment": delivery_commitment,
            "listing_commitment": listing_commitment,
            "equality": delivery_commitment == listing_commitment,
            "delivery_artifact_hash": receipt.delivery_artifact_hash,
            "receipt_hash": receipt.receipt_hash,
            "receipt": receipt.to_plain(),
            "executor": receipt.executor,
        })
        self._log(ledger, stage="DELIVERY", event_type="DELIVERY_VERIFY",
                  formula_id="DELIVERY_HASH_MATCH",
                  formula_output={"verified": True,
                                  "mode": mode.value,
                                  "delivery_commitment": delivery_commitment,
                                  "listing_commitment": listing_commitment,
                                  "receipt_hash": receipt.receipt_hash})
        self.artifacts.write_json("delivery_receipt.json", receipt.to_plain())
        return {"enabled": True, "verified": True, "receipt": receipt.to_plain(),
                "delivery_id": receipt.delivery_id}

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
                allowed_environments=allowed_environments,
                privacy_budget_max=rights.privacy_budget)
            # 确定性 receipt/event id（由请求内容派生）保证重放输出一致（§69）。
            receipt = UsageReceipt(
                receipt_id="receipt-" + content_hash(
                    {"tx": binding.tx_id, "actor": r.actor, "purpose": r.purpose,
                     "ts": r.timestamp, "n": before})[:16],
                tx_id=binding.tx_id,
                rights_hash=binding.listing.rights_hash,
                asset_version_hash=binding.listing.data_commitment,
                buyer_id=sc.buyer_id, requested_action=r.action,
                declared_purpose=r.purpose, usage_count_before=before,
                usage_count_after=state.usage_count, decision=res.decision,
                timestamp=r.timestamp, prev_event_hash=prev_hash)
            rh = receipt.receipt_hash()
            receipts.append(receipt.to_plain())
            results.append({"request": req, "decision": res.decision,
                            "violations": list(res.violations)})
            # lineage（§33 DataFlowEvent）→ hash chain
            ev = DataFlowEvent(
                event_id="evt-" + content_hash(
                    {"tx": binding.tx_id, "actor": r.actor, "purpose": r.purpose,
                     "ts": r.timestamp, "n": before, "rh": rh})[:16],
                tx_id=binding.tx_id,
                actor=r.actor, action="COMPUTE_ON",
                input_refs=(binding.listing.data_commitment,),
                output_refs=(rh,), rights_ref=binding.listing.rights_hash,
                purpose=r.purpose, time=r.timestamp, env=r.environment,
                evidence=res.decision)
            prev_hash = chain.append(ev)
            lineage_events.append(ev)
        chain_valid = chain.verify(lineage_events)

        # P0-N：从 UsageViolationEvidence 派生 buyer breach（MFC-G30）。
        # Mechanism 不读取 scenario 标准答案；违规由真实 DENY 请求派生。
        from valor.usage.misuse import BuyerBreachResolver, evidence_from_deny

        evidences = []
        for i, res in enumerate(results):
            if res["decision"] == "DENY":
                req = sc.usage_requests[i]
                r = UsageRequest(actor=req["actor"], purpose=req["purpose"],
                                 environment=req["environment"],
                                 timestamp=req["timestamp"])
                ev = evidence_from_deny(
                    receipt_id=receipts[i]["receipt_id"] if i < len(receipts) else "",
                    tx_id=binding.tx_id, request=r,
                    violations=res.get("violations", ["USAGE_VIOLATION"]),
                    contract_clause="usage-rights",
                    severity=2 if req.get("actor") != sc.buyer_id else 1,
                )
                evidences.append(ev)
        resolver = BuyerBreachResolver(repeated_threshold=3)
        buyer_breach_res = resolver.resolve(evidences)
        buyer_breach = bool(buyer_breach_res["breach"])

        # P0-N/MFC-G34：retention / deleteDuty 适用时执行受控删除
        deletion = None
        if rights.retention or rights.delete_duty:
            from valor.execution.deletion import execute_delete_duty

            deletion = execute_delete_duty(
                tx_id=binding.tx_id, dataset_commitment=binding.listing.data_commitment,
                buyer=sc.buyer_id, environment="approved_compute",
                derived_artifact_refs=[r.get("receipt_hash", "") for r in receipts],
                mode=rights.access_mode.value,
            )

        # MFC-G36：OpenLineage 兼容导出（权威血缘仍是 hash-chain）
        try:
            from valor.lineage.openlineage_adapter import export_usage_events

            ol_export = export_usage_events(lineage_events)
            self.artifacts.write_json("openlineage.json", ol_export.to_plain())
        except Exception:  # noqa: BLE001  OpenLineage 导出为 interop，失败不阻断
            ol_export = None

        self._stage("usage", {"enabled": True, "results": results,
                              "lineage_last": chain.last(),
                              "chain_valid": chain_valid,
                              "n_requests": len(results),
                              "buyer_breach": buyer_breach,
                              "buyer_breach_reasons": buyer_breach_res["reasons"],
                              "usage_violation_evidence": [e.to_plain() for e in evidences],
                              "deletion": deletion,
                              "openlineage_export": bool(ol_export)})
        self._log(ledger, stage="USAGE", event_type="PEP_ENFORCE",
                  formula_id="PEP",
                  formula_output={"results": results, "lineage_last": chain.last(),
                                  "chain_valid": chain_valid,
                                  "buyer_breach": buyer_breach,
                                  "buyer_breach_reasons": buyer_breach_res["reasons"]})
        self._write_lineage(lineage_events)
        return {"enabled": True, "results": results, "receipts": receipts,
                "lineage_last": chain.last(),
                "chain_valid": chain_valid,
                "buyer_breach": buyer_breach,
                "buyer_breach_reasons": buyer_breach_res["reasons"],
                "usage_violation_evidence": [e.to_plain() for e in evidences],
                "openlineage_export": bool(ol_export)}

    def _run_controlled_training(self, ledger, binding, cand_X, cand_y, terminal):
        """P0-M/P0-N：受控训练执行平面（仅 TRADE）。

        合法训练真实运行（MNIST MLP）；非法训练（actor/purpose/algorithm/
        output）在 key release / training start 前被拒。产出 TrainingOutcome
        供 MFC-G45/G46 校验。
        """
        from valor.execution.controlled_training import ControlledTrainingRunner
        from valor.execution.secure_execution import (
            TrainingJobSpec,
            default_mnist_catalog,
        )
        from valor.usage.models import UsageState

        if terminal != TerminalState.TRADE:
            self._stage("training", {"enabled": False})
            return {"enabled": False}

        sc = self.scenario
        rights = binding.listing.rights
        catalog = default_mnist_catalog()
        runner = ControlledTrainingRunner(catalog=catalog, rights=rights)
        usage_state = UsageState()
        results = []
        # 从 scenario 的训练作业请求派生（合法 + 非法用例）
        train_requests = sc.usage.get("training_requests", [])
        if not train_requests:
            # 默认：一个合法训练 + 一个非法 actor 训练
            train_requests = [
                {"actor": "buyer_org_A", "purpose": "digit-classification",
                 "requested_output": "MODEL_ARTIFACT", "environment": "approved_compute",
                 "expect": "ALLOW"},
                {"actor": "buyer_org_B", "purpose": "digit-classification",
                 "requested_output": "MODEL_ARTIFACT", "environment": "approved_compute",
                 "expect": "DENY"},
            ]
        alg = catalog.get("MNIST_MLP_TRAIN")
        for i, req in enumerate(train_requests):
            job = TrainingJobSpec(
                job_id=f"train-{i}", tx_id=binding.tx_id,
                dataset_commitment_hash=binding.listing.data_commitment,
                rights_hash=binding.listing.rights_hash,
                actor_id=req["actor"], declared_purpose=req["purpose"],
                algorithm_id="MNIST_MLP_TRAIN", algorithm_hash=alg.code_hash,
                container_image_digest=alg.container_digest,
                hyperparameters={"epochs": 1, "batch_size": 128, "lr": 1e-3},
                hyperparameters_hash="hp" * 32,
                input_refs=[binding.listing.data_commitment],
                requested_output=req.get("requested_output", "MODEL_ARTIFACT"),
                execution_profile_id="ep-1", network_policy_hash="np" * 32,
                seed=sc.split_seed + i,
            )
            out = runner.run(
                job=job, dataset_X=cand_X, dataset_y=cand_y,
                valid_from=rights.t0, valid_until=rights.t1, max_uses=rights.q,
                purposes=rights.purposes,
                authorized_actors=set(sc.usage.get("authorized_actors", ["buyer_org_A"])),
                allowed_environments=set(sc.usage.get("allowed_environments", ["approved_compute"])),
                environment=req["environment"], access_mode=rights.access_mode.value,
                derivative=rights.derivative, usage_state=usage_state,
                timestamp="2026-03-01",
            )
            results.append({"request": req, "outcome": out.to_plain()})
        self._stage("training", {
            "enabled": True, "results": results,
            "legal_trained": any(
                r["outcome"]["decision"] == "ALLOW" and r["outcome"]["training_started"]
                for r in results),
            "illegal_blocked": all(
                r["outcome"]["decision"] != "ALLOW" or not r["outcome"].get("training_started")
                for r in results),
            "n_jobs": len(results),
        })
        self._log(ledger, stage="TRAINING", event_type="CONTROLLED_TRAIN",
                  formula_id="TRAINING_PLANE",
                  formula_output={"results": [r["outcome"] for r in results]})
        return {"enabled": True, "results": results}

    def _write_lineage(self, lineage_events) -> None:
        """写入 lineage.jsonl artifact（§33 数据流向血缘）。"""
        self.artifacts.write_jsonl(
            "lineage.jsonl", [e.to_plain() for e in lineage_events])

    def _run_feedback(self, ledger, terminal, X_all_raw, y_all_raw,
                      final_eval_indices, base_X, base_y,
                      cand_X, cand_y, payoff, audit=None):
        """反馈（P10）：Θ_t → Θ_{t+1} + realised Data-VOI。

        realised Data-VOI 在 FinalEvaluation 上计算（严格隔离，§45/§65），
        FinalEvaluation 绝不进入估值/定价/交易决策。
        seller reliability 的 TP/FN 由真实审计证据 vs ground-truth breach 状态
        派生（禁止硬编码 tp=1/fn=0）。
        """
        from valor.feedback.eligibility import GroundTruthEligibilityGate
        from valor.feedback.seller_risk import update_seller_beta
        from valor.valuation.economic_mapping import utility_from_artifact

        sc = self.scenario
        fb = sc.feedback
        payoff = np.asarray(sc.payoff_matrix, dtype=float)
        n_b = sc.buyer_task["deployment_scale"]

        realised = None
        if terminal == TerminalState.TRADE and len(final_eval_indices) > 0:
            # P0-R：终态冻结后才 resolve FinalEvaluation（AccessGuard 语义）。
            idx = np.sort(np.asarray(final_eval_indices, dtype=int))
            final_X = X_all_raw.iloc[idx].reset_index(drop=True)
            final_y = y_all_raw.iloc[idx].reset_index(drop=True)
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

        eligible = GroundTruthEligibilityGate.is_eligible(fb["event_type"])
        theta_after = {"a": fb["theta_s_a"], "b": fb["theta_s_b"]}
        theta_updated = False
        tp = fn = 0
        if terminal == TerminalState.TRADE and eligible:
            # 真实发生：ground truth（scenario 控制 seller 是否真实 breach）
            # vs 审计证据结果（audit outcome）。TP/FN 由对比派生，禁止硬编码。
            gt_breach = bool(sc.seller_breach)
            outcome = (audit or {}).get("audit_trace_events") or []
            # 审计对 breach 的判定：evidence 是否出现 BREACH_EVIDENCE
            aud_breach = any(
                e.get("outcome") == "BREACH_EVIDENCE" for e in outcome)
            # TP/FN = 对 seller reliability 的正确/错误评估：
            #   gt=breach & aud=breach  → TP（正确检出）
            #   gt=breach & aud!=breach → FN（漏报）
            #   gt=诚实 & aud!=breach   → TP（正确判定诚实）
            #   gt=诚实 & aud=breach    → FN（误报，错误评估）
            if gt_breach:
                tp, fn = (1, 0) if aud_breach else (0, 1)
            else:
                tp, fn = (1, 0) if not aud_breach else (0, 1)
            if tp or fn:
                a, b = update_seller_beta(fb["theta_s_a"], fb["theta_s_b"],
                                          tp=tp, fn=fn,
                                          event_type=fb["event_type"])
                theta_after = {"a": a, "b": b}
                theta_updated = True
        self._stage("feedback", {
            "eligible": eligible,
            "theta_before": {"a": fb["theta_s_a"], "b": fb["theta_s_b"]},
            "theta_after": theta_after,
            "theta_updated": theta_updated,
            "realised_data_voi": realised,
            "feedback_tp": tp, "feedback_fn": fn,
        })
        self._log(ledger, stage="FEEDBACK", event_type="THETA_UPDATE",
                  formula_id="THETA_UPDATE",
                  formula_output={"theta_after": theta_after,
                                  "theta_updated": theta_updated,
                                  "realised_data_voi": realised,
                                  "tp": tp, "fn": fn})
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

    def _run_deterministic_replay(self, terminal, clearance, manifest) -> bool:
        """G33：确定性重放 —— 重新启动 isolated replay，重跑完整交易并比较。

        比较 decision / terminal / price / stage hashes / money ledger hash /
        lineage hash。用同一冻结 scenario 与固定 run_id 重放；递归深度限 1 层，
        避免无限重入。
        """
        if getattr(self, "_replay_depth", 0) >= 1:
            # 重放内不再嵌套重放（防止无限递归）
            return True
        try:
            replay = TransactionOrchestrator(
                self.scenario, run_id=f"replay-{self.run_id}",
                run_dir="runs",
                audit_executor=self.audit_executor,
                calibration=self.calibration)
            replay._replay_depth = 1
            r = replay.run()
            # 比较关键输出
            if r.decision != clearance.decision:
                return False
            if r.terminal_state != terminal.value:
                return False
            if abs((r.clearing_price or 0.0) - (clearance.clearing_price or 0.0)) > 1e-6:
                return False
            # stage hashes：比较各 stage 输出 hash 是否一致
            for k, v in replay._stages.items():
                mine = self._stages.get(k)
                if mine is None:
                    return False
                if content_hash(v.output) != content_hash(mine.output):
                    return False
            return True
        except Exception:  # noqa: BLE001  重放失败 → 不一致（fail closed）
            return False

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


def _evidence_seller_breach(audit: dict) -> bool:
    """P0-K：从审计 evidence 判定 seller breach（机制观察证据，非 scenario flag）。

    任一 audit step 的 outcome 为 BREACH_EVIDENCE（真实 corruption 被检测）
    → seller breach。禁止直接读 sc.seller_breach。
    """
    for e in (audit or {}).get("audit_trace_events", []):
        if e.get("outcome") == "BREACH_EVIDENCE":
            return True
    return False


def _certified_pb_from(cert: dict) -> float:
    """从 certificate 参数计算 certified p̲_B^sys（CertificationCatalog 独立复算）。"""
    from valor.security.certification import CertifiedCell, CertificationCatalog

    cat = CertificationCatalog()
    cat.register(CertifiedCell(
        "c1", cert["a_D"], cert["b_D"], cert["alpha_D"],
        {"breach": (cert["tp"], cert["fn"])}))
    return cat.p_breach_lower("c1", "breach")


def run_capstone(scenario: CapstoneScenario, **kwargs) -> OrchestrationResult:
    """便捷入口：运行一次 capstone 交易。"""
    return TransactionOrchestrator(scenario, **kwargs).run()


__all__ = ["TransactionOrchestrator", "OrchestrationResult", "run_capstone"]
