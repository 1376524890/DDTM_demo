# DDTM ZKP 实验复现说明

## 硬件环境
- CPU: QEMU Virtual CPU version 2.5+, 2 cores, 1 thread/core
- RAM: (VM环境)
- OS: Linux 6.8.0-124-generic
- 测试时间: 2026-06-11

## 软件环境
- Go: (编译时版本)
- gnark: github.com/consensys/gnark v0.x
- gnark-crypto: github.com/consensys/gnark-crypto (BN254曲线)
- 证明系统: Groth16

## 源代码
- 文件: ddtm_zkp/iteration1_2.go (486行)
- 编译产物: ddtm_zkp/ddtm_v22 (13.5MB ELF binary)
- 编译产物: ddtm_zkp/ddtm_zkp (13.5MB ELF binary)

## 运行方式
```bash
cd ddtm_zkp/
# ZKP电路基准测试
./ddtm_zkp benchmark

# π_key + π_deliver全量攻击测试
./ddtm_v22 both
```

## 电路说明

### π_key (密钥一致性证明)
- 基础版: 331约束 — 仅验证 MiMC(K_s) = h_Ks
- 完整版: 1,322约束 — 验证 MiMC(K_s) = h_Ks AND K_s_enc = MiMC(pk_B, K_s, r)
- 攻击测试5项: Valid_Proof, Wrong_Ks, Wrong_pk_B, Tampered_Ks_enc, Cross_pk_replay
- 全部通过 (5/5)

### π_deliver (交付证明)
- 基础版: 2,517约束 — 单块MiMC加密验证
- 4块版: 8,456约束 — 逐块MiMC加密，4个数据块
- 攻击测试4项: Valid_Delivery, Dgood_Cbad, Low_Quality, Wrong_Ks
- 全部通过 (4/4)
- 约束增长率: ~2,114约束/块

## 规模外推
基于4块实测数据线性外推，适用于估算大规模部署的约束规模、证明时间和PK大小。
验证时间保持常数(~1.7ms)，证明时间随约束数近线性增长。

## 限制条件
- 当前原型未包含π_Q质量证明电路（待实现）
- 原型运行于单机环境，未测试多节点共识
- 仲裁测试基于模拟参数，未部署真实陪审员网络
