# VALOR：权利感知、质量可验证与用途可审计的数据交易原型系统

> **Value-Aware Liability and Optimal Risk Allocation for Data Transactions**

以冻结版规范 **《VALOR_可实施原型系统_完整数学代码闭环与开发规范.md》** 为唯一设计依据，从零实现。本仓库不参考任何 DDTM 历史代码。

## 主链（规范 §1/§77）
```
Entitlement → QualityReference → DistributedQualityAudit → V̲_{D,R}^{gross}
→ Π_A^* → p̲_B^{sys} → B_S^* → (P_τ^{min},P_τ^{max}) → P_τ^* → UsageControl → S_T → Θ_{t+1}
```

## 当前进度：Phase 0–8 全部完成 ✅
- **Phase 0**：类型/参数治理（Gate phase0 全 PASS）。
- **Phase 1**：数据管线 + 质量 primitive reference/native + 复现 Gate B（7 primitive 全 PASS）。
- **Phase 2**：真实分布式质量节点（独立进程 + HTTP）+ Reverse VCG + BFT/liveness。
- **Phase 3**：审计校准 + Audit-VOI（贝叶斯风险/停止规则）+ 检测认证 p̲_B^sys。
- **Phase 4**：Data-VOI 估值（Oracle + 基线 + 保守下界 V̲_gross）。
- **Phase 5**：责任（B_S^*/pre-lock/资本成本）+ 定价（P_max/P_min/结算/NO_TRADE）+ 托管。
- **Phase 6**：用途控制（PDP/PEP/PIP/PXP + UsageReceipt）+ 数据流向血缘（hash 链）+ 交付模式。
- **Phase 7**：状态机（四终态）+ 结算 + 反馈（GroundTruthEligibilityGate）。
- **Phase 8**：实验/报告 + 全流程交易编排（主链完整数值闭环）。

## 真实 MNIST（本地缓存）
MNIST（60000×784）经 7891 SOCKS5 代理下载至 `data/raw/mnist/`（不入库）。
```bash
python scripts/train_mnist.py --epochs 3 --max-samples 5000   # 训练 MLP，test_acc≈0.87
python -c "from valor.data.download import load_dataset; h=load_dataset('mnist'); print(h.X.shape)"
```
依赖：`torch`（CPU，经代理 `pip install --proxy socks5h://127.0.0.1:7891 torch --index-url https://download.pytorch.org/whl/cpu`）、`pysocks`。

## 全流程交易（Phase 8 capstone）
```bash
python -m valor transaction run --config configs/experiments/full_transaction.json
```
从 Entitlement→QualityReference→Data-VOI→Audit-VOI→Certification→SellerBond→
Pricing→Clearing→StateMachine→Settlement→Feedback 全链计算，输出成交/不成交与全部数值，
生成 `reports/full_transaction.md` 与 `reports/figures/price_bounds.png`。

```bash
python -m valor experiment run --config configs/experiments/sweep.json   # 参数扫描
bash scripts/run-experiments.sh                                          # 一键复现
```

## 收敛层（Engine，P0–P13）：端到端可重放实验系统

把 VALOR 从"模块集合"收敛成**论文数学机制 = 代码真实执行 = 实验可复现**的闭环系统。
核心原则：每个箭头留下 machine-readable artifact，下游只读上游 artifact，禁止从 config 手填同一个量。

### 基础设施（`valor/engine/`）
- **RunManifest**：冻结单次 run 全部可复现性（commit/config/dataset/split/calibration/certificate/seed）。
- **TraceLedger**：统一 hash-chain 事件账本 `H_i = H(H_{i-1} ∥ Canonical(Event_i))`，`verify()` 全链重放。
- **StageResult / FormulaTrace**：主链阶段统一产出 + 公式对账（论文公式 = 代码执行）。
- **RunArtifacts**：`runs/<run_id>/` 目录落盘（manifest/trace/state/money/lineage/report）。
- **DatasetAdapter / TrainerAdapter**：MNIST 等数据集/训练器抽象，VALOR 估值层只消费 `y_true/y_pred/probability/训练元数据`。
- **CapstoneScenario**：冻结一次完整交易的全部输入（五角色数据隔离 / N_b / payoff / 权利 / 审计市场 / 安全参数）。

