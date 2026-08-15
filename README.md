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

## MNIST 完整交易流程（数值实例）

> 以下是一次真实 MNIST 完整交易（`CapstoneScenario` 默认场景）逐步执行与求值记录，
> 对应 `runs/<run_id>/` 下 `report.json` / `transaction_trace.jsonl` / `manifest.json`。
> **场景冻结**：MNIST（60000×784，10 类），五角色划分
> `historical 25% / buyer_base 20% / seller_candidate 5% / transaction_eval 10% / FinalEvaluation 40%`，
> 训练器 `MNISTMLP(784→128→64→10, epochs=3, lr=1e-3)`，部署规模 `N_b = 100,000`，
> 审计市场 `n_nodes=10, f=2 → m=7, q=5`，权利束 `q=3 次 / digit-classification / COMPUTE_ONLY`，
> seed = 0。离线校准（受控 duplicate 注入 → TP/FN）已冻结 likelihood/certificate/valuation artifact。

### 步骤与求得值

| 阶段 | 公式 / 动作 | 求得的数值 |
|---|---|---|
| **0. Listing** | 上架 `Z_τ=(A_D,R_τ)` | `listing_id=list-8f09…`，`product_hash=a1e522…`，`rights_hash=7ea25d…` |
| **1. Entitlement** | 资格/合规门 | `pass=true` |
| **2. Data-VOI** | `U_b(θ)=N_b Σ P̂(y,ŷ)r_{y,ŷ}` | `U_base=62,066.67`，`U_plus=65,266.67`，`ΔU=3,200.00` |
| | 竞争外部性 `L_comp` | `L_comp=2.0` |
| | `V_gross = ΔU − L_comp` | `V_gross = 3,198.00` |
| | 保守下界 `V̲_gross = V_gross + Q_{α_V}(e)` | `V̲_gross = 3,204.65`（calibration residual） |
| **3. Audit-VOI** | Reverse VCG 委员会（m=7） | `winner_set = node-0…node-6`，`MC_A^pay = Σ VCG = 119.0` |
| | 分布式审计执行 + quorum | `BFT = CERTIFIED`，`outcome = PASS`（≥5 个一致 PASS） |
| | 证据后验 `Bayes update` | `posterior = {P(G)=0.80, P(L)=0.20, P(B)=0.00}` |
| | 审计支付 | `audit_pay_s = 59.5`，`audit_pay_b = 59.5` |
| **4. Certification** | `p̲_B^sys = Q_{α_D}[Beta(a_D+TP, b_D+FN)]` | `p̲_B^sys = 0.82925` |
| **5. Seller Bond** | `B_S^* = ( (G^dev+ε)/p̲_B^sys − p_{e,F}F_S ) / (p_{e,Bond}λ_S)` | `B_S^* = B_S^pre = 141.12` |
| | 资本成本 `C_B^cap = κ_S(B_S^pre T_pre + B_S^* T_post)` | `C_B^cap = 28.22` |
| | 激励约束对账 | `LHS = 61.0`，`RHS = 61.0`，`slack = 0.0`，`PASS` |
| **6. Pricing** | `P_max = min[W_B^rem, V̲_gross − C_I − C_{A,B}^pay − C_R^pay − C_{B,use}^cap − R_B^post]` | `P_max = 500.00` |
| | `P_min = c^marg + C_{A,S}^pay + C_B^cap + C_{R,S}^pay + R_S^post + OC_S + Π_S^0` | `P_min = 115.72` |
| | `M_T = P_max − P_min` | `margin = 384.28` |
| **7. Clearing** | `P^* = P_min + β_bar·M_T`（β_bar=0.5） | `P* = 307.86`，`decision = TRADE` |
| **8. Settlement** | MoneyLedger 语义资金流 | `E_B^P → seller`：**307.86 CU**（数据成交价）；`conservation=true`，payer/recipient 语义全对 |
| **9. Usage** | PDP/PEP + UsageReceipt + Lineage hash-chain | 6 请求：`ALLOW,ALLOW,ALLOW,DENY,DENY,DENY`（前 3 次正确用途，之后超上限/错误主体/错误用途）；`chain_valid=true` |
| **10. Feedback** | `Θ_t → Θ_{t+1}` + realised Data-VOI | `Theta(1,1) → Theta(2,1)`（CONTROLLED_CANARY，`theta_updated=true`）；`realised_data_voi = 2,250.00`（FinalEvaluation） |

### 最终结果

```
decision = TRADE
clearing_price (P*) = 307.86 CU
terminal_state = TRADE
FullChainGate = PASS (33/33)   # Paper Closure Gate = PASS
```

### 可复现性（manifest.json 冻结）

```
run_id  = run-d00fddc1d0a147febd452897
tx_id   = tx-e1fad3dbe48d316d1a6ef200
config_hash            = 502ae429…
dataset_hash           = 4b3d399b…
split_hash             = c9a14cd2…
trainer_hash           = 87262fa2…
valuation_calibration_hash = 607034e8…
certificate_hash       = 4df1b882…
seed                   = 0
git_commit             = 13dd545f…
manifest_hash          = 423c2578…
```

> 该实例对应 9 个 artifact：`manifest.json` / `scenario.json` / `transaction_trace.jsonl` /
> `formula_trace.jsonl` / `state_trace.jsonl` / `money_ledger.jsonl` / `lineage.jsonl` /
> `report.json` / `report.md`。每个数值均可从上游 artifact 手动复算（下游只读上游，不手填）。

### 审计效果验证：零知识审计 vs 常规训练 baseline

在本地 MNIST 上实证：在卖方候选数据注入真实质量缺陷，对比「交易前零知识审计」与「常规训练 baseline」。

```bash
python scripts/audit_effectiveness.py --samples 4000 --epochs 1 --label-flip 0.2
```

| 候选数据 | baseline 训练后精度 | 精度变化 | 零知识审计 outcome | 审计信号 |
|---|---|---|---|---|
| 干净 | 0.8859 | — | `PASS` | 漂移 0/3，min_p=0.64 |
| covariate shift | 0.8825 | **−0.0034**（几乎无法察觉） | `QUALITY_FAIL` | 漂移 **3/3**，min_p=**0.00** |
| label 污染 20% | 0.8901 | +0.0042（被 base 稀释，无下降） | `QUALITY_FAIL` | CL label_error **0.19→0.38** |

**结论**：
- **covariate shift**：baseline 事后训练精度仅降 0.0034（几乎无法察觉）；审计在**交易前**即检测出（`QUALITY_FAIL`，3/3 显著漂移特征）→ 审计显著优于 baseline。
- **label 污染**：baseline 精度甚至不变/略升（污染被 20k base 数据稀释）；审计通过 Confident Learning 检测到候选内部 label 误差率 0.19→0.38 → 检测出。

→ **证明零知识审计在训练前即可检测出 MNIST 数据质量问题，而常规训练 baseline 事后难以或无法察觉。**
结构化结果：`reports/audit_effectiveness/result.json`。

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
