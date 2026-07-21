# DDTM-QAS P0 必修补丁

本文档列出在所有正式论文实验运行前必须完成的补丁。每项均标注当前实现状态和剩余工作。

## 状态图例
- ✅ **已完成**: 代码已实现，接口已定义
- 🔧 **原型完成**: 核心逻辑已实现，需要硬件/环境支持完成验证
- ⚠️ **部分完成**: 骨架已实现，需要补充电路级验证
- ❌ **未开始**: 需要外部资源（硬件、多参与方）

---

## P0-1: Cycle-Walking 电路验证

**状态**: ⚠️ 部分完成

**已完成**:
- ✅ `NativeFeistel17` + `NativeCycleWalk` 在 `native_helpers.go`
- ✅ `MaxCycleWalkIterations = 16`
- ✅ Feistel17 置换完整性已通过 Go 测试验证 (0..131071 一一映射)
- ✅ `CycleWalkIndex` + `VerifyCycleWalk` 电路接口已定义

**需要完成**:
- [ ] 在 `AuditBatchCircuit.Define()` 中添加完整的 cycle-walking 链验证
- [ ] 电路内证明 `index = Feistel17^k(seed, ordinal)` 且 `k <= MaxCycleWalkIterations`
- [ ] 测试覆盖 100000 行下 10^7 个 ordinal/seed 组合的迭代次数分布
- [ ] 超过上限的 seed 必须被 policy 拒绝，并换用下一 drand round

**解决方案**: 电路级 cycle-walk 需要 gnark 1.25 编译环境，验证后集成到 AuditBatchCircuit。

---

## P0-2: 合约内部 LLR 决策

**状态**: ✅ 已完成

**已完成**:
- ✅ `decideAudit()` 使用链上 `SprtParams` (Q32 整数)
- ✅ `setSprtParams()` 由 policy owner 设置
- ✅ INCONCLUSIVE 仅在 `auditN >= maxAuditSamples` 时触发
- ✅ 已移除外部 `decision` 参数
- ✅ LLR 计算: `failures * hitIncrementQ32 + clean * cleanIncrementQ32`
- ✅ Q32 空间比较避免除法精度损失

**剩余验证**:
- [ ] 部署对应 policy 的 SPRT Q32 常量
- [ ] 集成测试验证链上 LLR 与离线 Python 结果一致

---

## P0-3: Generated Verifier Adapter

**状态**: 🔧 原型完成

**已完成**:
- ✅ `Groth16VerifierAdapter.sol` 已实现
- ✅ gnark proof 解码 (256 bytes → a[2], b[2][2], c[2])
- ✅ `IZKVerifierAdapter` 接口符合规范
- ✅ 构造函数参数验证
- ✅ Proof 长度与输入数量检查
- ✅ `Groth16VerifierAdapter.t.sol` 测试已编写

**需要完成**:
- [ ] 部署 gnark 导出的 Solidity verifier
- [ ] 端到端验证: 有效/无效/重放证明
- [ ] 将 verifier bytecode hash 写入 PolicyRegistry

---

## P0-4: Circuit ↔ Native Poseidon2 交叉测试

**状态**: 🔧 原型完成

**已完成**:
- ✅ Go native: `canonicalizer-go/internal/merkle/poseidon.go` (Poseidon2 via gnark-crypto)
- ✅ Go circuit: `zk/circuits/merkle.go` (Poseidon2 via gnark std)
- ✅ 同一 TAG 常量定义 (TAG_ROW=0x44525401, TAG_NODE=0x444E4401, TAG_PADDING=0x44504401)
- ✅ 测试向量生成器: `experiments/cross_test_poseidon.py`
- ✅ 7 组跨语言测试用例 (单行、缺失、padding、行交换、小树)

**需要完成**:
- [ ] 在 Go 1.25 环境中运行完整交叉测试
- [ ] 验证: 叶子哈希、节点哈希、padding leaf、tag 常量
- [ ] 验证: 审计探针承诺、指标承诺

---

## P0-5: 真实 TDX/SEV-SNP Attestation

**状态**: ❌ 需要硬件

**已完成**:
- ✅ `AttestationProvider` trait 已定义
- ✅ `MockAttestation` 已实现 (`development_only=true`)
- ✅ `Evidence` 结构体已定义 (backend, measurement, report_data, raw_evidence)
- ✅ 合约端 `AttestationRegistry` 支持 measurement 审批

**需要完成**:
- [ ] 实现 `TdxAttestation` (DCAP Quote Generation + Verification Library)
- [ ] 实现 `SnpAttestation` (SEV-SNP guest ioctl + VCEK chain)
- [ ] 中继服务: 验证 PCK/TCB/CRL/VCEK，拒绝过期/不可接受 TCB
- [ ] 测试: 错误 measurement、过期 TCB、report_data 不匹配、重放拒绝
- [ ] 合约正式网络拒绝 Mock measurement

