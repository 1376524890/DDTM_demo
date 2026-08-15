# 默认值 / 模拟实现 / 假设 全面审查报告

> 范围：`valor/engine/`（P0–P13 收敛层）、`valor/audit/`、`valor/liability/`、
> `valor/pricing/`、`valor/distributed/`。目标：识别所有「隐式默认值、模拟/占位、
> 未验证假设」，并明确哪些符合规范（冻结场景输入）、哪些需要显式确认、哪些仍为近似。
> 审查日期：基于 VALOR-v1 当前 HEAD。

## 结论摘要

- 业务默认值静态扫描：**OK（无业务默认值）**（`python scripts/check_business_defaults.py --root valor`）。
- FullChainGate 的恒 `True` 占位检查：**已全部改为真实验证**（commit `d615f99`）。
- 审计证据源：**已由"默认全 PASS 模拟"改为真实质量检测**（commit `875eb7e`）。
- 仍存在三类需要使用者知晓的**机制参数默认值**与**简化假设**，列于下。

---

## A. 符合规范的「冻结场景输入」（非默认值，是显式场景定义）

这些是 `CapstoneScenario` / `CalibrationConfig` 的字段默认值，作为**一次性冻结的交易场景**
输入（对齐"冻结实验环境"），不是代码内部隐式默认。使用者通过 JSON/构造函数显式给出。

| 参数 | 默认值 | 说明 |
|---|---|---|
| `scenario.audit_prior` | `pi_b=0.25, q_l=0.2` | 先验信念（买方对卖方 breach/latent 的初始判断） |
| `scenario.likelihood` | PASS/QUALITY_FAIL/BREACH_EVIDENCE 三行 | 审计动作似然（**仅当未提供 P6 冻结 artifact 时回退**） |
| `scenario.certificate` | `a_D=1,b_D=1,alpha_D=0.05,tp=12,fn=2` | 检测认证 Beta 先验（**仅当未提供 P6 冻结证书时回退**） |
| `scenario.bond` | `g_dev=60,eps_s=1,p_e_bond=1,p_e_f=0.3,lambda_s=0.5,f_s=10,kappa_s=0.1` | 卖方责任/激励参数 |
| `scenario.buyer` / `seller` | `w_b_rem=500,c_i=20,...` | 买方/卖方成本结构 |
| `scenario.pricing.beta_bar` | `0.5` | 结算价谈判系数（§41） |
| `scenario.payoff_matrix` | 10×10（对角+1，误识别−3） | 买方任务 payoff（单位 CU） |
| `scenario.role_fracs` | hist 25% / base 20% / cand 5% / eval 10% | 五角色数据划分比例 |
| `CalibrationConfig.a_D/b_D/alpha_D` | `1.0/1.0/0.05` | 认证 Beta 先验 |

> 注：`CapstoneScenario` 的 `likelihood`/`certificate` 默认值在**提供 P6 冻结 artifact 时会被忽略**
> （`DistributedAuditExecutor` 优先用 `likelihood_artifact`/`certificate_artifact`）。因此
> 完整 capstone 交易中这些不是"手工似然/TP-FN"。

---

## B. 机制参数默认值（目前有默认，建议使用者显式确认）

这些是**机制运行参数**，代码提供了默认值。规范要求参数有显式来源；当前默认值便于运行，
但正式实验应显式给出。

| 位置 | 参数 | 默认值 | 风险 |
|---|---|---|---|
| `audit_executor.py:64` | `scenario.audit["cost"]` | `2.0` | 审计动作现金成本（MC_A^pay 基准） |
| `audit_executor.py:86-89` | `min_stake/timeout_s/rho/eta_b/eta_o/seed` | `0/10/0/0/0/0` | 审计市场/BFT 安全参数 |
| `audit_executor.py:117-118` | `alpha_shift / label_error_threshold` | `0.01 / 0.28` | 真实证据源检测阈值 |
| `real_evidence.py:54-57` | `alpha_shift=0.01, label_error_threshold=0.28, row_sample=2000, compress_dim=64` | 同上 | 检测灵敏度/性能假设 |
| `scenario.audit` | `n_nodes=10, f=2` | — | 委员会规模（VCG 反事实需 n>m） |

> 建议：正式 MNIST 实验在场景 JSON 中显式给出全部 audit 市场参数与检测阈值，
> 而非依赖默认值。

---

## C. 仍存的简化 / 近似（需使用者知悉）

这些是当前实现为跑通端到端而做的**简化或近似**，非论文机制的最终形态：

| 类别 | 位置 | 简化/近似 | 影响 |
|---|---|---|---|
| **审计执行方式** | `audit_executor.py` / `scheduler.py` | 默认用**进程内 evidence provider**（真实质量检测但单进程），未默认拉起真 HTTP 多节点进程 | 分布式 BFT 的「真多节点」由 P4 集成测试 `test_distributed_http.py` 单独验证；capstone 默认走进程内 |
| **证据一致性** | `real_evidence.py:make_real_evidence_provider` | 所有节点返回**同一真实检测结果**（诚实节点对同 committed data 运行确定性 primitive 应一致） | 合理近似；未模拟节点间恶意分歧 |
| **似然/证书回退** | `audit_executor.py` | 未提供 P6 artifact 时回退 `scenario.likelihood`/`certificate` | 完整流程应提供冻结 artifact；回退仅用于便捷/测试 |
| **FullChainGate G24 escrows** | `full_chain_gate.py` | 验证 money_events 存在，未逐账户校验 escrow 余额归零 | 结算语义已由 MoneyLedger 白名单 + conservation 校验 |
| **估值校准 pseudo-historical** | `calibration_runner.py` | 用简化代理量（`predicted=len(sub)` 等）构造伪历史 residual | 正式实验应从真实历史交易构造 residual |
| **label 检测** | `real_evidence.py:_label_check` | 用 LogisticRegression OOF + CL，64 维像素压缩 | 性能近似；检测阈值（0.28）为经验值 |
| **实验统计** | `experiments.py` | n_seeds 由用户设定；默认无自动多组 | 符合统计规范，需使用者配置 seed 数 |

---

## D. 已消除的模拟/占位（历史记录）

| 版本 | 消除项 |
|---|---|
| `875eb7e` | 审计证据源：默认全 PASS 模拟 → 真实质量检测（KS + CL） |
| `d615f99` | FullChainGate 恒 True 占位 → 真实验证 |
| `d615f99` | `CalibrationConfig` 占位 hash（`"p"*64` 等）→ 必填/上游生成 |

---

## 复现命令

```bash
# 业务默认值静态扫描
python scripts/check_business_defaults.py --root valor

# 审计效果对比（零知识审计 vs baseline）
python scripts/audit_effectiveness.py --samples 4000 --epochs 1 --label-flip 0.2

# 完整 capstone（真实审计 + 冻结 calibration）
python -m valor engine calibrate --dataset breast_cancer --out-dir calibration
python -m valor engine capstone --scenario <scenario.json> --run-dir runs \
    --calibration-dir calibration/<run_id>/calibration_bundle.json
```
