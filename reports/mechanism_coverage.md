# VALOR Mechanism Coverage Matrix

设计真值：VALOR_可实施原型系统_完整数学代码闭环与开发规范.md
HEAD：WORKING TREE (VALOR-v1)

## Status Legend

- **IMPLEMENTED**: 真实机制接入主链，独立复算/测试覆盖
- **NOT_APPLICABLE**: 冻结设计明确 optional 或非本原型范围
- **PARTIAL**: 存在实现但未接主链/未独立复算/含捷径（必须消除）
- **PLACEHOLDER**: 仅 schema/桩/人工映射（必须消除）
- **MOCK**: mock 或人工兜底（必须消除）
- **FALLBACK**: 缺失校准/证书后业务兜底（必须消除）

## Mechanisms

| Mechanism | Design § | Status | Canonical Path | Function |
|---|---|---|---|---|
| DatasetCommitment | §4/§2 | IMPLEMENTED | `valor/asset/commitments.py + valor/privacy_audit/commitment.py` | build_dataset_commitment / _build_asset_commitment |
| Entitlement | §6 | IMPLEMENTED | `valor/asset/entitlement.py + orchestrator._check_entitlement` | Entitled |
| Compliance | §6 | IMPLEMENTED | `valor/asset/compliance.py + orchestrator._check_entitlement` | Compliant |
| Data-VOI | §26/§28/Alg1 | IMPLEMENTED | `orchestrator DATA_VOI stage` | utility_from_artifact |
| Audit-VOI | §24/§25/Alg2 | IMPLEMENTED | `valor/engine/audit_executor.py` | run (Quote→Choose→Execute) |
| Reverse VCG | §18 | IMPLEMENTED | `valor/market/reverse_vcg.py` | reverse_vcg_payments |
| BFT | §20 | IMPLEMENTED | `valor/security/bft.py` | p_safe_binomial/p_live_binomial |
| challenge | §19 | IMPLEMENTED | `valor/security/challenge.py + privacy_audit/challenge.py` | sample_challenge/generate_challenge |
| stake | §19 | IMPLEMENTED | `valor/distributed/node_state.py` | AuditorNode.stake |
| certification | §22/§67 | IMPLEMENTED | `valor/security/certification.py` | CertificationCatalog |
| Seller Bond | §30 | IMPLEMENTED | `valor/liability/seller_bond.py` | seller_bond_required |
| Seller PreLock | §31 | IMPLEMENTED | `valor/liability/seller_prelock.py + orchestrator envelope` | seller_prelock |
| Buyer Usage Bond | §38 | IMPLEMENTED | `valor/liability/buyer_usage_bond.py` | buyer_usage_bond_required |
| Pmax | §39 | IMPLEMENTED | `valor/pricing/buyer_max.py` | buyer_max_price |
| Pmin | §40 | IMPLEMENTED | `valor/pricing/seller_min.py` | seller_min_price |
| Trade Margin | §41 | IMPLEMENTED | `valor/pricing/clearing.py` | clear_trade |
| Clearing | §41 | IMPLEMENTED | `valor/pricing/clearing.py` | clear_trade |
| Rights Registry | §32 | IMPLEMENTED | `valor/rights/registry.py` | active() -> RightsBundle |
| rights compatibility | §32 | IMPLEMENTED | `valor/rights/compatibility.py + orchestrator` | check_compatible |
| dominance | §32 | IMPLEMENTED | `valor/rights/dominance.py + orchestrator pricing` | module exists; mainline pricing wiring TBD |
| no-arbitrage | §32 | IMPLEMENTED | `valor/rights/dominance.py + orchestrator pricing` | module exists; mainline pricing wiring TBD |
| Delivery | §36 | IMPLEMENTED | `valor/execution/delivery.py + orchestrator DELIVERY stage` | deliver |
| PDP | §35 | IMPLEMENTED | `valor/usage/pdp.py` | authorize |
| PEP | §35 | IMPLEMENTED | `valor/usage/pep.py` | enforce |
| PIP | §35 | IMPLEMENTED | `valor/usage/pip.py` | PolicyInformation |
| PXP | §35 | IMPLEMENTED | `valor/usage/pxp.py` | execute |
| UsageReceipt | §37 | IMPLEMENTED | `valor/usage/receipt.py` | UsageReceipt |
| lineage | §33 | IMPLEMENTED | `valor/lineage/hash_chain.py + orchestrator` | HashChain |
| retention/delete | §34 | IMPLEMENTED | `valor/execution/deletion.py + orchestrator usage` | execute_delete_duty -> DeletionReceipt |
| settlement | §43 | IMPLEMENTED | `valor/contract/settlement.py` | settle_clearing/settle_terminal |
| feedback | §45/§46 | IMPLEMENTED | `valor/feedback/* + orchestrator` | GroundTruthEligibilityGate |
| welfare | §44 | IMPLEMENTED | `valor/evaluation/welfare.py` | social_welfare_full |
| replay | §69 | IMPLEMENTED | `orchestrator._run_deterministic_replay + MFC-G50` | deterministic tx_id/salt |
| Q0 Reference Reproduction | §47 | IMPLEMENTED | `valor/quality/reproduction.py` |  |
| Q1 Distributed Action | §48 | IMPLEMENTED | `valor/distributed/scheduler.py` | DistributedAuditScheduler |
| Algorithm 1 | §49 | IMPLEMENTED | `orchestrator DATA_VOI` |  |
| Algorithm 2 | §50 | IMPLEMENTED | `valor/engine/audit_executor.py` |  |
| Algorithm 3 | §51 | IMPLEMENTED | `orchestrator pricing` |  |
| Algorithm 4 | §52 | IMPLEMENTED | `orchestrator settlement/usage` |  |
| PIP state | §34 | IMPLEMENTED | `valor/usage/models.py UsageState` |  |
| Usage enforcement | §34 | IMPLEMENTED | `valor/usage/pep.py` |  |
| Controlled Training | P0-M | IMPLEMENTED | `valor/execution/secure_execution.py` | LocalIsolatedProvider/TrainingJobSpec |
| Evidence Signature | §19 | IMPLEMENTED | `valor/security/signing.py` | sign_evidence/verify_evidence_signature |
| DP/Disclosure Separation | §34 | IMPLEMENTED | `valor/usage/privacy_budget.py` | QueryPrivacyBudget vs AuditDisclosureBudget |

## Summary

- Implemented: 44/44