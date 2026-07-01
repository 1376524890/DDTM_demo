# DDTM 区块链数据要素交易系统——原型构建过程

> 基于研究报告《区块链赋能数据要素流通》(2026更新版) 和 DDTM 协议设计
> 原型代码位于 `~/workspace/research/ddtm_evm/` 和 `~/workspace/research/ddtm_zkp/`

---

## 一、为什么要做这个原型

### 1.1 背景

全国已有 58 家以上数据交易机构，但普遍"有场无市"——交易量极低，大量交易仍在场外私下完成。研究报告指出，核心问题不是缺交易所，而是**交易基础设施不够用**：

| 现状 | 问题 |
|------|------|
| 区块链仅做哈希存证 | 不驱动交易本身，是"电子签章的区块链版" |
| 隐私计算停留在概念验证 | 远未成为交易标配 |
| 定价全靠双方谈 | 无自动化定价机制 |
| DCB 数据资产凭证 | 本质是行政登记，不是可编程通证 |
| 各交易所各自建链 | 数据孤岛，互不互通 |

### 1.2 目标

做一个**链上驱动的数据交易引擎**，区别于现有交易所的"中心化撮合 + 区块链存证"模式。DDTM（Decentralized Data Trading Marketplace）协议让确权、定价、撮合、结算、交付全流程在链上通过智能合约和零知识证明驱动。

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      DDTM 交易协议                            │
│                                                              │
│  卖方                      链上合约                    买方    │
│  ┌──────┐              ┌──────────────┐              ┌──────┐ │
│  │ 数据  │──挂牌──────→│  DDTMProtocol │←──竞价+托管──│ 钱包  │ │
│  │ 卖方  │              │              │              │      │ │
│  │      │←──收款────────│ 10状态状态机  │────付款────→│      │ │
│  └──────┘              │              │              └──────┘ │
│       │                └──────┬───────┘                │      │
│       │                       │                        │      │
│       │   ┌───────────────────┴───────────────────┐    │      │
│       │   │           ZKP 验证层                   │    │      │
│       │   │                                       │    │      │
│       │   │  π_key  ─ 密钥一致性证明 (Groth16)      │    │      │
│       │   │  π_deliver ─ 交付证明                  │    │      │
│       │   │  π_Q  ─ 数据质量证明                   │    │      │
│       │   └───────────────────────────────────────┘    │      │
│       │                                                │      │
│       └──────────── 链下加密传输 ──────────────────────┘      │
│                                                              │
│  监管节点 ─── 门限签名 ─── 可审计ZKP ─── 实时介入             │
└──────────────────────────────────────────────────────────────┘
```

### 2.1 10 状态交易状态机

```
LISTED ──→ BIDDING ──→ ESCROWED ──→ QUALITY_VERIFIED ──→ DELIVERING
  │                                    │                      │
  │                                    │                      ├──→ CONFIRMED ✅
  │                                    │                      │
  │                                    └──→ DISPUTED ──→ ARBITRATING
  │                                          │                │
  │                                          │                ├──→ CONFIRMED ✅
  │                                          │                └──→ REFUNDED 🔙
  └──→ ABORTED ❌                            │
                                             └──→ REFUNDED (超时)
