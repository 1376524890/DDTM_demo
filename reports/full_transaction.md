# VALOR 全流程交易报告

生成时间：`2026-08-15T03:05:10.142011+00:00`

**成交决策：`TRADE`**

## 1. 资格/合规（§6）
- 卖方资格：`True`；合规：`True`

## 2. 质量复现 Gate B（§15/§47）
- Gate B 通过：`True`
- 分布式启用 primitive：['structural', 'exact_duplicates', 'confident_learning', 'ks_shift', 'categorical_shift', 'mmd', 'metadata_claim_audit']

## 3. Data-VOI（§26-28）
- U_base = -
- U_base+Δ = -
- 竞争外部性 L_comp = 0.00 CU
- 保守下界 V̲_gross = 300.00 CU

## 4. Audit-VOI（§24-25）
- 审计步数：`1`
- 后验 π：`{'prob_g': 0.8988902589395809, 'prob_l': 0.08877928483353885, 'prob_b': 0.012330456226880396}`
- 审计支付（卖/买）：0.50 CU / 0.50 CU

## 5. 检测认证（§22）
- p̲_B^sys = `0.8019`

## 6. 责任（§30-31）
- B_S^* = 75.32 CU
- B_S^pre = 75.32 CU
- 资本成本 C_B^cap = 7.53 CU

## 7. 定价（§39-41）
- P_max = 283.50 CU
- P_min = 26.03 CU
- 贸易边际 M = 257.47 CU
- 结算价 P* = 154.77 CU
- 决策：`TRADE`

## 8. 状态机与结算（§43）
- 终态：`TRADE`；权利状态：`ACTIVE`
- bond 罚没：0.00 CU

## 9. 反馈（§45-46）
- realised value：154.00 CU
- ground-truth 资格事件：`['CONTROLLED_CANARY']`