### 关键修复（对接交文档）
- **P4 quorum-by-result**：分布式审计要求同一结果 ≥ q 个一致 evidence（`#{i:Y_i=y^*}≥q`），非 `evidence_count≥q`；离线节点从备用池替换。
- **P5 VCG cost + 证据后验**：Audit-VOI 用 Reverse VCG 支付作为 `MC_A^pay`，后验由真实证据 Bayes 更新（非 config）。
- **P6 离线校准**：受控 breach injection → 检测 TP/FN → Beta 下界 `p̲_B^sys` 冻结；似然由检测敏感度/误报派生。
- **P7 Seller Bond IC 对账**：输出 `constraint_lhs/rhs/slack`，`slack≥−tol` 才 PASS。
- **P8 MoneyLedger**：语义化资金事件（payer/recipient/trigger 白名单），退款用实际锁定 escrow 而非 price=0。
- **P11 FullChainGate**：G1–G33 论文闭合门，全部 PASS 才输出 `Paper Closure Gate = PASS`。

### 使用（Engine CLI）
```bash
# 1. 离线校准（受控注入 → TP/FN → 冻结 likelihood/certificate/valuation artifact）
python -m valor engine calibrate --dataset breast_cancer --out-dir calibration

# 2. MNIST Capstone 交易（真分布式审计 + 冻结 calibration → FullChainGate）
python -m valor engine capstone --scenario <scenario.json> --run-dir runs \
    --calibration-dir calibration/<run_id>/calibration_bundle.json

# 3. 五场景验收 C0–C4（TRADE / NO_TRADE / SELLER_BREACH / BUYER_BREACH）
python -m valor engine acceptance --run-dir runs/acceptance

# 4. RQ 实验（Level 1 公式对账 + Level 4 多 seed paired trials + 统计）
python -c "from valor.engine.experiments import level1_reconciliation; print(level1_reconciliation())"
```

示例（Python）：
```python
from valor.engine import CapstoneScenario, run_capstone
sc = CapstoneScenario(scenario_id="paper-demo", seller_id="seller-1", buyer_id="buyer-1")
sc.trainer.update({"epochs": 3})
sc.buyer_task["deployment_scale"] = 100000
res = run_capstone(sc, run_dir="runs", calibration=bundle)   # bundle = 离线校准
print(res.decision, res.clearing_price, res.full_chain_gate["paper_closure_gate"])
```

## 目录结构
```
pyproject.toml        # 包元数据 + 依赖（规范 §72）
valor/                # 机制实现 + 实验代码（Python 包）
  engine/             # P0-P13 收敛层（orchestrator/calibration/gate/acceptance/experiments）
  adapters/           # DatasetAdapter/TrainerAdapter（MNIST）
valor/configs/        # 配置（JSON + JSON Schema；参数显式无默认值）
docs/                 # ARCHIVE_SPEC / VERSION_CONTROL_SPEC / DESIGN_DECISIONS
tests/                # 单元测试（unit/ + engine/）
scripts/              # 一键复现脚本
data/                 # 数据集（raw/prepared 不入库）
raw/  runs/           # 实验原始结果（gitignore）
reports/              # 实验报告（figures 不入库）
```

## 使用
```bash
# 安装
python -m pip install -e ".[dev]"

# CLI（规范 §71）
python -m valor --version
python -m valor transaction run --config configs/example.transaction.json

# Phase 1：质量 primitive 复现 Gate（写 reports/quality_reproduction/*.json）
python -m valor quality reproduce --config configs/quality/reproduce.json

# Phase 0 验收 Gate（检查单 T：输出机器可读 JSON，8 大硬 Gate）
python -m valor gate phase0 --config tests/fixtures/phase0_valid.json

# 业务默认值静态扫描（检查单 H）
python scripts/check_business_defaults.py --root valor

# 测试（unit + property）
python -m pytest
```

## 文档
- `docs/ARCHIVE_SPEC.md` — 目录归档规范
- `docs/VERSION_CONTROL_SPEC.md` — 版本控制规范（提交/门禁）
- `docs/DESIGN_DECISIONS.md` — 设计决策（D100 起）
- `VALOR_可实施原型系统_完整数学代码闭环与开发规范.md` — 唯一规范文档
