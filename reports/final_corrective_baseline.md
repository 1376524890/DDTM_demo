# VALOR-v1 Final Corrective Baseline

Generated at: 2026-08-18T09:45:00+08:00

## Repository State

- Branch: `VALOR-v1`
- HEAD: `0e93f685948f91b018740a4f17e76015455e1a13`
- Worktree: not clean; untracked `AGENTS.md` only (created as contributor guide, not part of this corrective baseline).
- Design truth: `VALOR_可实施原型系统_完整数学代码闭环与开发规范.md`
- Design truth SHA-256: `d72fcb402fc3d50ecac52eabec0c5ba61c40f75a450caef01fe65175baab6a97`

## Environment

- Python: 3.14.6 (`.venv`)
- pytest: 9.1.1
- Dependency environment: `.venv` with project installed editable (`valor 0.2.0`).
- Note: `.venv` cryptography was downgraded from 50.0.0 to 49.0.0 because the installed 50.0.0 wheel requires GLIBC_2.33 while this host provides GLIBC 2.31.

## Baseline Commands

| Command | Result |
|---|---|
| `git status --short` | `?? AGENTS.md` |
| `python scripts/check_business_defaults.py --root valor` | exit 0, “未发现业务默认值。” |
| `python scripts/check_forbidden_patterns.py --root valor` | exit 0, “未发现禁止模式（200 文件）” |
| `pytest -q` (first run) | 265 passed, 229 warnings, 1594.41s |
| `python scripts/reverse_self_audit.py` | exit 0, `REVERSE_SELF_AUDIT: PASS`; log at `reports/verification/reverse_audit_baseline.txt`. Note: this PASS includes `_E_auditor_no_full_data` returning True with “架构保证”, so it is not trustworthy as closure evidence. |
| `pytest -q` (log capture) | summary persisted to `reports/verification/pytest_baseline.txt`; full raw log not captured on first run. |

## FullChainGate / Coverage Baseline

The existing `reports/mechanism_coverage.json` claims 44/44 mechanisms IMPLEMENTED and `reports/final_closure_report.md` claims `paper_mechanism_closure=PASS`, but those reports are manually authored and stale: they reference an older HEAD (`1015677`) and do not reflect the current HEAD `0e93f68`. They also do not contain mutation-test evidence or machine-generated provenance.

## P0 Issue Inventory

All issues are currently classified as **OPEN** until the corrective phases produce machine-verifiable evidence. None are marked `VERIFIED_ALREADY_FIXED` because every listed invariant still has at least one observed shortcut or unverified path in production code.