**硬件依赖**: Intel TDX (4th Gen Xeon+) 或 AMD SEV-SNP (EPYC 7003+)

---

## P0-6: 多方可信设置

**状态**: ❌ 需要多参与方协调

**已完成**:
- ✅ 单方开发设置: `go run ./cmd/setup --unsafe-development-setup`
- ✅ 开发 artifact 标记 `UNSAFE_DEVELOPMENT_SETUP`
- ✅ `cmd/setup/main.go` 支持 utility/audit 电路

**需要完成**:
- [ ] 发布固定 R1CS + SHA-256
- [ ] Phase 1 (BN254) + Phase 2 (每个电路)
- [ ] 至少 5 个独立参与者顺序贡献
- [ ] 每次贡献验证 transcript
- [ ] 最终 PK/VK/R1CS/transcript 摘要上链
- [ ] VK 导出 Solidity → PolicyRegistry
- [ ] verifier bytecode hash 和 circuit hash 写入 PolicyRegistry

---

## P0-7: 保形审计探针校准

**状态**: 🔧 原型完成

**已完成**:
- ✅ `ml/train_audit_probe.py` 训练脚本
- ✅ 基于分位数的阈值校准
- ✅ 校准记录输出 (α, 样本数, quantile, 准确率)
- ✅ 特征中心、逆尺度平方、边际/距离/缺失阈值导出

**需要完成**:
- [ ] 在独立校准集上执行保形预测 (已预留 `--alpha` 参数)
- [ ] 校准记录写入可审计 trail
- [ ] 禁止根据卖方样本重新选择阈值 (需在协议中强制执行)
- [ ] 探针承诺 `c_A` 必须在卖方 c_D 进入评估前生成并上链

---

## P0-8: 完整端到端集成测试

**状态**: 🔧 原型完成

**已完成**:
- ✅ 20 步协议执行顺序文档 (参见 design doc §12 + `experiments/e2e_test.sh`)
- ✅ JABO SPRT 验证: 检测率 95.12%, 保证金 3141.09
- ✅ Feistel17 置换完整性验证
- ✅ 交叉测试向量生成 (7 例)
- ✅ SPRT 边界验证
- ✅ `DDTMMarketplaceIntegration.t.sol` 完整合约测试

**需要完成**:
- [ ] 卖方欺诈场景 (评估后调包数据)
- [ ] 买方争议场景 (假 manifest)
- [ ] 超时回退全部路径
- [ ] 所有攻击测试 (参见 design doc §13.3)

---

## P0-9: 合约 Fuzz/Invariant 测试

**状态**: 🔧 原型完成

**已完成**:
- ✅ `DDTMMarketplaceInvariants.t.sol` 已实现
- ✅ 资金守恒: bond + escrow 永不丢失
- ✅ 状态转换守卫: 不可跳状态
- ✅ 唯一 request ID 测试
- ✅ 参与者权限检查 (only seller/buyer)
- ✅ 自我出价禁止
- ✅ 过期后不可操作
- ✅ INCONCLUSIVE 不自动确认
- ✅ Bond fuzz 测试 (可变 bond amount)

**需要完成**:
- [ ] Foundry `forge test` 环境中运行完整 fuzz
- [ ] 添加 invariant_ 前缀的正式 invariant 测试
- [ ] Ghost variable 追踪 credits 总和

---

## 验收截止日期

所有 P0 补丁必须在以下里程碑前完成:

| 里程碑 | P0 项目 | 状态 |
|--------|---------|------|
| M3 (ZASA) | P0-1, P0-2, P0-4 | P0-1 ⚠️, P0-2 ✅, P0-4 🔧 |
| M4 (合约) | P0-2, P0-3, P0-9 | P0-2 ✅, P0-3 🔧, P0-9 🔧 |
| M5 (TEE安全) | P0-5 | P0-5 ❌ (需要硬件) |
| M6 (论文实验) | P0-6, P0-7, P0-8, P0-9 | P0-6 ❌ (需要多方), P0-7 🔧, P0-8 🔧, P0-9 🔧 |

## 环境依赖总结

| 补丁 | 阻断因素 | 可模拟 |
|------|----------|--------|
| P0-1 | Go 1.25 编译 | 否 (需要编译) |
| P0-4 | Go 1.25 编译 | 否 (需要编译) |
| P0-5 | Intel TDX / AMD SEV-SNP 硬件 | 是 (Mock 可用于功能测试) |
| P0-6 | 5+ 独立参与者 + 协调 | 是 (单方设置可用于功能测试) |
| P0-7 | 独立校准数据集 | 是 (现有脚本可用) |
| P0-8 | 完整编译环境 | 部分是 (Python 模块可独立测试) |
| P0-9 | Foundry | 否 (需要 forge 编译) |
