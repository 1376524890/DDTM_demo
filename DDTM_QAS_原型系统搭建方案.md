# DDTM-QAS 原型系统搭建与编程实施方案

## 0 交付说明

本方案与《DDTM-QAS 论文设计文档》逐项对齐，代码仓库目录为 `ddtm-qas-prototype/`。方案规定的协议字段、哈希标签、电路公开输入、智能合约状态、实验参数和文件路径不得由开发者自行更名或改变语义。硬件专用 TDX/SEV-SNP Quote 生成依赖实际平台，仓库提供严格接口和 Mock 后端；Mock 仅用于功能开发，不能作为安全实验结果。

## 1 固定决策

| 项目 | 最终选择 |
|---|---|
| 任务 | 表格二分类 |
| 数据规模 | 最大 100000 行，物理 128 维 |
| 模型 | 公开 128-64-1 ReLU MLP，参数私密 |
| 验证集 | 买方私密，评估前承诺 |
| 证明 | Groth16/BN254，正式版多方可信设置 |
| TEE | Intel TDX 或 AMD SEV-SNP；本地 Mock |
| 哈希 | 电路内和 Merkle 使用 Poseidon2；对象摘要 SHA-256 |
| 加密 | XChaCha20-Poly1305；X25519+HKDF 会话密钥 |
| 随机数 | 未来 drand 轮次，BLS 验证由 2/3 中继签名上链 |
| 审计 | AuditBatch-64 + 四轮 17 位 Feistel + Wald SPRT |
| 经济机制 | JABO 动态规划 + 最低保证金公式 |
| 本地硬件 | 16-32 核、64-128 GB、2×RTX 4090 |

## 2 仓库和环境

### 2.1 目录

```text
ddtm-qas-prototype/
├── specs/
├── canonicalizer-go/
├── tee-evaluator-rust/
├── zk/
├── contracts/
├── services/policy_optimizer/
├── ml/
├── experiments/
├── deployment/
├── docker-compose.yml
└── Makefile
```

### 2.2 系统安装

Ubuntu 24.04：

```bash
sudo apt update
sudo apt install -y build-essential git curl jq pkg-config libssl-dev \
  libsodium-dev protobuf-compiler docker.io docker-compose-plugin \
  postgresql-client clang cmake
sudo usermod -aG docker "$USER"
```

安装 Go 1.25.x。不要使用系统 Go 1.23 编译 gnark 0.15：

```bash
cd /tmp
curl -LO https://go.dev/dl/go1.25.6.linux-amd64.tar.gz
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.25.6.linux-amd64.tar.gz
echo 'export PATH=/usr/local/go/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
go version
```

安装 Rust：

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
rustup update stable
rustc --version
```

安装 Foundry：

```bash
curl -L https://foundry.paradigm.xyz | bash
source ~/.bashrc
foundryup
forge --version
```

Python：

```bash
sudo apt install -y python3.11 python3.11-venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements.txt
pip install -r services/policy_optimizer/requirements.txt
```

Docker 服务：

```bash
cp .env.example .env
# 修改所有密码
docker compose up -d postgres minio anvil
docker compose ps
```

### 2.3 GPU 分配

GPU0：PyTorch 训练和完整重训练 oracle。

```bash
export CUDA_VISIBLE_DEVICES=0
python ml/train_buyer_model.py ...
```

GPU1：gnark ICICLE 证明工作进程。ICICLE 为实验加速，必须保留 CPU 后端。若 AuditBatch-64 超出 24 GB 显存，不能删除安全约束，应切换 CPU 或并行处理更小批次并更新固定电路版本和 PolicyRegistry。

## 3 阶段一：冻结规范

开发开始前，审核并锁定：

- `specs/canonical-data-v1.md`
- `specs/protocol.md`
- `specs/threat-model.md`
- `specs/state-machine.md`

任何字段修改都必须：提升 schema/version；重新构建数据根；重新编译电路；重新执行 Groth16 设置；部署新 verifier；发布新 policyHash。

## 4 数据准备、规范化与 Merkle 根

### 4.1 准备公开数据

将原始数据转换为 CSV 或 Parquet，标签列必须是严格二分类。执行：

```bash
source .venv/bin/activate
python ml/prepare_tabular.py \
  --input data/raw/covertype.parquet \
  --label target \
  --output data/prepared/covertype \
  --seller-rows 100000 \
  --validation-rows 20000 \
  --seed 20260721
