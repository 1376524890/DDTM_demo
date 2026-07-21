# DDTM-QAS P0 必修补丁

本文档列出在所有正式论文实验运行前必须完成的补丁。这些补丁不会影响原型功能开发，但跳过任何一项将导致实验结果不可接受。

## P0-1: Cycle-Walking 电路验证

**当前状态**: `NativeCycleWalk` 已实现，`VerifyCycleWalk` 为骨架。

**需要完成**:
- 在 `AuditBatchCircuit.Define()` 中添加完整的 cycle-walking 链验证
- 电路必须固定 `MaxCycleWalkIterations=16`
- 证明 `index = Feistel17^k(seed, ordinal)` 且 `k <= MaxCycleWalkIterations`
- 测试覆盖 100000 行下 10^7 个 ordinal/seed 组合的迭代次数分布
- 超过上限的 seed 必须被 policy 拒绝，并换用下一 drand round

## P0-2: 合约内部 LLR 决策

**当前状态**: `decideAudit()` 使用 `SprtParams` 和链上整数 LLR 计算。

**需要完成**:
- 部署对应 policy 的 SPRT Q32 常量
- 添加 `testDecideAuditLLR()` 测试验证链上 LLR 与离线 Python 结果一致
- 确保 `INCONCLUSIVE` 在达到 `maxAuditSamples` 时触发，不提前自动通过
- 移除任何接受外部 `decision` 参数的能力

## P0-3: Generated Verifier Adapter

**当前状态**: `IZKVerifierAdapter` 接口已定义，但无具体实现。

**需要完成**:
- 创建 `Groth16VerifierAdapter.sol`，包装 gnark 导出的 Solidity verifier
- 统一 public inputs 布局与合约中 `submitUtility()` 和 `submitAuditBatch()` 的检查一致
- 验证 input count、dataRoot、metricsCommitment 等关键字段
- 测试包含有效/无效/重放证明

## P0-4: Circuit ↔ Native Poseidon2 交叉测试

**当前状态**: 两端都使用 Poseidon2，但需要交叉验证。

**需要完成**:
- 对相同输入，Go native hash、Rust native hash、Go circuit hash 产生相同结果
- 测试覆盖: 叶子哈希、节点哈希、padding leaf、tag 常量
- 测试覆盖: 审计探针承诺、指标承诺

## P0-5: 真实 TDX/SEV-SNP Attestation

**当前状态**: `MockAttestation` 已实现，`AttestationProvider` trait 已定义。

**需要完成**:
- 实现 `TdxAttestation` (DCAP Quote Generation + Verification)
- 实现 `SnpAttestation` (SEV-SNP guest ioctl + VCEK chain)
- 中继服务: 验证 PCK/TCB/CRL/VCEK，拒绝过期/不可接受 TCB
- 测试: 错误 measurement、过期 TCB、report_data 不匹配、重放全部拒绝

## P0-6: 多方可信设置

**当前状态**: 开发使用单方 `--unsafe-development-setup`。

**需要完成**:
- 发布固定 R1CS + SHA-256
- Phase 1 (BN254) + Phase 2 (每个电路)
- 至少 5 个独立参与者顺序贡献
- 每次贡献验证 transcript
- 最终 PK/VK/R1CS/transcript 摘要上链
- VK 导出 Solidity → PolicyRegistry

## P0-7: 保形审计探针校准

**当前状态**: `train_audit_probe.py` 使用基础分位数阈值。

**需要完成**:
- 在独立校准集上执行保形预测
- 校准记录包含样本 ID、非一致性分数、α 和 quantile 计算方式
- 禁止根据卖方样本重新选择阈值
- 探针承诺 `c_A` 必须在卖方 c_D 进入评估前生成并上链

## P0-8: 完整端到端集成测试

**当前状态**: 各模块独立测试已编写。

**需要完成**:
- 20 步完整协议执行测试 (参见 design doc §12)
- 覆盖: 正常流程、卖方欺诈、买方争议、超时回退
- 所有攻击测试通过 (参见 design doc §13.3)

## P0-9: 合约 Fuzz/Invariant 测试

**当前状态**: 基础单元测试已编写。

**需要完成**:
- escrow+bond 资金守恒 invariant
- 只有合法状态转换
- 唯一 request ID
- 旧 session/randomness/proof 不能重放
- 退款与卖方结算互斥
- INCONCLUSIVE 从不自动确认

## 验收截止日期

所有 P0 补丁必须在以下里程碑前完成:

| 里程碑 | P0 项目 |
|--------|---------|
| M3 (ZASA) | P0-1, P0-2, P0-4 |
| M4 (合约) | P0-2, P0-3, P0-9 |
| M5 (TEE安全) | P0-5 |
| M6 (论文实验) | P0-6, P0-7, P0-8, P0-9 |
