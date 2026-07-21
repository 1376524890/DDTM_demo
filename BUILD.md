# DDTM-QAS 构建与开发指南

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Ubuntu | 24.04 LTS | 推荐操作系统 |
| Go | 1.25+ | gnark 0.15 依赖 |
| Rust | 1.88+ (stable) | TEE 评估器 |
| Python | 3.11+ | ML 训练与策略优化 |
| Foundry | latest stable | Solidity 合约 |
| Docker | 27+ | PostgreSQL/MinIO/Anvil 服务 |
| GPU | 2×RTX 4090 (可选) | 模型训练与 ZKP 加速 |

## 快速开始

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y build-essential git curl jq pkg-config libssl-dev \
  libsodium-dev protobuf-compiler docker.io docker-compose-plugin \
  postgresql-client clang cmake
sudo usermod -aG docker "$USER"
# 重新登录以使 docker 权限生效
```

### 2. 安装 Go 1.25

```bash
cd /tmp
curl -LO https://go.dev/dl/go1.25.6.linux-amd64.tar.gz
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.25.6.linux-amd64.tar.gz
echo 'export PATH=/usr/local/go/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
go version  # 应显示 go1.25.6
```

### 3. 安装 Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
rustup update stable
```

### 4. 安装 Foundry

```bash
curl -L https://foundry.paradigm.xyz | bash
source ~/.bashrc
foundryup
```

### 5. 安装 Python 依赖

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r ml/requirements.txt
pip install -r services/policy_optimizer/requirements.txt
```

### 6. 启动 Docker 服务

```bash
cp .env.example .env
# 编辑 .env 修改密码
docker compose up -d postgres minio anvil
docker compose ps
```

### 7. 安装合约依赖

```bash
cd contracts
forge install OpenZeppelin/openzeppelin-contracts --no-commit
cd ..
```

### 8. 构建所有组件

```bash
# 数据规范化工具
make canonicalizer

# TEE 评估器
make evaluator

# ZK 电路测试
make zk-test

# ZK 开发设置 (UNSAFE - 仅用于开发)
make zk-setup

# 策略优化器
make optimizer

# 合约构建与测试
make contracts-build
make contracts-test
```

## 目录结构

```
ddtm-qas-prototype/
├── specs/                  # 冻结规范 (v1)
│   ├── canonical-data-v1.md
│   ├── protocol.md
│   ├── threat-model.md
│   └── state-machine.md
├── canonicalizer-go/       # Go: 数据规范化 + Poseidon2 Merkle
│   ├── cmd/ddtm-canonicalize/
│   ├── internal/codec/
│   └── internal/merkle/
├── tee-evaluator-rust/     # Rust: TEE 效用评估 + 审计探针
│   └── src/
│       ├── attestation/    # Mock + TDX/SEV-SNP 接口
│       ├── fixed.rs        # Q16.16 定点算术
│       ├── model.rs        # 128-64-1 MLP
│       ├── utility.rs      # ARUC 评估
│       ├── audit.rs        # 审计探针评分
│       └── crypto.rs       # XChaCha20-Poly1305 + X25519
├── zk/                     # Go: gnark Groth16 电路
│   ├── circuits/
│   │   ├── utility_threshold.go
│   │   ├── audit_batch.go
│   │   ├── merkle.go
│   │   ├── feistel.go
│   │   ├── cyclewalk.go
│   │   └── native_helpers.go
│   └── cmd/
│       ├── setup/
│       ├── prove-utility/
│       └── prove-audit/
├── contracts/              # Solidity: 市场合约 + 注册表
│   ├── src/
│   │   ├── DDTMMarketplace.sol
│   │   ├── PolicyRegistry.sol
│   │   ├── AttestationRegistry.sol
│   │   └── RandomnessRegistry.sol
│   └── test/
├── services/policy_optimizer/  # Python: JABO 动态规划
├── ml/                     # Python: 数据准备 + 模型训练
├── experiments/            # 实验配置与结果
├── deployment/             # 部署脚本
└── docker-compose.yml      # 本地服务
```

## 开发工作流

### 端到端流程 (Mock 模式)

```bash
# 1. 准备数据
make data-prep

# 2. 训练买方模型
make model-train

# 3. 训练审计探针
make probe-train

# 4. 构建规范化数据
make canonicalizer
make canonicalize

# 5. 构建评估器
make evaluator

# 6. 执行效用评估
make evaluate

# 7. 运行策略优化
make optimizer

# 8. 构建和测试合约
make contracts-build
make contracts-test
```

## 安全注意事项

1. **开发 ZK 设置**: `--unsafe-development-setup` 标志仅用于本地开发。生产环境必须执行多方可信设置。
2. **Mock TEE**: Mock 后端 (`development_only=true`) 仅用于功能测试。合约正式网络必须拒绝 Mock measurement。
3. **INCONCLUSIVE 状态**: 永远不自动结算给卖方。
4. **GPU 安全边界**: RTX 4090 不属于机密计算硬件。正式安全演示必须使用 TDX/SEV-SNP 机密虚拟机。

## P0 必修补丁 (正式实验前)

参见 [P0-ISSUES.md](P0-ISSUES.md)。