```

输出：

```text
base.npz
validation.npz
seller.npz
validation-canonical-input.csv
seller-canonical-input.csv
preprocessing-policy.json
```

必须将 `preprocessing-policy.json` 的 SHA-256 作为 schemaHash 来源。训练、验证和卖方数据使用完全相同的列顺序、裁剪、缩放、特征选择和 Q16.16 规则。

### 4.2 编译规范化工具

```bash
cd canonicalizer-go
go mod download
go build -o ../bin/ddtm-canonicalize ./cmd/ddtm-canonicalize
cd ..
```

### 4.3 构建卖方与验证集根

```bash
mkdir -p artifacts/data
bin/ddtm-canonicalize \
  --input data/prepared/covertype/seller-canonical-input.csv \
  --schema data/prepared/covertype/preprocessing-policy.json \
  --output artifacts/data/seller.canonical.bin \
  --manifest artifacts/data/seller.manifest.json \
  --dataset-version 1

bin/ddtm-canonicalize \
  --input data/prepared/covertype/validation-canonical-input.csv \
  --schema data/prepared/covertype/preprocessing-policy.json \
  --output artifacts/data/validation.canonical.bin \
  --manifest artifacts/data/validation.manifest.json \
  --dataset-version 1
```

### 4.4 必须执行的跨语言测试

1. 同一 CSV 重复运行根完全一致；
2. 修改任意一个 bit，根改变；
3. 交换两行，根改变；
4. 改 schemaHash，根改变；
5. 空值从“真实零”改为“缺失零”，根改变；
6. 100000 行后的填充叶子完全确定；
7. Merkle path 对正确根通过，对错误 index/row/path 拒绝。

## 5 买方模型和审计探针

### 5.1 训练固定结构模型

```bash
CUDA_VISIBLE_DEVICES=0 python ml/train_buyer_model.py \
  --base data/prepared/covertype/base.npz \
  --validation data/prepared/covertype/validation.npz \
  --output artifacts/model/model-q16.json \
  --epochs 30 \
  --seed 20260721 \
  --device cuda:0
```

训练脚本必须：固定随机种子；保存最佳验证 hinge loss；导出 128×64、64、64、1 个 Q16.16 参数；拒绝 int32 溢出。模型结构写入 policy，不允许交易期间改变隐藏层宽度、激活或损失函数。

### 5.2 审计探针

审计探针采用线性分类器，参数需导出为：

```json
{
  "weights_q8_8": [128个int16],
  "bias_q24": "int64",
  "center_q16_16": [128个int32],
  "inv_scale_sq": [128个uint20],
  "margin_threshold_q24": "int64",
  "distance_threshold_raw": "uint96",
  "missing_threshold": 16
}
```

探针应在买方验证集或独立校准集上训练，并在卖方 cD 进入评估之前生成 cA。禁止根据卖方样本重新选择阈值。保形阈值的校准记录包含样本 ID、非一致性分数、α 和 quantile 计算方式，并写入 policyHash。

## 6 TEE Evaluator

### 6.1 编译 Mock 后端

```bash
cd tee-evaluator-rust
cargo build --release
cd ..
```

Mock 运行：

```bash
tee-evaluator-rust/target/release/ddtm-tee-evaluator evidence \
  --report-data-hex $(printf '00%.0s' {1..64})
```

输出必须包含 `development_only=true`。合约正式网络必须拒绝 Mock measurement。

### 6.2 UtilityPolicy

创建 `artifacts/policy/utility-policy.json`：

```json
{
  "learning_rate": 655,
  "gradient_clip": 327680,
  "delta_clip": 65536,
  "mom_groups": 31,
  "lambda_mad": 65536,
  "lambda_shift": 16384,
  "lambda_linear": 32768,
  "min_utility": 65,
  "max_linear_error": 32768,
  "max_shift": 131072
}
```

Rust `Fixed` JSON 表示为 Q16.16 原始整数。上述参数仅为初始实验政策，必须通过 validation-only 调参和敏感性实验冻结；不能查看卖方测试结果后修改。

### 6.3 执行完整效用评估

```bash
tee-evaluator-rust/target/release/ddtm-tee-evaluator evaluate \
  --seller artifacts/data/seller.canonical.bin \
  --seller-rows 100000 \
  --validation artifacts/data/validation.canonical.bin \
  --validation-rows 20000 \
  --model artifacts/model/model-q16.json \
  --policy artifacts/policy/utility-policy.json \
  --seed-hex <32字节承诺种子> \
  --output artifacts/reports/utility-report.json
