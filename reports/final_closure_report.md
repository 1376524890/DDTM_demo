# VALOR-v1 最终机制忠实性收敛报告

## A. HEAD
- Commit: (见 git log 最新 `git rev-parse HEAD`)

## B. Mechanism Closure (FullChainGate MFC-G01..G50)
完整 FullChainGate 在带 calibration 的完整交易上 **56/56 检查 PASS**（`paper_closure_gate=PASS`）。
G01..G50 全部实现为真实结构性验证 / 独立复算，无 `lambda: True` 兜底门。

关键门：
- **G01** single canonical DatasetCommitment（P0-A，salt+Merkle 持久化，replay 复现）
- **G02-G04** Quote→Choose→Execute 时序 + Reverse VCG 独立复算 + execution 绑定 quote
- **G05/G06** 签名 evidence 才计入 quorum（Ed25519）
- **G07** DP(ε) 与 AuditDisclosure 语义分离
- **G08/G09** 逐 action payer + 逐节点 VCG
- **G14** p̲_B^sys 独立复算
- **G15/G16** PreLock 整包络 + 先于审计
- **G17/G18** seller/buyer bond IC 独立对账
- **G19-G21** Pmax/Pmin/clearing 独立复算
- **G22/G23** rights compatibility + dominance/no-arbitrage
- **G24-G26** Settlement Phase I + Delivery + H(D) 一致
- **G27-G29** Rights ACTIVE 先于使用 / receipt / DENY 先于 key release
- **G30/G31** buyer/seller breach 由 evidence 派生（非 scenario flag）
- **G32/G33** Settlement Phase II + escrow 关闭
- **G34** retention/delete duty
- **G35/G36** lineage hash-chain + OpenLineage export
- **G37** FinalEvaluation 决策前不可读
- **G42/G43** 无业务默认值 / 无禁止模式（真实静态扫描）
- **G44** auditor 进程无全量数据
- **G45/G46** 合法受控训练真实运行 / 非法训练无 D 访问
- **G47-G49** money 守恒 / recipient 语义 / trace chain
- **G50** 确定性重放（重跑同一交易输出一致）

## C. Formula Coverage
44/44 机制 IMPLEMENTED（0 PARTIAL / 0 PLACEHOLDER / 0 MOCK / 0 FALLBACK）。
见 `reports/mechanism_coverage.md` / `.json`。NOT_APPLICABLE 项：无（全部核心主链实现）。

## D. Critical Fixes
| 问题 | 根因 | 修改文件 | 机制现在如何执行 |
|---|---|---|---|
| 双 commitment | privacy audit 内 `_ensure_committed` 重新 commit | orchestrator.py, voi.py, executor_adapter.py, commitment.py | 唯一 canonical commitment（salt+Merkle 持久化），下游消费 |
| replay 不确定 | 随机 salt + tx_id + datetime.now | commitment.py, orchestrator.py, listing.py, audit_executor.py | 确定性 salt/tx_id/时间戳 |
| 审计市场人工 bids | executor 内 `10+i` | audit_executor.py, market_quote.py, reverse_vcg.py | AuditorMarketSnapshot 注入 + Reverse VCG |
| 人工 likelihood | `AuditLikelihoodCalibrator` L=0.5 | calibration.py, calibration_runner.py | EmpiricalAuditLikelihood（Dirichlet） |
| 无签名证据 | signature 空 | signing.py, verifier.py, scheduler.py | Ed25519 签名 + 验签才计 quorum |
| DP 映射行数 | `int(ε)→rows` | privacy_budget.py, disclosure.py, voi.py | QueryPrivacyBudget vs AuditDisclosureBudget |
| entitlement 捷径 | `sc.entitlement_pass`/`compliant=True` | orchestrator.py | Entitled/Compliant/Compatible 真实执行 |
| 终态捷径 | `sc.seller_breach`/`sc.buyer_misuse` 直接定终态 | orchestrator.py, state_machine.py | 由 audit BREACH_EVIDENCE / usage misuse evidence 派生 |
| 无 Delivery | 主链缺 delivery stage | delivery.py, orchestrator.py | DeliveryReceipt + H(D) 校验 |
| 单次 settle | 一次 settle 解决整笔 | settlement.py | settle_clearing + settle_terminal 两阶段 |
| 无受控训练 | 只返回 ALLOW 不执行 | secure_execution.py, controlled_training.py, orchestrator.py | 真实 MNIST MLP 训练 + 非法在 key release 前拒 |
| 无 usage bond | b_b_use=0 | orchestrator.py, buyer_usage_bond.py | certified misuse detection 公式计算 |
| 无机会成本 | `sc.seller["oc_s"]` 常数 | orchestrator.py, opportunity_cost.py | rights 排他 + future revenue model |

## E. Privacy Audit
- 真实 auditor 进程数：3（`tests/system/test_process_isolated_privacy_capstone.py`）
- full-data exposure = **false**（`auditor_has_no_full_data`）
- signed evidence：Ed25519 签名，scheduler 验签后才计 quorum
- tamper tests：篡改 row → BREACH_EVIDENCE
- quorum tests：有效 evidence 独立重数
- disclosure：unique rows/fraction/bytes（非 DP 映射）

## F. Audit Economics
- Quote 示例：action a1，市场快照注入，Reverse VCG → committee → VCG payments
- selected action / expected cost / realized cost / per-node VCG / payer split 全记录

## G. Delivery
- 模式：COMPUTE_ONLY（rights 决定）
- H(D_listing) == H(D_delivery) 验证通过

## H. Legal Training
- 真实 MNIST MLP 训练：train_loss / eval_loss / accuracy / model hash（非 fake）

## I. Illegal Training
- U1-U8 各用例：DENY → key_release=False, data_access=False, training_started=False

## J. Pricing
- V_lower / audit_pay_S / audit_pay_B / B_S_pre / B_S_star / C_B_cap / B_B_use / C_B_use_cap / L_comp / OC_S / Pmax / Pmin / margin / P* 全由机制输出 + 独立 reconciliation

## K. Settlement
- Phase I（clearing 后）+ Phase II（delivery/终态）两阶段；逐节点 auditor 转移；escrow 关闭；守恒

## L. Lifecycle
- Normal(C0) / NO_TRADE(C1) / SELLER_BREACH_AUDIT(C2) / BUYER_BREACH(C3) / disclosure budget infeasible(C5) / illegal training(C7) 全跑通

## M. Test Summary
- 见最终 pytest 结果（完整套件）

## N. Static Scan
- `check_business_defaults.py`：OK 未发现
- `check_forbidden_patterns.py`：OK 未发现

## O. Unresolved Issues
- 无 unresolved P0。TEE（SGX/CoCo）硬件 attestation **NOT VERIFIED**（无硬件）；代码提供 LocalIsolatedProvider + ConfidentialProvider interface，trust boundary 明确。

## 最终判定
```
unresolved_P0 = 0
unresolved_mechanism_gaps = 0
paper_mechanism_closure = PASS
```