| ID | Title | Status | Evidence |
|---|---|---|---|
| P0-A | Canonical DatasetCommitment unified | OPEN | `audit_executor.py` still sets `TaskEnvelope.data_commitment=ctx["dataset_hash"]` instead of the canonical `commitment_hash`; `privacy_audit` and `distributed` task paths have separate task/task_hash semantics. |
| P0-B | VCG quote strictly before VOI choose | OPEN | `PrivacyAuditVOIExecutor` uses hardcoded bids `10.0 + i` instead of an injected market snapshot; `DistributedAuditExecutor` uses fixed `quote_time == execution_time` and no logical `quote_seq < voi_decision_seq < execution_seq`. |
| P0-C | Action-specific likelihood bound to full action profile | OPEN | Only a single `a1` action is used in the default executor; `action_profile_hash=content_hash({"action":"a1","family":"quality"})`; likelihood rows fall back to `scenario.likelihood`; no full `AuditActionProfile` binding. |
| P0-D | R_cal runs real distributed audit actions for G/L/B | OPEN | `calibration_runner.py` derives counts from a local `structural` detector, then manually adds `L -> CLAIM_NOT_SUPPORTED` observations; no distributed audit execution, no `role_manifest.json`, no R_cal/R_cert overlap check. |
| P0-E | Independent full-policy R_cert | OPEN | `CalibrationConfig.__post_init__` fills placeholder hashes (`hash("calibration-default")`, `hash("quality-audit")`); certificate is computed from the same detection TP/FN as R_cal; no independent R_cert runs or full policy envelope traversal. |
| P0-F | Signed evidence required before quorum | OPEN | `PrivacyAuditScheduler` counts unsigned evidence when `public_keys` is empty; `DistributedAuditScheduler` path accepts in-process unsigned evidence provider output. |
| P0-G | COMMIT_CHALLENGE privacy audit in transaction mainline | OPEN | Default production executor is `DistributedAuditExecutor` (`generic DistributedAuditScheduler` + in-process provider); `PrivacyAuditScheduler` only runs when explicitly injected in tests. |
| P0-H | DP/query budget vs audit disclosure budget separated semantically | OPEN | `_dp_disclosure_separated` returns True when no budget is configured; no mainline invariant proves semantic separation. |
| P0-I | Entitlement/Compliance provenance + fail closed | OPEN | `_check_entitlement` uses `grant_authority` default True, `buyer_eligible` default True; no `EntitlementEvidence`/`AuthorityRecord`; missing inputs are silently defaulted. |
| P0-J | Seller PreLock uses full certified envelope | OPEN | Envelope falls back to scenario certificate single cell when no calibration; R_cert does not currently certify a full `Ω_allowed`. |
| P0-K | Breach fully derived from observed evidence | OPEN | `audit_executor._breach_evidence_wrapper` forces `BREACH_EVIDENCE` when `sc.seller_breach=True`; feedback TP/FN reads `sc.seller_breach`. |
| P0-L | Delivery independent stage, failure changes terminal | OPEN | Delivery stage exists but returns `terminal_override="SELLER_BREACH"` which is not consumed; delivery failure does not alter terminal before usage/training/settlement. |
| P0-M | Controlled training genuinely isolated | OPEN | `ControlledTrainingRunner._train` runs directly in the orchestrator process with `dataset_X/dataset_y`; `LocalIsolatedProvider` only returns a capability flag, no subprocess/worker; `raw_data_access=False` is self-reported. |
| P0-N | Illegal training rejected before capability release | OPEN | PDP checks exist, but provider can be bypassed by calling `_train` directly; no worker-start evidence; illegal matrix is not enforced by a secure provider. |
| P0-O | Two-phase settlement lifecycle | OPEN | Orchestrator calls single `settle()` before delivery/usage; per-auditor VCG payments are aggregated to `"auditor"`; usage bond can be returned in Phase II before buyer breach is resolved. |
| P0-P | Rights lifecycle ACTIVE after verified delivery | OPEN | Registry registers rights as ACTIVE during entitlement stage; no lifecycle transition from PROPOSED/RESERVED through delivery verified; delivery failure does not keep rights non-ACTIVE. |
| P0-Q | Pricing inputs real provenance | OPEN | `l_comp` read directly from `sc.exposure["l_comp"]`; `OC_S` uses `rev_future_without/with` with fallback to `oc_s` and `oc_s*0.2`; `residual_q` falls back to 0.0 without calibration; capital costs use scenario `t_pre/t_post` instead of ledger timeline. |
| P0-R | FinalEvaluation physically isolated | OPEN | `final_X/final_y` are materialized at the start of `run()` and passed into feedback; there is no `AccessGuard` preventing pre-terminal access. |
| P0-S | Bond capital cost from real timeline; usage bond not silently zero | OPEN | `capital_cost` uses `sc.bond["t_pre"]/["t_post"]`; `_buyer_usage_bond` defaults many usage-bond parameters to 0/1 and returns 0 without explicit `NotApplicableReason`. |
| P0-T | FullChainGate/reverse audit has no false-pass | OPEN | `FullChainGate` has `_role_isolation_ok`/`_trainer_scope_ok` returning True, `delivery.get("verified", True)`, G08 always True, G44 accepts `FULL_DATA_REFERENCE`, G37 checks a flag never set, and `reverse_self_audit._E_auditor_no_full_data` returns True with “架构保证”. |

## Dependency Ordering

1. Canonical commitment + privacy task binding
2. Privacy audit mainline + signatures + process isolation
3. Action profiles + VCG-before-VOI
4. Real R_cal (distributed G/L/B empirical likelihood)
5. Independent R_cert + policy envelope
6. Remove scenario-label/expect leakage
7. Entitlement/compliance/rights lifecycle
8. Two-phase settlement
9. Isolated controlled training
10. FinalEvaluation isolation
11. Pricing input provenance
12. Static scanners (semantic completeness)
13. MechanismInvariantGate + mutation tests
14. Scenario matrix + reverse self-audit rewrite
15. Machine-generated coverage and final reports

## Next Step

Proceed to Phase 2 (canonical commitment + privacy task binding) only after the running reverse self-audit and pytest logs are captured and appended to this baseline.
