# DDTM-QAS

DDTM-QAS 是隐私保护数据交易的研究原型，三个紧耦合机制：

1. **ARUC** — 机密 VM 内的可证明稳健效用认证。
2. **ZASA** — 基于 Poseidon2 Merkle 承诺的零知识自适应语义审计。
3. **JABO** — 激励相容结算的联合审计/保证金优化。

参考任务为表格二分类：最多 100,000 行、128 个定点特征。模型架构公开，模型参数与买方验证集保密。

## 两个独立目标

- **G0** — 让统计计算、经济模型与实验报告成为可信基线。
- **G1** — 让 Python / Go / Rust / gnark 对同一数据产生完全相同的编码、叶子与 Merkle Root。

当前两者均已通过（G0 PASS / G1 PASS / 工作区 CLEAN / 四语言 0 mismatch）。

## 一键复现

```bash
# G0：统计与经济基线（含 11 项 pytest）
bash scripts/run-g0.sh

# G1：四语言跨语言一致性（生成向量 → Go/Rust/gnark 验证 → gate）
bash scripts/run-g1.sh

# G0 + G1 release 报告（要求 CLEAN 工作树）
bash scripts/generate-report.sh
```

Python 依赖：`pip install -r experiments/requirements.txt`（gmpy2 + pytest）。

## 仓库结构

- `specs/` — 冻结的规范：`canonical-data-v1`（行布局/量化/SchemaHash/叶子与节点）、`poseidon2-bn254-v1`（钉定的 width-4 常量 + KAT）、域标签、错误码。
- `experiments/g0/` — SPRT 整数态动态规划、JABO 经济模型、收敛 Gate、release 元数据。
- `experiments/g1/` — Python 参考实现（quantize / row_codec / poseidon / merkle）+ manifest 生成 + 跨语言 gate。
- `canonicalizer-go/internal/canonical/` — Go 验证器（gnark-crypto fr.Element 域运算）。
- `tee-evaluator-rust/src/bin/verify_vectors.rs` — Rust 验证器（crypto-bigint U256 原始算术）。
- `zk/circuits/row_commitment.go` + `zk/tests/` — gnark 电路内 width-4 Poseidon2 行承诺验证。
- `experiments/vectors/manifest.json` — 测试向量清单（17 positive + 3 negative + 2 generated）。
- `archive/` — 已被 G0/G1 取代的旧版代码与配置（旧 optimizer、旧报告生成器、旧 codec/merkle 等），仅供历史追溯。

## 关键设计决策

- **Poseidon2 width=4**：gnark-crypto v0.20.1 BN254 仅对 t∈{4,8,12,16} 硬编码审计常量；常量经 `canonicalizer-go/cmd/export-poseidon-params` 导出，四语言共用。
- **NaN / +Inf / −Inf 一律 REJECT**（`NON_FINITE_FEATURE`），不裁剪。
- **大向量容量 8192**：解释型语言在 131072 太慢；算法与容量无关，生产用 131072 同一代码路径。
- **BN254 标量域模量** = `0x30644e72e131a029b85045b68181585d2833e84879b9709143e1f593f0000001`（Rust 从 JSON 读取，不硬编码）。

## 不可妥协的协议不变量

1. 买方模型/验证集承诺必须在卖方数据根透露给评估方之前发布。
2. 每个证明与 attestation 都绑定 `chain_id`、`contract`、`transaction_id`、`policy_hash` 与单调递增的 session nonce。
3. 审计索引来自在其公布前已承诺的某个未来 drand 轮次。
4. 审计抽样绝不替代完整交付身份；买方始终重算完整根。
5. `INCONCLUSIVE` 永不视为 `PASS`。
6. Groth16 开发期 setup 产物绝不可复用于公开部署。

详见 `specs/protocol.md` 与 `experiments/reports/final-report.md`。

## 所需版本

- Go 1.22+（模块声明 1.25，工具链会自动下载）
- gnark 0.15.0 / gnark-crypto 0.20.1
- Rust stable（已在 1.97 验证）
- Python 3.12+
