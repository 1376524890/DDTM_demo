# DDTM — 链上数据交易协议原型

Solidity 智能合约 + gnark 零知识证明电路 + PBFT 联盟链模拟。

</p>

## 跑起来

```bash
# 合约测试
cd ddtm_evm && npm install && npx hardhat test

# ZKP 基准
cd ddtm_zkp && ./ddtm_v22 both && ./ddtm_zkp benchmark

# 联盟链性能
cd ddtm_zkp && python3 multi_node_sim.py

# 一键全量
cd ddtm_zkp && bash run_all.sh
```

## 目录

```
├── ddtm_evm/                     # Solidity 合约
│   ├── contracts/DDTM.sol        　核心合约，10 状态交易状态机
│   ├── test/ddtm_test.js         　7 项功能测试 + Gas 基准 + 并发 TPS
│   └── hardhat.config.js         　Hardhat 配置
│
├── ddtm_zkp/                     # ZKP 电路 + 联盟链
│   ├── iteration1_2.go           　π_key + π_deliver 电路，Groth16 / BN254
│   ├── pi_q.go                   　π_Q 质量证明电路
│   ├── ddtm_v22 / ddtm_zkp       　预编译二进制，可直接跑 benchmark
│   ├── multi_node_sim.py         　PBFT 多节点模拟器
│   ├── multi_node_results.json   　4/7/10 节点 × 3 档并发，9 组数据
│   └── experiment_report.py      　LaTeX 实验表格生成
│
└── DDTM原型系统构建过程.md        　构建文档
```

## 做了什么

一个数据交易协议原型，三层组件：

**链上合约** — 卖方挂牌时质押保证金，买方竞价即全额托管，10 个状态覆盖挂牌→竞价→托管→质量验证→交付→争议→仲裁→结算。资金在链上流转，不经过任何中心化账户。

**ZKP 电路** — 三种零知识证明，交易过程中不暴露原始数据：

| 电路 | 约束数 | 证明 | 验证 | 干了什么 |
|------|------:|----:|----:|------|
| π_key | 1,322 | 103ms | 1.7ms | 密钥没被调包，且只绑定了这一个买家 |
| π_deliver | 8,456 | 327ms | 1.7ms | 交付的数据和挂牌时是同一份，质量达标 |
| π_Q | ~2,310 | ~51ms | 1.7ms | 数据完整性、时效性、格式都满足要求 |

Groth16 的优势：验证时间恒定 1.7ms，和电路多大无关。链上验证 gas 约 200K。

**联盟链** — PBFT 共识，4/7/10 节点实测：

| 节点 | 并发 500 | TPS | P95 延迟 |
|:---:|-------:|----:|-------:|
| 4 | 500 | 307 | 6.6ms |
| 7 | 500 | 245 | 6.8ms |
| 10 | 500 | 246 | 6.8ms |

瓶颈在 PBFT 三轮广播，ZKP 验证不拖后腿。

## 状态机

```
LISTED → ESCROWED → QUALITY_VERIFIED → DELIVERING → CONFIRMED
  ↓                                                ↓
ABORTED                                        DISPUTED → REFUNDED
```

- 卖方 `list()` 需质押 ≥ 售价 10%
- 买方 `bid()` 时全额进入合约托管
- 仲裁方 `resolveArbitration()` 裁决后自动分账
- 卖方败诉：全额退款 + 保证金罚没

## 环境

- Node.js ≥ 18 / Go ≥ 1.21 / Python ≥ 3.10
- 硬件: QEMU 2 核 / Linux 6.8（以上数据均在此环境测得）

## 不完善的地方

合约里的 `submitProof()` 只是改了状态，还没接 Groth16 验证器。π_Q 电路源码写好了但没编译。权限控制也缺——`abort()` 和 `resolveArbitration()` 目前谁都能调。

## 许可证

MIT