```

Evaluator 执行顺序：验证文件长度和 row_id；验证模型形状；流式累计卖方梯度；累计验证梯度；裁剪平均梯度；构造 θ'；计算每个验证样本的 clipped loss delta；按确定性组哈希计算 31 组均值；计算 median 和 MAD；计算一阶 dot product、E_lin 和 shift；计算 U_cert 和 pass。

### 6.4 真实 TDX/SEV-SNP 适配

实现 `AttestationProvider`：

```rust
pub trait AttestationProvider {
    fn evidence(&self, report_data: &[u8;64]) -> Result<Evidence>;
}
```

TDX：使用 DCAP Quote Generation Library 生成 Quote，将 X25519 临时公钥、报告签名公钥、policyHash、sessionId 和镜像 digest 的哈希写入 REPORTDATA。中继使用 Quote Verification Library、PCK/TCB/CRL 验证，并拒绝过期或不可接受 TCB。

SEV-SNP：通过 guest ioctl 获取 attestation report，将同一 64 字节 report_data 写入用户数据；中继验证 VCEK 证书链、chip_id、TCB 和 measurement。

严格要求：私钥只在 VM 内生成；认证通过前不释放模型或数据密钥；每次会话使用新临时密钥；会话结束后 zeroize；report_data 与链上 sessionId 一一绑定。

## 7 Groth16 电路

### 7.1 编译测试

```bash
cd zk
go mod download
go test ./...
```

### 7.2 UtilityThresholdCircuit

文件：`zk/circuits/utility_threshold.go`。

公开输入固定顺序：

```text
TID, DataRoot, ModelCommitment, ValidationRoot, MetricsCommitment,
PolicyHash, SessionHash, MinUtilityEnc, MaxLinearError, MaxShift,
LambdaMAD, LambdaShift, LambdaLinear
```

私有见证：UMomEnc、MAD、Shift、LinearError、UCertEnc、MetricsBlind。

电路关系：

```text
MetricsCommitment = Poseidon2(TAG_METRICS, transaction bindings, metrics, blind)
UCertEnc = UMomEnc - λmad*MAD - λshift*Shift - λlinear*LinearError
UCertEnc >= MinUtilityEnc
LinearError <= MaxLinearError
Shift <= MaxShift
all values satisfy explicit bit ranges
```

### 7.3 AuditBatchCircuit

文件：`zk/circuits/audit_batch.go`。固定 64 条，变更批大小意味着新电路和新 policy。

每条见证：index、valid、label bit、timestamp、128 个 mask bit、128 个特征 offset 编码、19 个 packed features、两个 mask limb、17 个 sibling。

电路必须执行：

```text
expectedIndex = Feistel17(seed, batchNumber*64+i)
row.index == expectedIndex
row.index < rowCount
leaf(row) + MerklePath == DataRoot
AuditCommitment opens to private probe
linear margin, diagonal distance, missing count are computed exactly
failed flag is correct
NewN = PreviousN + 64
NewFailures = PreviousFailures + sum(failed)
```

注意：真实 rowCount 小于 2^17 时，Feistel 可能产生 padding index。生产版本必须实现确定性 cycle-walking：对结果 >=rowCount 的索引，将 permutation 再次应用，直到进入 [0,rowCount)。必须在原生索引生成器和电路中使用相同最大轮数，并证明在政策支持的 rowCount 下不会超过该上限。仓库当前 `Feistel17` 是核心置换，cycle-walking 是进入正式 100000 行实验前必须完成的 P0 任务。

### 7.4 开发 Setup

```bash
go run ./cmd/setup \
  --circuit utility \
  --out ../artifacts/zk/utility \
  --unsafe-development-setup

go run ./cmd/setup \
  --circuit audit \
  --out ../artifacts/zk/audit \
  --unsafe-development-setup
```

开发 artifact 必须标记 UNSAFE_DEVELOPMENT_SETUP，不得部署到公开网络。

### 7.5 正式多方设置

1. 发布固定 R1CS 和 SHA-256；
2. 使用 gnark BN254 mpcsetup 执行 Phase 1/2；
3. 至少 5 个独立参与者顺序贡献；
4. 每次贡献验证 transcript；
5. 最终 PK、VK、R1CS、transcript 全部发布摘要；
6. VK 导出 Solidity；
7. verifier bytecode hash 和 circuit hash 写入 PolicyRegistry。

## 8 drand 和抽样

### 8.1 未来轮次

挂牌时记录 `beaconId` 和 `futureRound`。futureRound 必须晚于数据根、模型承诺和审计探针承诺全部确认后的时间。

### 8.2 中继

三台独立中继执行：

1. 从多个 drand endpoint 获取相同 round；
2. 验证 chain hash、round、previous signature/unchained 规则和 BLS 签名；
3. 重算 randomness；
4. 对 `(chainId, RandomnessRegistry, beaconId, round, signatureHash, randomness)` ECDSA 签名；
5. 合约要求地址严格递增的 2/3 签名，防止重复计数。

不要只把 drand HTTP 返回的 `randomness` 当作可信值。

### 8.3 cycle-walking

对于 N=100000：

```text
x = Feistel17(seed, ordinal)
while x >= N:
    x = Feistel17(seed, x)
