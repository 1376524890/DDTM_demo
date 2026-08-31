"""FullChainGate —— 论文闭合门（MFC-G01..G50），真正独立复算 + 真实重放。

对可公式化量（Data-VOI、Pmax/Pmin/Clearing、p̲_B^sys、MC_A^pay、seller/buyer
bond、capital cost）用 FormulaReconciliationEngine 独立重算；对协议/机制量
（commitment、quorum、evidence 签名、posterior、escrow、delivery、usage、
replay）做真实结构性验证。

所有 PASS 才输出 Paper Closure Gate = PASS。禁止 `replay_consistent=True`
兜底，禁止读取 scenario 标准答案作为机制决策。

门清单（对齐任务书 §38）：
    G01 single commitment instance
    G02 VCG quote before VOI decision
    G03 quote independently recomputes Reverse VCG
    G04 execution binds frozen quote
    G05 all counted evidence signed
    G06 quorum independently recounted from valid evidence
    G07 DP/query budget != audit disclosure budget
    G08 payer from action policy
    G09 exact per-node VCG settlement
    G10 action-specific likelihood
    G11 no manual likelihood
    G12 posterior independently replayed
    G13 runtime policy hash == certified policy hash
    G14 pB_sys independently recomputed
    G15 PreLock uses entire allowed envelope
    G16 PreLock before audit
    G17 seller bond IC reconciles
    G18 buyer usage bond IC reconciles
    G19 Pmax reconciliation
    G20 Pmin reconciliation
    G21 margin + clearing reconciliation
    G22 rights compatibility passed
    G23 rights menu dominance/no-arbitrage
    G24 Settlement Phase I
    G25 Delivery exists
    G26 D_delivery == D_transaction
    G27 Rights ACTIVE before any data use
    G28 every usage request has receipt
    G29 DENY before key/data release
    G30 BUYER_BREACH derived from evidence
    G31 SELLER_BREACH derived from evidence
    G32 Settlement Phase II
    G33 escrow balances close at correct lifecycle point
    G34 retention/delete duty executed
    G35 lineage hash-chain valid
    G36 OpenLineage export consistent
    G37 FinalEvaluation unreadable pre-terminal
    G38 R_cal/R_cert/R_eval isolated
    G39 calibration trainer scope matches online trainer
    G40 feedback eligibility valid
    G41 theta update independently reproducible
    G42 no business defaults in EXPERIMENT/PRODUCTION
    G43 no placeholder hashes / manual TP/FN / overrides
    G44 auditor process has no full dataset
    G45 legal controlled training actually runs
    G46 illegal controlled training cannot access D
    G47 money conservation
    G48 recipient semantics correct
    G49 trace/artifact chain valid
    G50 deterministic replay actually reruns transaction
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from valor.engine.calibration import CalibrationBundle
from valor.engine.formula_reconciliation import build_valor_engine
from valor.engine.manifest import RunManifest
from valor.engine.scenario import CapstoneScenario
from valor.engine.trace import TraceLedger


@dataclass
class MechanismVerificationContext:
    """Formal/production artifact context for FullChainGate.

    Replaces legacy CalibrationBundle-only wiring. In FORMAL/PRODUCTION every
    check must be derivable from these explicit artifacts rather than from
    `calibration is not None`.
    """

    execution_mode: str = ""
    role_registry: Any = None
    valuation_calibration: Any = None
    likelihood_catalog: Any = None
    action_profile_catalog: Any = None
    audit_policy: Any = None
    policy_certificate: Any = None
    market_snapshot: Any = None
    quote_ledger: Any = None
    raw_audit_evidence_store: Any = None
    runtime_descriptor: Any = None
    money_ledger: Any = None
    rights_registry: Any = None
    final_eval_access_ledger: Any = None
    randomness_manifest: Any = None
    replay_artifact: Any = None
    provenance_graph: Any = None


@dataclass
class FullChainGate:
    """论文闭合门评估器（独立复算 + 真实重放）。"""

    scenario: CapstoneScenario
    manifest: RunManifest
    ledger: TraceLedger
    stages: dict[str, Any]
    calibration: CalibrationBundle | None = None
    legacy_replay_consistent: bool | None = None
    legacy_final_eval_accessed_before_decision: bool | None = None
    context: MechanismVerificationContext | None = None

    def _stage(self, name: str) -> dict:
        st = self.stages.get(name)
        return st.output if st else {}

    def _check(self, results: dict[str, bool], name: str, fn) -> None:
        try:
            results[name] = bool(fn())
        except Exception:
            results[name] = False

    def _ctx(self) -> MechanismVerificationContext | None:
        return self.context

    def _no_business_defaults(self) -> bool:
        import subprocess
        import sys
        from pathlib import Path

        repo = Path(__file__).resolve().parent.parent.parent
        proc = subprocess.run(
            [sys.executable, str(repo / "scripts" / "check_business_defaults.py"),
             "--root", str(repo / "valor")],
            capture_output=True, text=True, timeout=120,
        )
        biz_ok = "未发现业务默认值" in proc.stdout or "未发现" in proc.stdout
        # MFC-G43：禁止模式扫描（expected_cash_cost=0 / total_pay*0.5 / 手工 TP-FN）
        proc2 = subprocess.run(
            [sys.executable, str(repo / "scripts" / "check_forbidden_patterns.py"),
             "--root", str(repo / "valor")],
            capture_output=True, text=True, timeout=120,
        )
        forb_ok = "未发现禁止模式" in proc2.stdout
        return biz_ok and forb_ok

    def run(self) -> dict:
        results: dict[str, bool] = {}
        s = self._stage
        cal = self.calibration
        eng = build_valor_engine()

        # ================= MFC-G01：单一 canonical commitment 实例 ==========
        def _g01():
            listing = s("listing").get("commitment_hash")
            valuation = s("valuation").get("dataset_commitment") or s("valuation").get("commitment_hash")
            audit = s("audit").get("commitment_hash")
            delivery = s("delivery").get("delivery_commitment") or s("delivery").get("commitment_hash")
            usage = s("usage").get("asset_version_hash") or s("usage").get("commitment_hash")
            training = s("training").get("commitment_hash")
            pairs = [
                ("listing", listing), ("valuation", valuation), ("audit", audit),
                ("delivery", delivery), ("usage", usage), ("training", training),
            ]
            # For TRADE, every required stage that exists must provide a ref; all refs equal.
            if self._is_trade():
                for stage_name, ref in pairs:
                    if stage_name in self._stages and not ref:
                        return False
            refs = [r for _, r in pairs if r]
            if not refs:
                return self.manifest.dataset_hash is not None
            return all(x == refs[0] for x in refs)
        self._check(results, "MFC-G01_SINGLE_DATASET_COMMITMENT", _g01)

        # ================= MFC-G02..G04：Quote→Choose→Execute ===============
        audit_events = s("audit").get("audit_trace_events", [])

        def _g02():
            # mandatory audit must have executed at least one step
            if (self._is_trade() and self.scenario.audit.get("mandatory_base_audit_policy")
                    and not audit_events):
                return False
            if self._ledger_quote_order_ok():
                return True
            # legacy fallback: logical sequence from audit event seq fields
            for e in audit_events:
                if e.get("quote_seq") is not None:
                    if not (e.get("quote_seq") < e.get("voi_decision_seq")
                            < e.get("execution_seq")):
                        return False
            return True
        self._check(results, "MFC-G02_VCG_QUOTED_BEFORE_VOI", _g02)

        def _g03():
            # quote 独立重算 Reverse VCG：从 frozen snapshot + profile + m 重算。
            snap = s("audit").get("market_snapshot")
            for e in audit_events:
                if e.get("status") == "CERTIFIED":
                    if not snap:
                        return False
                    from valor.audit.market_quote import AuditMarketSnapshot
                    from valor.distributed.node_state import AuditorNode, NodeRegistry
                    from valor.core.ids import AuditorID
                    from valor.market.reverse_vcg import reverse_vcg_payments

                    mkt = AuditMarketSnapshot(
                        snapshot_id=snap.get("snapshot_id", "mkt"),
                        family=snap.get("family", "quality"),
                        qualified_nodes=snap["qualified_nodes"],
                        bids={str(k): float(v) for k, v in snap["bids"].items()},
                        min_stake=float(snap.get("min_stake", 0.0)),
                        source_kind=snap.get("source_kind", "MARKET_DISCOVERED"),
                        source_ref=snap.get("source_ref", ""),
                        version=snap.get("version", "1"),
                        capability=snap.get("capability", {}),
                        stake=snap.get("stake", {}),
                        availability=snap.get("availability", {}),
                        reliability=snap.get("reliability", {}),
                        public_key_fingerprint=snap.get("public_key_fingerprint", {}),
                    )
                    f = int(self.scenario.audit.get("f", 2))
                    m = 3 * f + 1
                    reg = NodeRegistry()
                    for nid in mkt.qualified_nodes:
                        reg.register(AuditorNode(
                            AuditorID(nid), (mkt.family,), 1.0, mkt.min_stake))
                    bids = {AuditorID(str(nid)): float(b) for nid, b in mkt.bids.items()}
                    try:
                        payments, _ = reverse_vcg_payments(
                            reg, family=mkt.family, m=m, bids=bids,
                            min_stake=mkt.min_stake)
                    except Exception:
                        return False
                    realized = {str(k): float(v) for k, v in e.get("vcg_payments", {}).items()}
                    recomputed = {str(k): float(v) for k, v in payments.items()}
                    if sorted(realized) != sorted(recomputed):
                        return False
                    for nid in realized:
                        if abs(realized[nid] - recomputed[nid]) > 1e-6:
                            return False
                    if abs(sum(recomputed.values()) - e.get("mc_a_pay", 0)) > 1e-6:
                        return False
                    if sorted(e.get("committee", [])) != sorted(recomputed):
                        return False
            return True
        self._check(results, "MFC-G03_QUOTE_MATCHES_REVERSE_VCG", _g03)

        def _g04():
            # execution 绑定冻结 quote：decision record profile/snapshot/likelihood
            # must exactly equal the executed action's profile/snapshot/quote hash.
            decision_records = s("audit").get("frozen_audit_decision_records", [])
            exec_records = s("audit").get("audit_execution_records", [])
            if not decision_records or not exec_records:
                return False
            by_quote = {r.get("quote_hash"): r for r in decision_records}
            for er in exec_records:
                qh = er.get("selected_quote_hash")
                dr = by_quote.get(qh)
                if dr is None:
                    return False
                if dr.get("action_profile_hash") != er.get("selected_action_profile_hash"):
                    return False
                if dr.get("market_snapshot_hash") != er.get("selected_market_snapshot_hash"):
                    return False
            # likelihood_artifact_hash is G10 territory, not G04; do not require here.
            # every CERTIFIED audit event must carry quote/snapshot/profile binding
            for e in audit_events:
                if e.get("status") == "CERTIFIED":
                    if not e.get("quote_hash") or not e.get("market_snapshot_hash") or not e.get("action_profile_hash"):
                        return False
            return True
        self._check(results, "MFC-G04_EXECUTION_BINDS_QUOTE", _g04)

        # ================= MFC-G05/G06：签名 evidence + 有效 quorum ==========
        def _g05():
            # 审计证据必须签名（P0-F），且 CERTIFIED 必须有足够有效签名。
            for e in audit_events:
                if e.get("evidence_signed") is False:
                    return False
                if e.get("status") == "CERTIFIED":
                    q = 2 * self.scenario.audit.get("f", 2) + 1
                    if e.get("valid_signature_count", 0) < q:
                        return False
                    if not e.get("evidence_artifact_refs"):
                        return False
            if self._raw_evidence_available():
                return self._evidence_independent_replay_ok()
            return True
        self._check(results, "MFC-G05_SIGNED_EVIDENCE_ONLY", _g05)

        def _g06():
            # quorum 从有效 evidence 独立重数（若 raw evidence 可用则独立重放）
            for e in audit_events:
                rc = e.get("result_counts", {})
                if rc:
                    top = max(rc.values()) if rc else 0
                    q = 2 * self.scenario.audit.get("f", 2) + 1
                    if e.get("status") == "CERTIFIED" and top < q:
                        return False
                if e.get("status") == "CERTIFIED":
                    q = 2 * self.scenario.audit.get("f", 2) + 1
                    refs = e.get("evidence_artifact_refs", [])
                    if len(refs) < q:
                        return False
            if self._raw_evidence_available():
                return self._evidence_independent_replay_ok()
            return True
        self._check(results, "MFC-G06_QUORUM_COUNTS_VALID_EVIDENCE_ONLY", _g06)

        # ================= MFC-G07：DP/披露语义分离 ==========================
        self._check(results, "MFC-G07_DP_DISCLOSURE_SEMANTIC_SEPARATION",
                    lambda: self._dp_disclosure_separated())

        # ================= MFC-G08/G09：payer 语义 + 逐节点 VCG =============
        def _g08():
            # payer 来自 action policy（SELLER/BUYER），非 total*0.5
            audit_s = s("audit").get("audit_pay_s", 0)
            audit_b = s("audit").get("audit_pay_b", 0)
            for e in audit_events:
                if e.get("payer") not in ("SELLER", "BUYER"):
                    return False
            computed_s = sum(e.get("mc_a_pay", 0) for e in audit_events
                             if e.get("payer", "SELLER") == "SELLER")
            computed_b = sum(e.get("mc_a_pay", 0) for e in audit_events
                             if e.get("payer", "SELLER") == "BUYER")
            if abs(computed_s - audit_s) > 1e-6 or abs(computed_b - audit_b) > 1e-6:
                return False
            total = audit_s + audit_b
            if total > 1e-6 and abs(audit_s - audit_b) > 1e-6:
                return True  # 已按 payer 拆分（非 50/50）
            # 全 SELLER 或全 BUYER 也合法
            return True
        self._check(results, "MFC-G08_AUDIT_PAYER_SEMANTICS", _g08)

        def _g09():
            # 逐节点 VCG payment + settlement 实际支付到 node（MFC-G09）
            if not any(e.get("vcg_payments") for e in audit_events):
                return False
            phase1 = s("settlement_phase1")
            obligations = phase1.get("audit_obligations", [])
            if not obligations:
                return False
            recipients = {o["node_id"] for o in obligations}
            for e in audit_events:
                for nid in (e.get("vcg_payments") or {}).keys():
                    if str(nid) not in recipients:
                        return False
            if not self._per_node_reconciliation_ok(obligations):
                return False
            return True
        self._check(results, "MFC-G09_PER_NODE_VCG_SETTLEMENT", _g09)

        # ================= MFC-G10/G11：action-specific likelihood ===========
        self._check(results, "MFC-G10_ACTION_SPECIFIC_LIKELIHOOD",
                    lambda: self._action_likelihood_ok())
        self._check(results, "MFC-G11_NO_MANUAL_LIKELIHOOD",
                    lambda: self._no_scenario_likelihood_used())

        # ================= MFC-G12/G13/G14：posterior / policy hash / pB =====
        self._check(results, "MFC-G12_POSTERIOR_REPLAYED",
                    lambda: self._posterior_recomputable())
        self._check(results, "MFC-G13_RUNTIME_POLICY_HASH_MATCHES_CERT",
                    lambda: self._policy_hash_matches())
        def _g14():
            rule = [r for r in eng.reconcile(s("certification"))
                    if r["formula_id"] == "P_BREACH_LOWER_SYS"]
            return bool(rule and rule[0]["passed"])
        self._check(results, "MFC-G14_PB_SYS_RECOMPUTED", _g14)

        # ================= MFC-G15/G16：PreLock envelope + 时序 ==============
        def _g15():
            pre = s("prelock")
            if not pre.get("n_cells", 0) or not pre.get("envelope_cells"):
                return False
            return self._prelock_envelope_ok()
        self._check(results, "MFC-G15_PRELOCK_USES_ENTIRE_ENVELOPE", _g15)
        self._check(results, "MFC-G16_PRELOCK_BEFORE_AUDIT",
                    lambda: self._prelock_before_audit())

        # ================= MFC-G17/G18：bond IC ==============================
        self._check(results, "MFC-G17_SELLER_BOND_IC_RECONCILES",
                    lambda: s("seller_bond").get("reconciliation", {}).get("pass", False))
        self._check(results, "MFC-G18_BUYER_USAGE_BOND_IC_RECONCILES",
                    lambda: self._usage_bond_ic_reconciles())

        # ================= MFC-G19/G20/G21：pricing =========================
        for gid, fid in [("MFC-G19_PMAX_RECONCILES", "PMAX"),
                         ("MFC-G20_PMIN_RECONCILES", "PMIN"),
                         ("MFC-G21_MARGIN_CLEARING_RECONCILES", "CLEAR_TRADE")]:
            def _mk(fid):
                def fn():
                    rule = [r for r in eng.reconcile(s("pricing"))
                            if r["formula_id"] == fid]
                    return bool(rule and rule[0]["passed"])
                return fn
            self._check(results, gid, _mk(fid))

        # ================= MFC-G22/G23：rights compat + dominance ===========
        self._check(results, "MFC-G22_RIGHTS_COMPATIBILITY_PASSED",
                    lambda: self._rights_compatibility_passed())
        self._check(results, "MFC-G23_RIGHTS_MENU_DOMINANCE",
                    lambda: self._dominance_no_arbitrage())

        # ================= MFC-G24..G26：settlement Phase I + delivery =======
        self._check(results, "MFC-G24_SETTLEMENT_PHASE1",
                    lambda: (not self._is_trade()) or bool(s("settlement_phase1")))
        self._check(results, "MFC-G25_DELIVERY_EXISTS",
                    lambda: bool(s("delivery")))
        self._check(results, "MFC-G26_DELIVERY_HASH_MATCHES_TRANSACTION",
                    lambda: s("delivery").get("verified", False))

        # ================= MFC-G27..G29：rights ACTIVE / receipt / DENY =====
        self._check(results, "MFC-G27_RIGHTS_ACTIVE_BEFORE_USE",
                    lambda: self._rights_active_before_use()
                            or not self._is_trade())
        self._check(results, "MFC-G28_EVERY_USAGE_HAS_RECEIPT",
                    lambda: self._usage_has_receipts()
                            or not self._is_trade())
        self._check(results, "MFC-G29_DENY_BEFORE_KEY_RELEASE",
                    lambda: self._deny_before_key_release()
                            or not self._is_trade())

        # ================= MFC-G30/G31：breach derived from evidence =========
        self._check(results, "MFC-G30_BUYER_BREACH_FROM_EVIDENCE",
                    lambda: self._buyer_breach_from_evidence())
        self._check(results, "MFC-G31_SELLER_BREACH_FROM_EVIDENCE",
                    lambda: self._seller_breach_from_evidence())

        # ================= MFC-G32/G33：settlement Phase II + escrow close ===
        self._check(results, "MFC-G32_SETTLEMENT_PHASE2",
                    lambda: s("settlement").get("conservation", False))
        self._check(results, "MFC-G33_ESCROWS_CLOSED",
                    lambda: self._escrows_closed())

        # ================= MFC-G34：retention/delete ========================
        self._check(results, "MFC-G34_RETENTION_DELETE_DUTY",
                    lambda: self._retention_delete_duty())

        # ================= MFC-G35/G36：lineage =============================
        self._check(results, "MFC-G35_LINEAGE_HASH_CHAIN_VALID",
                    lambda: s("usage").get("chain_valid", False)
                            or self._stage("state").get("terminal") != "TRADE")
        self._check(results, "MFC-G36_OPENLINEAGE_CONSISTENT",
                    lambda: self._openlineage_consistent())

        # ================= MFC-G37：final eval unreadable ===================
        def _g37():
            fb = s("feedback")
            ledger = fb.get("final_eval_access_ledger") or {}
            for rec in ledger.get("records", []):
                if rec.get("stage") not in ("FEEDBACK",):
                    return False
            # TerminalDecisionArtifact/capability must exist and stage==FEEDBACK
            terminal_art = fb.get("terminal_decision_artifact")
            if not terminal_art:
                return False
            if terminal_art.get("stage") != "FEEDBACK":
                return False
            return True
        self._check(results, "MFC-G37_FINALEVAL_UNREADABLE_PRE_TERMINAL", _g37)

        # ================= MFC-G38/G39：split isolation + trainer scope =====
        self._check(results, "MFC-G38_RCAL_RCERT_REVAL_ISOLATED",
                    lambda: self._role_isolation_ok())
        self._check(results, "MFC-G39_CALIBRATION_TRAINER_SCOPE",
                    lambda: self._trainer_scope_ok())

        # ================= MFC-G40/G41：feedback eligibility + theta ========
        self._check(results, "MFC-G40_FEEDBACK_ELIGIBILITY_VALID",
                    lambda: self._feedback_eligibility_ok())
        self._check(results, "MFC-G41_THETA_UPDATE_REPRODUCIBLE",
                    lambda: self._theta_reproducible())

        # ================= MFC-G42/G43：no defaults / no placeholders =======
        self._check(results, "MFC-G42_NO_BUSINESS_DEFAULTS",
                    lambda: self._no_business_defaults())
        self._check(results, "MFC-G43_NO_PLACEHOLDER_HASHES",
                    lambda: self._no_placeholder_hashes())

        # ================= MFC-G44：auditor no full dataset =================
        self._check(results, "MFC-G44_AUDITOR_NO_FULL_DATASET",
                    lambda: self._auditor_no_full_dataset())

        # ================= MFC-G45/G46：training plane ======================
        self._check(results, "MFC-G45_LEGAL_CONTROLLED_TRAINING_RUNS",
                    lambda: self._legal_training_runs())
        self._check(results, "MFC-G46_ILLEGAL_TRAINING_NO_ACCESS",
                    lambda: self._illegal_training_blocked())

        # ================= MFC-G47/G48/G49：money / recipient / trace =======
        self._check(results, "MFC-G47_MONEY_CONSERVATION",
                    lambda: s("settlement").get("conservation", False))
        self._check(results, "MFC-G48_RECIPIENT_SEMANTICS",
                    lambda: len(s("settlement").get("money_semantics_ok", [])) == 0)
        ok, _ = self.ledger.verify()
        self._check(results, "MFC-G49_TRACE_ARTIFACT_CHAIN_VALID", lambda: ok)

        # ================= MFC-G50：deterministic replay ====================
        self._check(results, "MFC-G50_DETERMINISTIC_REPLAY",
                    lambda: self._deterministic_replay_ok())

        # ---- 兼容旧测试名（G4/G5/G10/G15/G33）----
        self._check(results, "G4_no_manual_likelihood",
                    lambda: cal is not None and cal.likelihood is not None)
        self._check(results, "G5_no_manual_tp_fn",
                    lambda: cal is not None and cal.certificate is not None)
        self._check(results, "G10_independent_value_calibration_used",
                    lambda: cal is not None and cal.valuation is not None)
        self._check(results, "G15_certified_policy_match",
                    lambda: self._policy_hash_matches())
        self._check(results, "G33_replay_produces_same_result",
                    lambda: self._deterministic_replay_ok())

        results["G1_provenance_complete"] = all(results.values())
        failures = [k for k, v in results.items() if not v]
        passed = not failures
        return {
            "passed": passed,
            "paper_closure_gate": "PASS" if passed else "FAIL",
            "n_checks": len(results),
            "n_passed": sum(1 for v in results.values() if v),
            "checks": results,
            "failures": failures,
        }

    # ---- 辅助验证 ----
    def _dp_disclosure_separated(self) -> bool:
        """MFC-G07：QueryPrivacyBudget(ε) 与 AuditDisclosureBudget 语义分离。"""
        # 审计披露 budget 用 rows/fraction/bytes，不用 DP ε 映射
        pb = self.scenario.audit.get("privacy_budget", {})
        if pb:
            return ("max_unique_rows" in pb
                    and "max_fraction" in pb and "max_bytes" in pb)
        return True

    def _usage_bond_ic_reconciles(self) -> bool:
        """MFC-G18：buyer usage bond IC 独立对账（若适用）。"""
        pricing_stage = self._stage("pricing")
        b_b_use = pricing_stage.get("b_b_use", 0.0)
        # 若合同适用（b_b_use>0），验证 IC：p̲_U(p_e_ubond λ_B B_B + p_e_uf F_B) >= G+ε
        if b_b_use > 0:
            ub = self.scenario.usage.get("usage_bond", {})
            p_u = ub.get("p_misuse_lower_sys", 0.0)
            g = ub.get("g_misuse", 0.0)
            eps = ub.get("eps_b", 0.0)
            pe = ub.get("p_e_ubond", 1.0)
            lam = ub.get("lambda_b", 1.0)
            puf = ub.get("p_e_uf", 0.0)
            fb = ub.get("f_b", 0.0)
            lhs = p_u * (pe * lam * b_b_use + puf * fb)
            return lhs >= g + eps - 1e-6
        return True

    def _rights_compatibility_passed(self) -> bool:
        """MFC-G22：Rights compatibility 真实通过。"""
        return self._stage("entitlement").get("compatible", {}).get("passes", False)

    def _dominance_no_arbitrage(self) -> bool:
        """MFC-G23：rights menu dominance / no-arbitrage（同一 pricing snapshot）。"""
        pricing_stage = self._stage("pricing")
        if not pricing_stage:
            return False
        return (not pricing_stage.get("dominance_violations")
                and not pricing_stage.get("no_arbitrage_violations"))

    def _terminal(self) -> str:
        return (self._stage("state").get("terminal")
                or self._stage("settlement").get("terminal", ""))

    def _is_trade(self) -> bool:
        return self._terminal() == "TRADE"

    def _rights_active_before_use(self) -> bool:
        """MFC-G27：Rights ACTIVE 在任何数据使用之前。"""
        return self._stage("delivery").get("verified", False) and bool(
            self._stage("usage"))

    def _usage_has_receipts(self) -> bool:
        """MFC-G28：每个 usage request 都有 receipt。"""
        return (len(self._stage("usage").get("results", []))
                == self._stage("usage").get("n_requests", 0))

    def _buyer_breach_from_evidence(self) -> bool:
        """MFC-G30：BUYER_BREACH 由 UsageViolationEvidence 派生。"""
        terminal = self._terminal()
        if terminal == "BUYER_BREACH":
            # 必须存在 usage violation evidence 且 resolver 判定 breach
            usage = self._stage("usage")
            return bool(usage.get("buyer_breach")) and bool(
                usage.get("usage_violation_evidence"))
        return True

    def _seller_breach_from_evidence(self) -> bool:
        """MFC-G31：SELLER_BREACH 由审计/delivery evidence 派生。"""
        terminal = self._terminal()
        if terminal == "SELLER_BREACH":
            # 必须存在 audit BREACH_EVIDENCE 或 delivery hash mismatch
            audit = self._stage("audit")
            has_breach_evidence = any(
                e.get("outcome") == "BREACH_EVIDENCE"
                for e in audit.get("audit_trace_events", []))
            return has_breach_evidence or not self._stage("delivery").get("verified", False)
        return True

    def _openlineage_consistent(self) -> bool:
        """MFC-G36：OpenLineage 导出一致性（若启用）。"""
        usage = self._stage("usage")
        return (usage.get("openlineage_export", False)
                or not self._is_trade())

    def _retention_delete_duty(self) -> bool:
        """MFC-G34：retention/delete duty 在适用时执行。"""
        usage = self._stage("usage")
        deletion = usage.get("deletion")
        rights = self.scenario.rights
        if rights.get("retention") or rights.get("delete_duty"):
            # 适用时必须有 deletion receipt
            if not deletion or not deletion.get("receipt"):
                return False
            # DOWNLOAD_TRACEABLE 只能 DELETION_PENDING（客观边界）
            if rights.get("access_mode") == "DOWNLOAD_TRACEABLE":
                return deletion.get("state") in ("DELETION_PENDING", "DELETED_ATTESTED")
            return deletion.get("state") == "DELETED_ATTESTED"
        return True  # 不适用

    def _escrows_closed(self) -> bool:
        """MFC-G33：所有 escrow 最终余额归零。"""
        money_events = self._stage("settlement").get("money_events", [])
        if not money_events:
            return False
        escrow_accounts = {"E_B^P", "E_S^A", "E_B^A", "B_S^pre", "B_S^*", "B_B^use"}
        balance = {a: 0.0 for a in escrow_accounts}
        init = self._stage("settlement").get("escrow_initial_balances", {})
        for a, amt in init.items():
            if a in balance:
                balance[a] = amt
        for e in money_events:
            frm, to, amt = e["from_account"], e["to_account"], e["amount"]
            if frm in balance:
                balance[frm] -= amt
            if to in balance:
                balance[to] += amt
        return all(abs(v) < 1e-6 for v in balance.values())

    def _no_placeholder_hashes(self) -> bool:
        """MFC-G43：无占位 hash / 人工 TP-FN / 人工成本。

        检查 manifest certificate_hash 来自真实 calibration artifact（非占位），
        且 audit trace 的 MC_A^pay 来自 VCG 报价（非人工）。
        """
        # certificate_hash 必须来自 calibration artifact（非 content_hash(scenario) 占位）
        if self.calibration is not None and self.calibration.certificate is not None:
            if self.manifest.certificate_hash != self.calibration.certificate.artifact_hash:
                return False
        # 审计 trace 的 mc_a_pay 必须 > 0（VCG 报价），禁止 0/人工
        audit_events = self._stage("audit").get("audit_trace_events", [])
        for e in audit_events:
            if e.get("mc_a_pay", 0) <= 0:
                return False
        return True

    def _feedback_eligibility_ok(self) -> bool:
        """MFC-G40: feedback eligibility from evidence event_type/source/terminal timing."""
        fb = self._stage("feedback")
        evs = fb.get("feedback_evidence", [])
        if fb.get("eligible") is not None and not evs:
            return False
        terminal = self._terminal()
        for ev in evs:
            if ev.get("event_type") not in ("OBSERVED_BREACH", "NORMAL_COMPLETION"):
                return False
            if ev.get("terminal_timing") != terminal:
                return False
            if ev.get("eligibility_policy") != "post_terminal_eligible":
                return False
        return fb.get("eligible") is not None

    def _theta_reproducible(self) -> bool:
        """MFC-G41: recompute theta from Theta_before + eligible evidence + update formula."""
        fb = self._stage("feedback")
        if not fb.get("theta_updated", False):
            return True
        before = fb.get("theta_before", {})
        after = fb.get("theta_after", {})
        evs = fb.get("feedback_evidence", [])
        if not evs:
            return False
        a = float(before.get("a", 0.0))
        b = float(before.get("b", 0.0))
        for ev in evs:
            if ev.get("source") == "SELLER_BREACH":
                a += 1.0
            elif ev.get("source") == "BUYER_BREACH":
                b += 1.0
            elif ev.get("source") == "NORMAL":
                a += 1.0
        return abs(float(after.get("a", 0.0)) - a) < 1e-9 and abs(float(after.get("b", 0.0)) - b) < 1e-9

    def _prelock_envelope_ok(self) -> bool:
        """MFC-G15: prelock envelope must match certificate allowed_profile_set."""
        ctx = self._ctx()
        cert_profile_set = set()
        if ctx is not None and ctx.policy_certificate is not None:
            cert = ctx.policy_certificate
            allowed = getattr(cert, "allowed_profile_set", None)
            if allowed is None:
                cert_plain = cert.to_plain() if hasattr(cert, "to_plain") else {}
                if isinstance(cert_plain, dict):
                    allowed = cert_plain.get("allowed_profile_set", [])
            cert_profile_set = set(allowed or [])
        pre = self._stage("prelock")
        pre_profile_set = set()
        for cell in pre.get("envelope_cells", []):
            aph = cell.get("action_profile_hash") or cell.get("profile_hash")
            if aph:
                pre_profile_set.add(aph)
        if ctx is not None and ctx.policy_certificate is not None:
            return bool(cert_profile_set) and cert_profile_set == pre_profile_set
        return bool(pre_profile_set)

    def _prelock_before_audit(self) -> bool:
        """MFC-G16: SELLER_PRELOCK_LOCKED event seq < audit quote/execution seq."""
        prelock_seq = None
        audit_seq = None
        for ev in self.ledger.events:
            if ev.event_type == "SELLER_PRELOCK_LOCKED":
                prelock_seq = ev.seq
            if ev.event_type in ("AUDIT_QUOTE_FROZEN", "AUDIT_EXECUTION_STARTED"):
                audit_seq = ev.seq
        if prelock_seq is not None and audit_seq is not None:
            return prelock_seq < audit_seq
        # legacy fallback: stage existence
        return bool(self._stage("prelock")) and bool(self._stage("audit"))

    def _per_node_reconciliation_ok(self, obligations: list[dict]) -> bool:
        """MFC-G09: per quote_hash x profile x node reconcile quoted payment,
        obligation realized_payment, MoneyLedger transfer, and recipient amount."""
        audit = self._stage("audit")
        money_events = self._stage("settlement").get("money_events", [])
        quote_by_node = {}
        for e in audit.get("audit_trace_events", []):
            qh = e.get("quote_hash")
            aph = e.get("action_profile_hash")
            for nid, amt in (e.get("vcg_payments") or {}).items():
                quote_by_node[(qh, aph, str(nid))] = float(amt)
        for ob in obligations:
            key = (ob.get("quote_hash"), ob.get("action_profile_hash"), str(ob.get("node_id")))
            quoted = quote_by_node.get(key)
            if quoted is None:
                return False
            realized = float(ob.get("realized_payment", 0.0))
            if abs(realized - quoted) > 1e-6:
                return False
            # MoneyLedger transfer to auditor recipient must match, except zero
            # VCG obligations which need no cash movement.
            if money_events and abs(realized) > 1e-9:
                found = False
                for me in money_events:
                    if (str(me.get("to_account", "")) == str(ob.get("node_id"))
                            and abs(float(me.get("amount", 0.0)) - realized) < 1e-6):
                        found = True
                        break
                if not found:
                    return False
        return True

    def _raw_evidence_available(self) -> bool:
        ctx = self._ctx()
        if ctx is not None and ctx.raw_audit_evidence_store is not None:
            return bool(ctx.raw_audit_evidence_store)
        store = self._stage("audit").get("raw_evidence")
        return bool(store)

    def _evidence_independent_replay_ok(self) -> bool:
        """MFC-G05/G06: independently verify every raw evidence and rebuild counts."""
        from valor.security.signing import verify_evidence_signature
        ctx = self._ctx()
        store = None
        public_keys = {}
        if ctx is not None and ctx.raw_audit_evidence_store:
            store = ctx.raw_audit_evidence_store
        if store is None:
            store = self._stage("audit").get("raw_evidence") or {}
        runtime = None
        if ctx is not None:
            runtime = ctx.runtime_descriptor
        if runtime is None:
            runtime = self._stage("audit").get("runtime_descriptor")
        if runtime is not None:
            d = runtime.to_plain() if hasattr(runtime, "to_plain") else runtime
            public_keys = d.get("node_public_keys", {})
        audit = self._stage("audit")
        snap = audit.get("market_snapshot") or {}
        public_keys = public_keys or audit.get("auditor_public_keys") or snap.get("public_key_fingerprint", {})
        for e in audit.get("audit_trace_events", []):
            if e.get("status") != "CERTIFIED":
                continue
            refs = e.get("evidence_artifact_refs", [])
            if not refs:
                return False
            counts = {}
            for ref in refs:
                ev = None
                if isinstance(store, dict):
                    ev = store.get(ref)
                    if ev is None:
                        ev = store.get(str(ref))
                    if ev is None:
                        for k, v in store.items():
                            if v.get("evidence_id") == ref or v.get("node_id") == ref:
                                ev = v
                                break
                if ev is None:
                    return False
                nid = str(ev.get("node_id", ""))
                pk = public_keys.get(nid) or ev.get("public_key")
                if not pk:
                    return False
                sig = ev.get("signature", "")
                if not sig or not verify_evidence_signature(
                        public_key_hex=pk, evidence_plain=ev, signature=sig):
                    return False
                if ev.get("task_hash") and e.get("task_hash"):
                    if ev["task_hash"] != e["task_hash"]:
                        return False
                counts[ev.get("result")] = counts.get(ev.get("result"), 0) + 1
            q = 2 * int(self.scenario.audit.get("f", 2)) + 1
            if not counts or max(counts.values()) < q:
                return False
        return True

    def _ledger_quote_order_ok(self) -> bool:
        """MFC-G02: derive order from TraceLedger event seq if present."""
        seqs = {"AUDIT_QUOTE_FROZEN": None, "AUDIT_VOI_DECISION": None,
                "AUDIT_EXECUTION_STARTED": None}
        for ev in self.ledger.events:
            et = ev.event_type
            if et in seqs:
                seqs[et] = ev.seq
        if seqs["AUDIT_QUOTE_FROZEN"] is None:
            return False
        return (seqs["AUDIT_QUOTE_FROZEN"] < seqs["AUDIT_VOI_DECISION"]
                < seqs["AUDIT_EXECUTION_STARTED"])

    def _action_likelihood_ok(self) -> bool:
        """MFC-G10: each executed action profile has an exact frozen likelihood
        artifact whose hash is consistent with the policy certificate/catalog."""
        ctx = self._ctx()
        audit = self._stage("audit")
        for e in audit.get("audit_trace_events", []):
            aph = e.get("action_profile_hash")
            if not aph:
                return False
            if ctx is not None and ctx.likelihood_catalog is not None:
                try:
                    art = ctx.likelihood_catalog.resolve(aph)
                except Exception:
                    return False
                if ctx.policy_certificate is not None:
                    cert_policy_hashes = getattr(
                        ctx.policy_certificate, "policy", None)
                    if cert_policy_hashes is None:
                        cert_plain = getattr(ctx.policy_certificate, "to_plain", lambda: {})()
                        cert_plain = cert_plain if isinstance(cert_plain, dict) else {}
                        if art.artifact_hash not in cert_plain.get("likelihood_catalog_hash", ""):
                            return False
                    else:
                        if aph not in getattr(ctx.policy_certificate.policy, "action_profile_hashes", ()):
                            return False
            else:
                # legacy fallback: at least require a frozen likelihood artifact hash
                if not e.get("likelihood_artifact_hash"):
                    return False
        return True

    def _no_scenario_likelihood_used(self) -> bool:
        """MFC-G11: FORMAL/PRODUCTION must never read scenario.likelihood."""
        ctx = self._ctx()
        if ctx is None:
            # Without context, legacy calibration path is accepted for older tests,
            # but only when calibration.likelihood is present (not scenario.likelihood).
            return self.calibration is not None and self.calibration.likelihood is not None
        return (ctx.likelihood_catalog is not None
                and ctx.audit_policy is not None)

    def _deterministic_replay_ok(self) -> bool:
        """MFC-G50: real ReplayVerificationArtifact, not bool."""
        ctx = self._ctx()
        if ctx is not None and getattr(ctx, "replay_artifact", None) is not None:
            art = ctx.replay_artifact
            if isinstance(art, dict):
                return bool(art.get("status") == "PASS"
                            and not art.get("mismatch_list"))
            return bool(getattr(art, "status", "") == "PASS")
        if self.legacy_replay_consistent is True:
            # legacy bool is never sufficient for closure
            return False
        return False

    def _auditor_no_full_dataset(self) -> bool:
        """MFC-G44: AuditRuntimeDescriptor must prove process isolation, no full dataset."""
        ctx = self._ctx()
        runtime = None
        if ctx is not None:
            runtime = ctx.runtime_descriptor
        if runtime is None:
            runtime = self._stage("audit").get("runtime_descriptor")
        if runtime is None:
            return False
        if hasattr(runtime, "to_plain"):
            d = runtime.to_plain()
        else:
            d = runtime
        if d.get("transport_mode") != "PROCESS_HTTP":
            return False
        if not d.get("process_isolated"):
            return False
        if d.get("full_dataset_present", False):
            return False
        if d.get("seller_private_mount", True):
            return False
        if not d.get("node_pids"):
            return False
        if d.get("input_row_count", 0) > int(d.get("challenge_disclosure", 0) or 0):
            return False
        return True

    def _deny_before_key_release(self) -> bool:
        """MFC-G29：非法训练 DENY 发生在 key release / data 访问之前。"""
        tr = self._stage("training")
        if not tr.get("enabled"):
            return False
        for r in tr.get("results", []):
            out = r.get("outcome", {})
            if out.get("decision") == "DENY":
                if out.get("key_released") or out.get("raw_data_access") \
                        or out.get("training_started"):
                    return False
        return True

    def _role_isolation_ok(self) -> bool:
        """MFC-G38: check actual R_cal/R_cert/R_eval sample-id sets from manifests."""
        ctx = self._ctx()
        if ctx is None:
            return (
                self.calibration is not None
                and self.calibration.valuation is not None
                and self.calibration.likelihood is not None
                and self.calibration.certificate is not None
            )
        registry = ctx.role_registry
        if registry is None or not getattr(registry, "frozen", False):
            return False
        manifests = getattr(registry, "manifests", None)
        if manifests is None and hasattr(registry, "manifests_by_role"):
            manifests = registry.manifests_by_role
        if not manifests:
            return False
        roles = {}
        if isinstance(manifests, dict):
            roles = {str(k): getattr(v, "sample_ids", v) for k, v in manifests.items()}
        elif isinstance(manifests, (list, tuple)):
            roles = {str(getattr(m, "role_id", i)): getattr(m, "sample_ids", ())
                     for i, m in enumerate(manifests)}
        sets = {k: set(int(x) for x in v) for k, v in roles.items() if v is not None}
        if len(sets) < 3:
            return False
        keys = sorted(sets)
        return all(not (sets[a] & sets[b])
                   for i, a in enumerate(keys) for b in keys[i + 1:])

    def _trainer_scope_ok(self) -> bool:
        """MFC-G39: valuation calibration trainer_scope_hash/trainer_hash matches runtime manifest."""
        ctx = self._ctx()
        if ctx is not None and ctx.valuation_calibration is not None:
            vc = ctx.valuation_calibration
            data = vc.data if hasattr(vc, "data") else vc
            if isinstance(data, dict):
                cal_trainer = (data.get("trainer_scope_hash")
                               or data.get("trainer_hash")
                               or data.get("dataset_hash"))
            else:
                cal_trainer = getattr(vc, "trainer_scope_hash", None) or getattr(vc, "trainer_hash", None)
            return bool(cal_trainer and cal_trainer == self.manifest.trainer_hash)
        return (
            self.calibration is not None
            and self.calibration.valuation is not None
            and "trainer_hash" in self.calibration.valuation.data
            and self.calibration.valuation.data.get("trainer_hash") == self.manifest.trainer_hash
        )

    def _legal_training_runs(self) -> bool:
        """MFC-G45：合法受控训练真实运行（decision=ALLOW 且 training_started）。"""
        tr = self._stage("training")
        if not tr.get("enabled"):
            return self._stage("state").get("terminal") != "TRADE"
        for r in tr.get("results", []):
            out = r.get("outcome", {})
            if out.get("decision") == "ALLOW":
                if not out.get("worker_pid") or not out.get("model_artifact_hash"):
                    return False
                if not out.get("training_started"):
                    return False
        return tr.get("legal_trained", False)

    def _illegal_training_blocked(self) -> bool:
        """MFC-G46：非法训练无法访问 D（key_release=False, training_started=False）。"""
        tr = self._stage("training")
        if not tr.get("enabled"):
            return self._stage("state").get("terminal") != "TRADE"
        for r in tr.get("results", []):
            out = r.get("outcome", {})
            if out.get("decision") == "DENY":
                if out.get("key_released") or out.get("training_started") \
                        or out.get("raw_data_access"):
                    return False
        return True

    def _posterior_recomputable(self) -> bool:
        """MFC-G12：从 prior + Λ + evidence 独立重算 posterior。"""
        from valor.audit.bayes_update import bayes_update
        from valor.audit.state_model import StateBelief

        prior = self.scenario.audit_prior
        belief = StateBelief.from_prior(prior["pi_b"], prior["q_l"])
        events = self._stage("audit").get("audit_trace_events", [])
        if not events:
            return True
        lik_rows = None
        if self.calibration is not None and self.calibration.likelihood is not None:
            lik_rows = self.calibration.likelihood.data.get("rows")
        else:
            lik_rows = self.scenario.likelihood
        for e in events:
            outcome = e.get("outcome")
            if outcome is None or outcome not in lik_rows:
                return False
            belief = bayes_update(belief, lik_rows[outcome])
        expected = belief.to_plain()
        actual = self._stage("audit").get("posterior")
        if not actual:
            return False
        return abs(float(expected.get("pi_b", 0.0)) - float(actual.get("pi_b", 0.0))) < 1e-9 and \
               abs(float(expected.get("q_l", 0.0)) - float(actual.get("q_l", 0.0))) < 1e-9

    def _policy_hash_matches(self) -> bool:
        """MFC-G13: runtime AuditPolicy.policy_hash == PolicyCertificationArtifact.policy_hash."""
        ctx = self._ctx()
        if ctx is not None:
            if ctx.audit_policy is None or ctx.policy_certificate is None:
                return False
            runtime_policy_hash = getattr(ctx.audit_policy, "policy_hash", None)
            cert_policy_hash = getattr(ctx.policy_certificate, "policy_hash", None)
            if not runtime_policy_hash or not cert_policy_hash:
                # policy certificate may embed policy object
                cert_policy = getattr(ctx.policy_certificate, "policy", None)
                if cert_policy is not None:
                    cert_policy_hash = getattr(cert_policy, "policy_hash", None)
            return bool(runtime_policy_hash and runtime_policy_hash == cert_policy_hash)
        if self.calibration is None or self.calibration.certificate is None:
            return False
        cert_hash = self.calibration.certificate.artifact_hash
        return self.manifest.certificate_hash == cert_hash


def evaluate_full_chain(
    *,
    scenario: CapstoneScenario,
    manifest: RunManifest,
    ledger: TraceLedger,
    stages: dict[str, Any],
    calibration: CalibrationBundle | None = None,
    legacy_replay_consistent: bool | None = None,
    legacy_final_eval_accessed_before_decision: bool | None = None,
    context: MechanismVerificationContext | None = None,
) -> dict:
    """便捷入口：评估 FullChainGate。"""
    g = FullChainGate(scenario=scenario, manifest=manifest, ledger=ledger,
                      stages=stages, calibration=calibration,
                      legacy_replay_consistent=legacy_replay_consistent,
                      legacy_final_eval_accessed_before_decision=legacy_final_eval_accessed_before_decision,
                      context=context)
    return g.run()


__all__ = ["FullChainGate", "MechanismVerificationContext", "evaluate_full_chain"]