```

### 2.2 技术栈选型

| 层 | 技术 | 选型理由 |
|---|------|---------|
| 链上合约 | Solidity 0.8.20 + Hardhat | EVM 兼容，工具链成熟 |
| ZKP 电路 | Go + gnark + Groth16 + BN254 | DDTM 协议设计语言，性能好 |
| 哈希函数 | MiMC (ZKP-friendly) | 电路内约束少，gas 低 |
| 联盟链模拟 | Python PBFT 模拟器 | 快速验证共识性能 |
| 联盟链部署 | FISCO BCOS (计划) | 国产联盟链，国密支持 |

---

## 三、构建过程（已完成部分）

### 阶段 1：核心智能合约（Solidity）

**文件**: `ddtm_evm/contracts/DDTM.sol`（176行）

实现了完整的 10 状态机，关键设计决策：

**挂牌时锁定保证金**。卖方调用 `list()` 时需质押 ≥ 售价 10% 的保证金，防止恶意挂牌。交易数据以承诺形式上链（`c_D`, `c_Q`, `c_k`, `root`），原始数据不暴露。

**竞价即托管**。买方 `bid()` 时全额付款进入合约托管，状态从 LISTED 直接跳到 ESCROWED——无中间 BIDDING 等待期，减少状态切换成本。

**争议双向裁决**。仲裁方 `resolveArbitration(id, sellerWins)` 根据布尔值分出胜负：卖方胜 → 结算放款；买方胜 → 全额退款并罚没卖方保证金。

**测试覆盖** (`ddtm_evm/test/ddtm_test.js`，137行)：

```
Scenario 1: 正常交易 → CONFIRMED ✅
Scenario 2: 错误密钥争议 → DISPUTED → REFUNDED ✅
Scenario 3: 卖方胜诉 → CONFIRMED ✅
Scenario 4: 撤销挂牌 → ABORTED ✅
Scenario 5: 卖方拒交付超时 → REFUNDED ✅
Performance: Gas 基准 → 全流程 ~395K gas
Performance: 50并发 → 108.5 TPS
```

**Gas 消耗实测**（Hardhat 本地网，单位 gas）：

| 操作 | Gas | 说明 |
|------|----:|------|
| listing | 209,833 | 最贵（4 个 bytes32 + 保证金转账） |
| bidding | 70,774 | 含 ETH 托管 |
| submitProof | 30,196 | 状态切换（ZKP 验证需外加） |
| delivery | 30,111 | |
| confirm | 53,659 | 含多笔转账结算 |
| **全流程** | **394,573** | |

> 在以太坊主网 gas=20 gwei 的情况下，全流程约 0.008 ETH。在 L2 或联盟链上成本更低。

### 阶段 2：ZKP 电路（Go + gnark）

**目录**: `ddtm_zkp/`

#### π_key（密钥一致性证明）

证明卖方交付的解密密钥与挂牌时承诺的密钥一致，且加密绑定到买方公钥。

**基础版**（331 约束，31ms 证明）：
- 验证 `MiMC(K_s) == h_Ks`
- ZKP 的 Hello World，验证哈希一致性

**完整版**（1,322 约束，103ms 证明）：
- 验证 `MiMC(K_s) == h_Ks` **且** `K_s_enc = MiMC(pk_B || K_s || r)`
- 绑定买方公钥，防止密钥被第三方截获后冒用

攻击测试 5 项全部通过：Valid_Proof / Wrong_Ks / Wrong_pk_B / Tampered_Ks_enc / Cross_pk_replay

#### π_deliver（交付证明）

证明交付的加密数据与挂牌时承诺的数据一致，且质量达到阈值。

**基础版**（2,517 约束，99ms 证明）：
- 单块 MiMC 加密验证

**4 块版**（8,456 约束，327ms 证明）：
- 逐块 MiMC 加密，4 个数据块
- 约束增长率约 2,114 约束/块

攻击测试 4 项全部通过：Valid_Delivery / Dgood_Cbad / Low_Quality / Wrong_Ks

#### π_Q（质量证明，电路已设计，待编译）

**文件**: `ddtm_zkp/pi_q.go`（229行）

验证数据质量达到买方要求：
1. **完整性检查**：`H(D || r_D) == c_D`（数据未被篡改）
2. **质量承诺**：`H(Q(D) || r_Q) == c_Q`（质量声明确实来自该数据）
3. **阈值判定**：`Q_val >= Theta`（质量指标达到要求）
4. **时效性**：`Q_val <= Ctx`（数据未过期）

#### 性能汇总

| 电路 | 约束数 | 证明时间 | 验证时间 | 设置时间 | PK 大小 |
|------|-------:|-------:|-------:|-------:|------:|
| π_key 基础版 | 331 | 31ms | 1.5ms | 131ms | 67KB |
| π_key 完整版 | 1,322 | 103ms | 1.7ms | 497ms | 266KB |
| π_deliver 基础版 | 2,517 | 99ms | 1.7ms | 735ms | 421KB |
| π_deliver 4块版 | 8,456 | 327ms | 1.7ms | 2,937ms | 1,714KB |

> 硬件: QEMU 2 核 / Linux 6.8。验证时间恒定 ~1.7ms，与电路规模无关——这是 Groth16 的核心优势。

#### 规模外推

基于 4 块实测数据（2,114 约束/块）线性外推：

| 数据块数 | 预估约束 | 预估证明时间 | 预估 PK 大小 | 适用场景 |
|--------:|--------:|----------:|----------:|---------|
| 10 | 21,140 | 0.8s | 4.3MB | 小数据集 |
| 50 | 105,700 | 4.1s | 21.5MB | 中等数据集 |
| 100 | 211,400 | 8.2s | 43.0MB | 大型数据集 |
| 500 | 1,057,000 | 40.9s | 215MB | 批量交付 |
| 1,000 | 2,114,000 | 81.8s | 430MB | 超大规模 |

> 证明时间近线性增长。500 块以上建议用递归证明（LatticeFold/Nova 等折叠方案）压缩。

### 阶段 3：联盟链 PBFT 模拟

**文件**: `ddtm_zkp/multi_node_sim.py`（171行）

模拟 4/7/10 节点 PBFT 共识下的 DDTM 交易吞吐量。交易类型按权重混合：listing(25%) + bidding(20%) + zkp_verify(30%) + confirm(15%) + dispute(10%)。

**实测结果** (`multi_node_results.json`)：

| 节点数 | 并发交易 | TPS | P50 延迟 | P95 延迟 | 失败率 |
|:-----:|--------:|----:|-------:|-------:|-----:|
| 4 | 10 | 49.4 | 5.4ms | 7.8ms | 2.5% |
| 4 | 100 | 282.1 | 3.2ms | 6.6ms | 2.1% |
| 4 | 500 | 307.8 | 3.2ms | 6.6ms | 1.7% |
| 7 | 10 | 49.4 | 5.7ms | 11.1ms | 2.5% |
| 7 | 100 | 220.6 | 4.1ms | 8.4ms | 2.2% |
| 7 | 500 | 245.4 | 3.9ms | 6.8ms | 2.1% |
| 10 | 10 | 50.0 | 6.0ms | 15.0ms | 1.2% |
| 10 | 100 | 195.9 | 5.0ms | 6.6ms | 2.4% |
| 10 | 500 | 246.1 | 5.1ms | 6.8ms | 1.8% |

**关键发现**：
- 4→7→10 节点时 TPS 下降约 20%，主要来自三轮 PBFT 广播开销
- P95 延迟在 10 节点时最高 15ms，仍在可接受范围
- 失败率稳定在 1-3%，主要来自模拟中的并发竞争

---

## 四、如何运行原型

### 4.1 EVM 智能合约

```bash
cd ~/workspace/research/ddtm_evm

