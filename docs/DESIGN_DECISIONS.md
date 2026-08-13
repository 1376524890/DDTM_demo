# VALOR-v1 设计决策 D1–D20

本文记录三轮评审后冻结的核心设计决策，作为冻结版机制文档 v2 的工程对应。每项决策标注对应机制文档章节与评审依据。

## D1. 三级检测概率接口（核心数学改动）
单节点审计器检测能力 ≠ 系统审计动作结果分布 ≠ 整套序贯策略检测能力。
```
λ^prim(o|x)        底层审计器/单节点检测结果（per-auditor, per-primitive）
      ↓  committee/node-behavior composition（含 m,q,ρ,η_B,η_O）
Λ_a^action(y|x,Γ)  候选系统审计动作 a=(policy,m,q,ρ,Γ) 的结果分布
                   ★ Algorithm 2 计算 MV_A 时读取的量 ★
      ↓  full-policy composition（sequential stop rule）
p_B^sys(Π_A)       整套序贯策略最终能否发现 Seller Breach（用于 Seller Bond）
```
Phase：1.5A 校准 λ^prim → 1.5B 组合 Λ_a^action → 2 跑 Algorithm 2 → 2.5 认证 p_B^sys。

## D2. p̲_B^sys 认证有限 certified cells
不可声称对连续参数包络求真实 worst-case。采用有限离散 cells：
```
Ω_c = {ω_1,...,ω_K}；p̲_B,c^sys = min_k LCB_k
registry key: (policy_hash, m, q, ρ, attack_family, threat_tier) + Ω_c
多 breach family: p̲_B^sys = min_{h∈H_contract} p̲_B,h^sys
ω_tx ∉ Ω_c → PROFILE_OUT_OF_CERTIFIED_RANGE
```

## D3. π₀ Prior 显式来源
```
π_B = E[θ_S]
q_L = P(L|X≠B, C_b)          # buyer-context suitability calibration，仅用交易前特征
π_L = (1−π_B)·q_L
π_G = (1−π_B)·(1−q_L)
audit/state_model.py::build_initial_prior(seller_breach_prior, buyer_suitability_prior) -> StateBelief
```

## D4. P0 Audit Policy Library（7 类，tabular v1）
CommitmentIntegrity / SchemaConsistency / Missingness / DuplicateInflation（确定性 ground truth）、LabelConsistency / DistributionShift（clean reference）、MetadataClaim（seller claim + 故意违反）。Provenance fraud 用合成 provenance 场景。

## D5. RQ1 交易估值单位 = candidate seller batch
`D_k = candidate seller batch / provider dataset`。K=20~40 主质量，K=100 scalability。seller batch/provider 优先当 Shapley player。

## D6. 真实数据按自身维度进入
`dataset_manifest.json`：`{name, source, sha256, license, n_raw, d_raw, split_seed}`。N=10000,d=64 仅 benchmark config。

## D7. 经济映射 g_b() cost-sensitive payoff（修正矩阵索引）
行=true label，列=predicted：
```
R_b = [[ r_TN, r_FP ],
       [ r_FN, r_TP ]]
U_b(θ) = N_b · Σ_{y,ŷ} P(y,ŷ;θ) · r_{y,ŷ}
V_D^gross,* = U_b(θ_train+D) − U_b(θ_train)
```
避免 ΔAUC×1000 冒充经济价值。

## D8. Phase Gate = 验证实现正确
RQ1 主指标 Spearman/Kendall/MAE/RMSE/Top-k/Coverage_V（AUROC 附加）；RQ6 不要求与 Oracle"完全一致"。

## D9. Reverse VCG（核心数学改动）
- private type 冻结为 `b_i = c_i^part = k_i + κ_A·B_A,i·T_A`（execution+capital）。truthfulness 在 b_i=c_i^part 附近 sweep。
- 限制可报告变量：cap_i/availability_i/B_A,i/r_i 来自 protocol-observed，不能节点自填。
- 精确分配（exhaustive/milp），Gate：AllocationOptimalityGap=0。
- 工程边界：counterfactual_feasible；MC_A^pay ≤ E_available^audit。
- k_i 仅 simulator/Oracle 可见。

## D10. RQ7 不把 B_S 作独立扫描变量
B_S* 内生；扫描 m,ρ,B_A,λ_A,η_B,η_O,p_target,κ_S,C_chain,G_S^dev。仅 Fixed Bond baseline 可扫 B_S。

## D11. 参数分类
ρ 是 protocol design variable；威胁变量 η_B,η_O,η_C,G_i^dev,G_S^dev。

## D12. 统一货币量纲 [CU]
CurrencyUnit=CU；V_D/L_AB/L_RG/C_A/B_S/P_D 全具 [CU]。configs/economics + 单位校验。

## D13. 保证金预锁 + 资本成本积分（核心数学改动）
- B_S^pre = max_{ω∈Ω_allowed} B_S*(ω)，Audit 前锁定；Audit 后释放差额；违约直接罚已锁 B_S^pre。
- C_B^cap = κ_S·∫₀ᵀ B_S(t)dt；v1 分段 κ_S(B_S^pre·T_audit + B_S*·T_post)。入 P_min 与 SW_full。
- seller 无法提供 B_S^pre → NO_TRADE / participation infeasible（非 SELLER_BREACH）。

## D14. 预期 vs 实际审计成本分开
MC_A^pay（含 E[C_challenge]+E[C_dispute]）用于 VOI；C_A^pay,realized（实际）用于 Pricing/Settlement/Utility。payer attribution 累加 realized。

## D15. G/L/B 严格 partition（修正伪代码 bug）
```
if SellerContractViolation:        X = B
elif TechnicalSuitabilityPredicate(D,C_b)==0:  X = L
else:                              X = G
```
B first→L second→G otherwise。单纯经济价值低不作 L。q_L 仅用交易前特征。

## D16. SW/SAW 会计口径冻结（修双重计费）
```
C_audit-service^res = Σ_i k_i
C_protocol^res = C_BFT + C_network + C_chain + C_challenge + C_dispute
SecurityCost = C_audit-service^res + C_protocol^res + C_B^cap + C_A^cap
SW_base = V_real − C_D − C_I − C_nonsec^res
SW_full = SW_base − SecurityCost − ExpectedResidualLoss
SAW := SW_full
```

## D17. 四角色数据划分
`BaseTrain ∩ SellerPool ∩ ValuationValidation ∩ FinalEvaluation = ∅`。防 estimator 用最终 holdout 泄漏。

## D18. 证据资格门 EvidenceEligibilityGate
只有 strong challenge / adjudicated dispute / canary / independent full audit / externally verified ground truth 更新检测能力与 auditor reliability。GroundTruthEligible=1。NO_TRADE 不能假装拥有 V_real；ExperimentalOracleFeedback ≠ ProductionObservableFeedback。

## D19. 认证样本量 + k_i 可见性 + 买方违约注入
- 样本量按 p_target/α_D/FN_allow 反推（Beta(1,1)、p̲≥0.90：零漏检 ~28、2 漏检 ~60）。certification.py 含计算器，进 R_cert 前冻结 n。
- k_i 仅 simulator/Oracle 可见；校准的是 ResourceCostModel_j / profiling distribution。
- BUYER_BREACH 注入：buyer 触发增量审计后拒绝继续（AUDIT 阶段检测）、拒绝 escrow、DELIVERY commitment 后取消。

## D20. 文档治理
D1–D20 中属机制定义的内容回写进机制文档生成冻结版 v2；VALOR-v1 只认一份 normative source。