return x
```

因为 Feistel 是置换，cycle-walking 在子域上仍产生置换。电路需要固定最大迭代，例如 16 次，并为每轮提供 active bit；若超过上限，政策拒绝该 rowCount/seed 组合并换用下一 future round。测试应覆盖 100000 行下至少 10^7 个 ordinal/seed 组合的迭代次数分布。

## 9 序贯检验与 JABO

### 9.1 运行默认策略

```bash
python services/policy_optimizer/optimizer.py \
  --config experiments/configs/policy-default.json \
  --output experiments/policy-default-result.json
```

已验证输出：10% 异常率拒绝概率 0.951215；平均样本 214.34；示例最低保证金 3141.09。

### 9.2 上链整数化

合约不使用浮点或 log。离线计算：

```text
hit_increment_q32 = round(log(tau1/tau0)*2^32)
clean_increment_q32 = round(log((1-tau1)/(1-tau0))*2^32)
upper_q32 = round(log((1-beta)/alpha)*2^32)
lower_q32 = round(log(beta/(1-alpha))*2^32)
```

合约根据 `(n, failures)` 计算：

```text
llr = failures*hit_increment_q32 + (n-failures)*clean_increment_q32
```

不要接受协调器自由提供 decision。仓库合约中的 `decideAudit()` 目前标注为原型协调器版，正式论文实验前必须改为合约内部确定性计算，这是 P0 必修补丁。

### 9.3 保证金

合约公式：

```text
covered = ceil((Gmax + safetyMargin)*1e6/detectionPpm)
B = max(0, covered - price)
```

Gmax 来源必须记录：行业单位标注/清洗成本上界，或 κP 保守模型。论文必须做 κ∈{0.25,0.5,1,1.5,2} 敏感性分析。

## 10 智能合约部署

### 10.1 安装依赖

```bash
cd contracts
forge install OpenZeppelin/openzeppelin-contracts --no-commit
forge build
forge test -vv
```

### 10.2 部署顺序

1. Utility verifier 和 Audit verifier adapter；
2. PolicyRegistry；
3. AttestationRegistry；
4. RandomnessRegistry；
5. DDTMMarketplace；
6. 设置批准 TEE measurements；
7. 发布 PolicyRecord；
8. 冻结生产 owner 到多签或时间锁。

### 10.3 必须修复的生产差异

仓库提供的是可编程核心骨架，以下项目在正式结果前必须完成：

- generated verifier 与统一 adapter 的真实输入布局；
- 合约内部 LLR 决策，删除自由 decision 参数；
- dispute 和 attested delivery receipt 完整状态；
- 所有 deadline 和 timeout；
- `conditional` 状态支付审计成本；
- EIP-712 结构化签名替代 personal_sign；
- 事件中公开完整 listing id；
- verifier/policy/session/transcript 的全部重复绑定检查；
- fuzz、invariant 和重入测试。

## 11 加密交付

### 11.1 分块

使用 8 MiB chunk。每块生成 24 字节随机 nonce，AAD：

```text
tid || dataRoot || schemaHash || chunkIndex || totalChunks || manifestVersion
```

清单包含 ciphertext SHA-256、nonce、size、totalChunks、canonical data SHA-256 和 dataRoot。密文上传 MinIO 后，先验证对象 HEAD/size 和 SHA-256，再提交 manifestDigest。

### 11.2 密钥封装

买方提供 X25519 公钥。卖方生成 32 字节数据密钥 KD，通过 X25519+HKDF 生成 KEK，使用 XChaCha20-Poly1305 封装 KD。AAD 绑定 tid、buyer、dataRoot 和 manifestDigest。

### 11.3 买方验证

买方必须：验证 envelope；逐块 AEAD 解密；校验 chunk digest；拼接 canonical binary；校验 canonical SHA-256；重新构建所有 Poseidon2 叶子和完整根；确认 cD。任何一步失败均不得确认。

## 12 端到端执行顺序

```text
1 BuyerPrepare: train model/probe, build cM/cV/cA, publish commitments
2 SellerCanonicalize: build canonical.bin, manifest, cD
3 PolicyOptimize: calculate audit policy and required bond
4 List: seller posts cD/policy/future drand and bond
5 Bid: buyer escrows price
6 RegisterTEE: verify quote and register session
7 SecureUpload: seller data and buyer assets encrypted to TEE
8 EvaluateARUC: full evaluation, report, metrics commitment
9 ProveUtility: generate and verify UtilityThreshold proof
10 FetchDrand: relay verifies future round
11 StartAudit
12 AuditLoop: build 64-row witness, prove, update n/failures, contract computes LLR
13 Accept/Reject/Inconclusive
14 EncryptDelivery: XChaCha chunks and manifest
15 CommitCiphertext
16 ReleaseKeyEnvelope
17 BuyerFullRootCheck
18 Confirm or OpenDispute
19 AttestedDisputeVerification
20 Settle and withdraw
```

## 13 测试清单

### 13.1 单元测试

- Fixed add/sub/mul overflow；
- model shape/forward/hinge/gradient；
- MoM deterministic grouping；
- shift bounds；
- row marshal and feature packing；
- native Poseidon and circuit Poseidon cross-test；
- Feistel permutation covering 0..131071 exactly once；
- cycle-walking uniqueness for N=100000；
- Merkle path；
- audit integer score native/circuit equality；
- SPRT DP probability mass equals 1；
- bond formula monotonicity。

### 13.2 合约 fuzz/invariant

- escrow+bond conservation；
- credits never exceed deposits；
- only legal state transitions；
- unique request IDs；
- old session/randomness/proof cannot replay；
- refund and seller settlement mutually exclusive；
- INCONCLUSIVE never auto-confirms；
- verifier public inputs exactly match listing commitments。

### 13.3 攻击测试

行调换、标签翻转、Merkle sibling 修改、错误 index、错误 model commitment、审计探针替换、未来随机轮次替换、密文 bit flip、AAD 变化、旧 quote replay、旧 transcript、买方假 manifest、卖方评估后调包。

## 14 性能实验命令模板

```bash
# 机制仿真
python services/policy_optimizer/optimizer.py --config ... --output ...