# 编译合约
npx hardhat compile

# 运行全部测试（7项）
npx hardhat test
```

输出示例：
```
DDTM Protocol — Full State Machine & Performance
  ✔ Scenario 1: Normal trade → CONFIRMED
  ✔ Scenario 2: Wrong key → DISPUTED → REFUNDED
  ✔ Scenario 3: Seller wins dispute → CONFIRMED
  ✔ Scenario 4: Abort listing → ABORTED
  ✔ Scenario 5: Seller refuses → REFUNDED via timeout
  ✔ Performance: Gas costs
  ✔ Performance: Concurrent TPS (50 listings)

7 passing (2s)
```

### 4.2 ZKP 电路基准测试

```bash
cd ~/workspace/research/ddtm_zkp

# π_key + π_deliver 全量攻击测试
./ddtm_v22 both

# 基准测试
./ddtm_zkp benchmark
```

### 4.3 联盟链性能模拟

```bash
cd ~/workspace/research/ddtm_zkp

# PBFT 共识模拟（4/7/10 节点 × 10/100/500 并发）
python3 multi_node_sim.py

# 生成 LaTeX 实验表格
python3 experiment_report.py
```

### 4.4 一键全量实验

```bash
cd ~/workspace/research/ddtm_zkp
bash run_all.sh
```

---

## 五、待完成事项

### 5.1 高优先级

| 事项 | 说明 | 预估工时 |
|------|------|:------:|
| **π_Q 电路编译验证** | `pi_q.go` 已写好，需 `go build` 并跑通基准测试 | 2h |
| **EVM ↔ ZKP 集成** | 合约 `submitProof()` 目前只改状态，需接入 Groth16 链上验证器 | 1天 |
| **端到端 CLI 演示** | 一个脚本跑通 挂牌→竞价→ZKP验证→交付→结算 | 1天 |

### 5.2 中优先级

| 事项 | 说明 | 预估工时 |
|------|------|:------:|
| **FISCO BCOS 部署** | 从 Hardhat 单节点迁移到国产联盟链 | 3天 |
| **门限签名仲裁** | 实现 t-of-n 门限签名的争议裁决（GG20 协议） | 3天 |
| **可审计 ZKP** | 在 Groth16 基础上增加监管审计密钥 | 5天 |
| **Web 前端** | React + ethers.js 可视化交易状态机 | 5天 |

### 5.3 低优先级

| 事项 | 说明 |
|------|------|
| 跨链桥（联盟链 ↔ 公链） | 国际化数据资产流通 |
| AMM 自动定价 | 链上自动化数据估值 |
| IPFS 链下存储 | 替代本地文件系统 |

---

## 六、设计决策记录

### 为什么用 Groth16 而不是 Plonk？

Groth16 的验证 gas 最低（~200K），证明体积最小（~200 字节）。联盟链场景下，受信设置（Trusted Setup）可通过多方计算仪式完成，不是致命缺陷。如果需要通用电路（不重新设置），后续可迁移到 Plonk。

### 为什么用 MiMC 而不是 Poseidon？

MiMC 在 gnark 中实现更简洁，`AssertIsLessOrEqual` 等比较约束配合更好。在 EVM 上 verify gas 差距不大（~5%）。DDTM 论文使用 MiMC，保持一致性。

### 为什么合约中没有实际验证 ZKP？

当前 `submitProof()` 是占位符——只做状态切换，不做链上证明验证。这是因为链上 Groth16 验证器需要预编译合约或椭圆曲线库，在 Hardhat 本地网不可用。生产环境需接入 `verifyProof()` 预编译（EIP-197）。

### 为什么 PBFT 模拟器是 Python 写的而不是真实联盟链？

快速验证共识层面的吞吐量瓶颈。用真实 FISCO BCOS 部署 10 节点需要大量配置工作，Python 模拟器可以在 5 秒内给出 TPS 数量级估计，用来确认 PBFT 三轮通信是瓶颈（而非 ZKP 验证）。

---

## 七、文件索引

| 文件 | 说明 |
|------|------|
| `ddtm_evm/contracts/DDTM.sol` | 核心合约（176行，10状态机） |
| `ddtm_evm/test/ddtm_test.js` | 合约测试（137行，7项测试） |
| `ddtm_evm/hardhat.config.js` | Hardhat 配置 |
| `ddtm_zkp/iteration1_2.go` | π_key + π_deliver 电路（486行） |
| `ddtm_zkp/pi_q.go` | π_Q 质量证明电路（229行，待编译） |
| `ddtm_zkp/ddtm_v22` | 预编译 ZKP 二进制（13.5MB） |
| `ddtm_zkp/multi_node_sim.py` | PBFT 共识模拟器（171行） |
| `ddtm_zkp/multi_node_results.json` | 联盟链性能数据（9组配置） |
| `ddtm_zkp/experiment_report.py` | LaTeX 实验报告生成器（283行） |
| `ddtm_zkp/EXPERIMENT_README.md` | 实验复现说明 |
| `ddtm_zkp/run_all.sh` | 一键实验脚本 |

---

*2026年7月1日 · 基于 DDTM v24 原型*
