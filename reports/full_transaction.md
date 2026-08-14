# VALOR 全流程交易报告

生成时间：`2026-08-14T18:08:13.248404+00:00`

**成交决策：`NO_TRADE`**

## 1. 资格/合规（§6）
- 卖方资格：`True`；合规：`True`

## 2. 质量复现 Gate B（§15/§47）
- Gate B 通过：`True`
- 分布式启用 primitive：['structural', 'exact_duplicates', 'confident_learning', 'ks_shift', 'categorical_shift', 'mmd', 'metadata_claim_audit']

## 3. Data-VOI（§26-28）
- U_base = 180.00 CU
- U_base+Δ = 180.00 CU
- 竞争外部性 L_comp = 2.00 CU
- 保守下界 V̲_gross = -2.00 CU

## 4. Audit-VOI（§24-25）
- 审计步数：`1`
- 后验 π：`{'prob_g': 0.7876447876447875, 'prob_l': 0.17374517374517376, 'prob_b': 0.03861003861003861}`
- 审计支付（卖/买）：1.00 CU / 1.00 CU

## 5. 检测认证（§22）
- p̲_B^sys = `0.6366`

## 6. 责任（§30-31）
- B_S^* = 185.66 CU
- B_S^pre = 185.66 CU
- 资本成本 C_B^cap = 37.13 CU

## 7. 定价（§39-41）
- P_max = 0.00 CU
- P_min = 66.13 CU
- 贸易边际 M = -66.13 CU
- 结算价 P* = -
- 决策：`NO_TRADE`

## 8. 状态机与结算（§43）
- 终态：`NO_TRADE`；权利状态：`SUSPENDED`
- bond 罚没：0.00 CU

## 9. 反馈（§45-46）
- realised value：-
- ground-truth 资格事件：`[]`