# 污染数据
python ml/contaminate.py --input seller.npz --output seller-label10.npz --rate 0.10 --type label-flip

# ZK 约束和证明基准
/usr/bin/time -v go test -run TestUtilityBenchmark -v ./zk/...
CUDA_VISIBLE_DEVICES=1 /usr/bin/time -v <icicle proof command>

# 合约 gas
cd contracts && forge test --gas-report

# GPU 监控
nvidia-smi dmon -s pucvmet -d 1 -o DT > experiments/logs/gpu.csv

# CPU/内存
/usr/bin/time -v tee-evaluator-rust/target/release/ddtm-tee-evaluator evaluate ...
```

所有性能表必须记录：git commit、policyHash、circuit hash、R1CS constraints、CPU 型号、RAM、GPU/driver/CUDA、TEE 类型、操作系统、编译参数和随机种子。

## 15 开发里程碑和验收

### M1 规范与数据根

验收：100000×128 数据根可重复，跨语言一致；所有篡改测试通过。

### M2 ARUC

验收：Rust 固定点结果与 Python 参考误差在规定量化范围；完整 100000 行评估运行；UtilityThreshold proof 上链验证。

### M3 ZASA

验收：Feistel/cycle-walking 无重复；AuditBatch-64 native/circuit 一致；SPRT 10% 检出≥95%，5% 误拒≤1%。

### M4 JABO 和合约

验收：合约内部 LLR；动态保证金；资金守恒 invariant；所有超时与争议完成。

### M5 安全 TEE

验收：真实 TDX/SNP quote；错误 measurement、过期 TCB、report_data 不匹配和 replay 全部拒绝。

### M6 论文实验

验收：三数据集、八污染率、全部基线和消融；所有原始日志与分析脚本可复现。

## 16 当前代码状态和诚实边界

交付仓库包含协议规范、确定性行编码和 Poseidon2 Merkle 核心、Rust 固定点 MLP/ARUC 核心、UtilityThreshold 和 AuditBatch 电路核心、JABO 动态规划、合约注册表和市场状态机骨架、数据准备和污染脚本。

由于当前执行环境没有 Go 1.25 依赖下载、真实 TDX/SNP 硬件和 Foundry 依赖缓存，本次交付不能诚实声称仓库已经完成全量编译和真实远程认证。文档已经明确列出正式结果前的 P0 补丁，尤其是 cycle-walking、电路与 native Poseidon 交叉测试、合约内部 LLR、generated verifier adapter 和真实 attestation backend。开发时不得跳过这些事项，也不得将 Mock 结果写成安全实验结果。
