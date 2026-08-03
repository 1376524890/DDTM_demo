# DDTM-QAS 核心研究方案与 G2 实施指南

**版本：** v1.0  
**性质：** 核心研究章程、系统对齐规范与 G2 验收依据  
**适用范围：** GitHub `main` 分支；G0/G1 保持冻结，不重复重写

---

## 0. 文档使用规则

DDTM-QAS 后续新增模块、实验和论文主张，必须明确服务于以下至少一项：

1. 提高买方条件化效用相对于完整重新训练 Oracle 的估计准确性；
2. 提高效用证书的保守性、可校准性或密码学可信度；
3. 提高卖方数据、买方任务、评估结果与链上交易之间的绑定完整性；
4. 在抑制低质量数据伪造的同时，降低审计、证明、保证金和残余风险总成本。

不能直接服务于以上目标的功能，不应进入核心协议，也不应作为论文主要贡献。

正式实验前必须固定实际代码状态：

```bash
git checkout main
git pull --ff-only
git status --porcelain
git rev-parse HEAD
git submodule status
```

工作区必须 CLEAN。每份结果必须记录 Git commit、配置哈希、数据哈希、模型哈希、随机种子、依赖版本和运行环境。

---

# 1. 冻结后的核心研究主线

DDTM-QAS 的核心研究问题为：

> 面向特定买方任务，在卖方数据、买方模型和买方验证集均不提前公开的条件下，对尚未交付的数据产品进行边际任务效用评估；生成与卖方数据身份、买方任务状态和链上交易绑定的可验证保守效用证书；并结合可验证质量审计、低质量伪造收益、验证成本、保证金资本成本和剩余风险形成动态成交价格。

研究主链：

```text
买方任务预承诺
    ↓
卖方规范化数据承诺
    ↓
买方条件化完整重新训练价值定义
    ↓
ARUC 低成本效用估计
    ↓
相对于完整重新训练 Oracle 的保守证书校准
    ↓
TEE attestation 与 ZK 阈值证明
    ↓
交易上下文逐项绑定并上链
    ↓
可验证质量审计
    ↓
审计强度—保证金联合优化
    ↓
风险调整后的可成交价格区间
    ↓
加密交付、完整根复核与结算
```

必须严格区分：

\[
\text{买方任务效用}\neq\text{数据契约质量}\neq\text{货币价格}
\]

- **任务效用**：该数据对当前买方任务能带来多少边际训练收益；
- **契约质量**：数据是否满足挂牌声明、格式、标签、缺失和交付一致性要求；
- **货币价格**：在效用、风险和成本约束下，买卖双方是否存在可接受成交区间。

---

# 2. 买方条件化效用的形式化定义

## 2.1 买方任务上下文

定义买方 \(b\) 在任务版本 \(t\) 的上下文：

\[
\mathcal T_{b,t}=
(B_{b,t},\theta_{b,t},V_{b,t},\mathcal A_b,\ell_b,m_b,\rho_b,\Xi_b,e_{b,t})
\]

| 符号 | 含义 |
|---|---|
| \(B_{b,t}\) | 买方当前基础训练数据 |
| \(\theta_{b,t}\) | 当前模型检查点 |
| \(V_{b,t}\) | 私有验证集或目标分布样本 |
| \(\mathcal A_b\) | 冻结训练算法及超参数 |
| \(\ell_b\) | 训练损失函数 |
| \(m_b\) | 最终任务评价指标 |
| \(\rho_b\) | 候选数据混合、采样和权重规则 |
| \(\Xi_b\) | 训练随机种子分布 |
| \(e_{b,t}\) | 任务 epoch 或状态版本 |

初始参考任务冻结为：表格二分类、最多 100000 行、128 个 Q16.16 特征、标签 \(-1,+1\)、128→64→1 ReLU MLP、hinge loss。模型架构和政策公开，买方模型参数和验证集私有。

任务上下文必须在卖方数据根对评估器可见之前承诺，防止买方看到候选数据后修改验证目标压低估值。

## 2.2 完整重新训练 Oracle

对卖方数据产品 \(D\)，基础训练结果为：

\[
\theta^{0,\xi}_{b,t}=\mathcal A_b(B_{b,t};\xi)
\]

加入候选数据后：

\[
\theta^{D,\xi}_{b,t}=\mathcal A_b(B_{b,t}\oplus_{\rho_b}D;\xi)
\]

若评价指标越大越好：

\[
U^*_{b,t}(D)=
\mathbb E_{\xi\sim\Xi_b}
[m_b(\theta^{D,\xi}_{b,t},V_{b,t})-m_b(\theta^{0,\xi}_{b,t},V_{b,t})]
\]

若使用验证损失：

\[
U^*_{b,t}(D)=
\mathbb E_{\xi\sim\Xi_b}
[L_V(\theta^{0,\xi}_{b,t})-L_V(\theta^{D,\xi}_{b,t})]
\]

统一约定：\(U^*>0\) 有益，\(U^*=0\) 无可识别增益，\(U^*<0\) 有害。所有估值方法最终必须与该 Oracle 对齐。

## 2.3 两类 Oracle

**Primary Oracle：配对冷启动完整重新训练。** 基础模型和增强模型对每个 seed 从相同初始化开始，分别在 \(B\) 与 \(B\oplus D\) 上完整训练。它是论文主要 Oracle。

**Secondary Oracle：固定预算热启动增量训练。** 从已承诺的 \(\theta_{b,t}\) 开始，在冻结预算下继续训练。它用于部署外部有效性，不替代 Primary Oracle。

## 2.4 同一数据对不同买方价值不同

通常：

\[
U^*_{b_1,t_1}(D)\neq U^*_{b_2,t_2}(D)
\]

原因包括基础数据覆盖、模型成熟度、验证分布、类别成本、历史购买和冗余程度不同。同一买方模型更新后也可能满足：

\[
U^*_{b,t}(D)\neq U^*_{b,t+1}(D)
\]

因此效用凭证必须绑定买方身份、任务 epoch、基础数据承诺、模型承诺、验证集承诺、训练政策、估值政策、卖方数据根、交易 ID、有效期和 nonce，不能跨买方或跨任务版本复用。

---

# 3. ARUC 的计算定义

## 3.1 当前实现：ARUC-v0

当前 Rust 代码已完成：全量卖方梯度、验证梯度、一次全局虚拟更新、逐验证行 loss delta、按验证行分组的 MoM、MAD、一阶方向效用、LinearError、Shift、UCert 与阈值判断。

应将当前方法正式命名为：

```text
ARUC-v0-global-update-validation-MoM
```

它必须保留为 G2 的现有基线。当前 MoM 主要缓和验证样本的重尾或局部异常，并未直接对候选卖方数据的局部污染分组。

## 3.2 ARUC-v1：候选数据分组 MoM

使用交易绑定种子把候选数据确定性分成 \(K_D\) 组：

\[
D=D_1\cup\cdots\cup D_{K_D}
\]

分组索引由 `dataRoot`、任务承诺、policy、seed 和 rowId 共同决定，卖方不得选择分组。

对每组计算平均梯度并裁剪：

\[
g_j=\frac{1}{|D_j|}\sum_{z\in D_j}\nabla_\theta\ell(\theta;z),\qquad
\widetilde g_j=\operatorname{Clip}(g_j,C)
\]

执行非持久化更新：

\[
\theta'_j=\theta-\eta\widetilde g_j
\]

计算：

\[
\Delta_j=L_V(\theta)-L_V(\theta'_j)
\]

定义：

\[
\widehat U^{\mathrm{cand-MoM}}=\operatorname{median}_j\Delta_j
\]

\[
\operatorname{MAD}_D=\operatorname{median}_j|\Delta_j-\widehat U^{\mathrm{cand-MoM}}|
\]

该版本直接降低少数候选污染组对估值的影响。

## 3.3 ARUC-v2：双轴鲁棒估计

将验证集独立分为 \(K_V\) 组，计算：

\[
\Delta_{j,r}=L_{V_r}(\theta)-L_{V_r}(\theta'_j)
\]

先对验证组取中位数：

\[
u_j=\operatorname{median}_r\Delta_{j,r}
\]

再对候选组取中位数：

\[
\widehat U^{\mathrm{bi-MoM}}=\operatorname{median}_j u_j
\]

ARUC-v2 同时处理候选数据污染和验证集重尾，但计算更贵。只有在 pilot 中显著提高 Oracle 保真度或证书覆盖时才进入 final。

## 3.4 基线量

一阶方向效用：

\[
U^{\mathrm{FI}}=\eta\langle g_V,\widetilde g_D\rangle
\]

整体一步更新效用：

\[
\Delta^{\mathrm{1step}}=L_V(\theta)-L_V(\theta-\eta\widetilde g_D)
\]

推荐比较两种 LinearError：

\[
E_{\mathrm{lin,global}}=|\Delta^{\mathrm{1step}}-U^{\mathrm{FI}}|
\]

\[
E_{\mathrm{lin,robust}}=|\widehat U^{\mathrm{robust}}-U^{\mathrm{FI}}|
\]

最终选择必须由 Oracle 预测能力与覆盖率决定。

## 3.5 Shift 候选定义

当前实现保留为 `Shift-v0`：

\[
S_0=\frac1d\sum_k|\mu_{D,k}-\mu_{V,k}|
\]

G2 至少增加标准化版本：

\[
S_1=\frac1d\sum_k\frac{(\mu_{D,k}-\mu_{V,k})^2}{\sigma^2_{V,k}+\varepsilon}
\]

以及均值—方差联合版本作为消融。最终协议优先选择固定点易实现、范围可约束且真正提高 Oracle 预测或证书覆盖的最低复杂度指标。

## 3.6 保守证书

最终形式：

\[
U^{\mathrm{cert}}=
\widehat U^{\mathrm{robust}}
-\lambda_{\mathrm{MAD}}\operatorname{MAD}
-\lambda_{\mathrm{shift}}S
-\lambda_{\mathrm{lin}}E_{\mathrm{lin}}
-q_\delta
\]

\(\lambda\) 不允许手工随意设置，\(q_\delta\) 必须来自独立校准集。目标性质：

\[
\Pr[U^*_{b,t}(D)\ge U^{\mathrm{cert}}_{b,t}(D)]\ge1-\delta
\]

这是 G2 的核心验收对象。

---

# 4. G2 总体目标与当前缺口

G2 要建立：

```text
真实训练模型 → 多买方上下文 → 多候选产品 → 完整重训练 Oracle
→ ARUC 与 baseline → Python/Rust 固定点一致性 → 证书校准
→ 独立测试验证 → 可复现报告与 Gate
```

当前可直接复用：G1 canonical data、Q16.16、548-byte 行、Poseidon2 root、Rust MLP/hinge/gradient/one-step、ARUC-v0、UtilityThresholdCircuit。

当前必须补齐：

1. `BuyerTaskContext` 规范；
2. 完整重新训练 Oracle；
3. 正式训练 pipeline；
4. 多买方任务矩阵；
5. 候选产品与污染规范；
6. Python float、Python fixed、Rust fixed 一致性；
7. ARUC-v1/v2；
8. FI、One-Step、Shapley/Banzhaf 等 baseline；
9. train/calibration/test 隔离；
10. 基于 Oracle 的 penalty 与 conformal 校准；
11. 证书覆盖率；
12. 真实公开数据结果；
13. 20K/50K/100K 性能报告。

---

# 5. 推荐仓库结构

```text
specs/
  buyer-task-context-v1.md
  full-retraining-oracle-v1.md
  candidate-product-v1.md
  aruc-estimator-v1.md
  aruc-certificate-v1.md
  g2-result-schema-v1.md

ml/g2/
  canonical_reader.py
  task_context.py
  preprocessing.py
  model.py
  train.py
  oracle.py
  estimators/
  products/
  calibration/
  fixed_reference/
  metrics.py
  manifests.py

experiments/g2/
  configs/
  tasks/
  products/
  raw/
  reports/
  calibration/
  manifests/

scripts/
  run-g2-smoke.sh
  run-g2-pilot.sh
  run-g2-final.sh
  run-g2-scale.sh
  generate-g2-report.sh
```

G2 只新增目录和版本化实现，不破坏 G0/G1 的脚本、向量与报告。

---

# 6. G2 分阶段实施方法

## G2.0：快照与规范冻结

### 实现

1. 固定 `main` 的实际 HEAD 和 CLEAN 状态；
2. 冻结模型架构、训练政策、Oracle 定义和主要效用单位；
3. 冻结预处理、缺失值处理和候选数据混合规则；
4. 对所有规范、配置生成 SHA-256；
5. 明确 pilot 结束后哪些参数不得再修改。

建议训练政策至少包含：

```yaml
architecture: 128-64-1-relu
loss: hinge
optimizer: fixed and versioned
epochs: fixed
batch_size: fixed
early_stopping: disabled for primary oracle
normalization: fitted from buyer base training data only
missing_value: normalized zero plus committed missing mask
candidate_mix_weight: fixed
class_weight: fixed or committed in task context
seed_policy: paired seeds
```

主 Oracle 不建议使用普通验证集早停，避免验证集同时用于训练选择和价值评价。可采用固定 epoch，或使用买方基础数据内部的独立控制集。

### 验收

- 所有规范有版本、哈希和兼容性说明；
- 三次运行产生相同任务哈希和配置哈希；
- 不存在读取卖方数据后修改买方任务配置的路径；
- `run-manifest.json` 明确写入实际 Git commit。

## G2.1：建立统一 Python 训练参考

### 实现

使用 Python/PyTorch 建立浮点训练参考：

1. 读取 G1 canonical binary；
2. 把 Q16.16 特征解码为 float32；
3. 按 missing mask 执行冻结填充；
4. 训练 128→64→1 ReLU MLP；
5. 使用 hinge loss；
6. 输出模型权重、训练曲线、验证 loss 和辅助指标；
7. 导出 Rust `Model` 所需 Q16.16 JSON；
8. 计算模型文件哈希和模型承诺。

Oracle 和 ARUC 必须读取同一份 canonical data。禁止 Oracle 使用原始 CSV、Rust 使用量化 binary 的双轨方式。

标准化参数只能从买方基础训练集拟合。候选数据和验证集只能应用已承诺的参数，不能重新拟合。

### 验收

- 相同 seed、相同容器、相同 CPU 路径三次结果一致；
- 模型形状与 Rust 完全一致；
- Rust 能读取导出模型；
- Python fixed 与 Rust 的 score、loss、gradient 和 one-step 可比；
- 所有非确定性来源有明确配置。

## G2.2：建立至少 5 个买方任务

初始先保持模型架构和损失一致，通过基础数据和目标分布体现异质性：

| 买方 | 基础状态 | 验证目标 |
|---|---|---|
| B1 通用买方 | IID 基础集 | 总体 IID |
| B2 少数类买方 | 少数类不足 | 少数类密集或加权目标 |
| B3 亚群 A 买方 | 主要覆盖 B | 亚群 A |
| B4 亚群 B 买方 | 主要覆盖 A | 亚群 B |
| B5 低数据买方 | 小基础集 | 与 B1 相同目标 |

可选扩展包括时间窗口、地域、设备、历史购买和模型成熟度差异。

每个任务建议保存：

```json
{
  "task_version": 1,
  "buyer_id": "B1",
  "task_epoch": 0,
  "base_data_root": "...",
  "model_commitment": "...",
  "validation_root": "...",
  "preprocessing_hash": "...",
  "training_policy_hash": "...",
  "valuation_policy_hash": "...",
  "seed_set_hash": "...",
  "created_before_seller_root": true
}
```

### 验收

- 至少 5 个预先定义的买方任务；
- 每个任务有独立基础数据、模型和验证承诺；
- 差异不是为追求理想结果事后挑选；
- 相同候选产品可在所有买方上运行。

## G2.3：建立候选卖方数据产品目录

### 合成工业数据

至少覆盖：

- 干净且相关；
- 干净但冗余；
- 新亚群覆盖；
- 标签翻转；
- 特征噪声；
- 离群点；
- 随机缺失；
- 结构化缺失；
- 类别失衡；
- 协变量偏移；
- 标签条件偏移；
- 重复样本；
- 局部集中污染；
- 决策边界定向污染。

### 真实公开数据

至少使用一个公开真实表格二分类数据集。推荐 HIGGS 用于 100K 规模，Adult 用于可解释亚群实验。少于 128 维的特征补零，并在 schema 中记录。

### 产品元数据

```json
{
  "product_id": "P001",
  "source_dataset": "synthetic-industrial-v1",
  "clean_parent_hash": "...",
  "canonical_root": "...",
  "row_count": 20000,
  "product_type": "label_flip",
  "severity": 0.1,
  "pollution_seed": 7,
  "generator_version": 1
}
```

### 验收

- 每个产品可由 manifest 重建；
- 重建后 dataRoot 完全一致；
- 至少 10 类产品；
- 至少 20K、50K、100K 三个规模；
- 污染在 canonicalization 前生成，最终结果由数据根绑定。

## G2.4：实现配对完整重新训练 Oracle

对每个 `buyer task × candidate product × model seed`：

1. 用 seed \(\xi\) 在基础数据训练 \(\theta^{0,\xi}\)；
2. 用同一 seed 在基础数据加候选产品训练 \(\theta^{D,\xi}\)；
3. 在同一验证集计算：
   \[
   U^\xi=L_V(\theta^{0,\xi})-L_V(\theta^{D,\xi})
   \]
4. 对 seed 求均值并保留每个 seed 结果；
5. 输出 paired bootstrap 或配对置信区间。

基础模型应缓存：

```text
buyer × model seed → base model and base metrics
```

候选混合规则必须冻结：是否拼接、是否重采样、总训练 step 是否固定、候选数据暴露比例。主 Oracle 建议固定总训练步数和混合权重，另做自然拼接外部有效性实验。

### 验收

- 同配置三次一致；
- 每个候选产品保留 seed-level 结果；
- 数据中确实存在正、近零和负效用；
- Oracle 不读取 ARUC 输出；
- Oracle 与估值器代码路径隔离。

## G2.5：实现估值 baseline

最低 baseline：

1. Mean One-Step；
2. One-Step；
3. Forward Influence；
4. ARUC-v0；
5. ARUC-v1；
6. ARUC-v2（pilot 后允许因成本退出）；
7. 可扩展 Data Shapley；
8. 可扩展 Data Banzhaf；
9. 可选 Data-OOB。

统一主要效用单位为：

```text
validation hinge-loss reduction
```

公平比较要求：同基础模型、同候选数据、同验证集、同预处理、同 seed。所有超参数仅用训练/校准部分选择，final test 不参与调参。

### 验收

- 所有方法使用统一结果 schema；
- 失败保留错误码，不静默删除；
- baseline 不能把 Oracle 值作为输入；
- 统一测量运行时间和峰值内存。

## G2.6：Python—Rust 固定点一致性

建立三层：

1. Python float32；
2. Python Q16.16 模拟；
3. Rust Q16.16。

逐项比较：forward score、hinge loss、per-row gradient、average gradient、updated parameters、validation delta、MoM、MAD、Shift、FI、LinearError、UCert。

### Bit-exact Gate

Python fixed 与 Rust 冻结向量逐整数一致。

### Quantization Fidelity Gate

Python float 与固定点报告效用 MAE、排序相关、符号不一致率和阈值结论不一致率。

### 验收

- Python fixed 与 Rust：0 mismatch；
- float/fixed 候选排序 Spearman ≥ 0.98；
- 效用符号不一致率 ≤ 2%；
- 阈值结论不一致率 ≤ 2%；
- 所有溢出、饱和、裁剪有计数。

未达标时应调整量化、范围或训练约束，不得通过放宽结果容差掩盖问题。

## G2.7：证书参数学习与单侧校准

候选产品和买方组合必须分为：

- estimator-training set；
- certificate-calibration set；
- final test set。

优先按数据来源或 clean parent 分组划分，避免同一数据的轻微污染版本跨 calibration/test 泄漏。

定义高估残差：

\[
r_i=\widehat U_i^{\mathrm{robust}}-U_i^*
\]

特征：

\[
z_i=(\operatorname{MAD}_i,S_i,E_{\mathrm{lin},i})
\]

使用非负分位数回归拟合：

\[
\widehat r_i=\lambda^Tz_i+c,
\qquad \lambda\ge0
\]

在独立 calibration set 进行单侧 conformal 校准，得到 \(q_\delta\)，最终：

\[
U^{\mathrm{cert}}=U^{\mathrm{rawcert}}-q_\delta
\]

同时报告 90% 和 95% 目标覆盖率。

### 防止空洞证书

高覆盖但始终输出极小值没有研究意义。必须报告：平均/中位证书宽度、正证书 precision/recall、有害数据误接受、coverage-width trade-off。

### 验收

- final test 未参与参数和 \(q_\delta\) 选择；
- 95% 目标证书整体实测覆盖率 ≥ 93%；
- 主要污染族单独报告覆盖；
- 最坏主要污染族建议 ≥ 90%；
- `U_cert > 0` 时有害数据误接受率 ≤ 10%；
- 证书不能全部非正或全部落入最低档位。

## G2.8：多买方异质性实验

计算效用矩阵：

\[
\mathbf U^*=[U^*_{b,t}(D_s)]_{b,s}
\]

必须报告：

1. 同一产品跨买方的效用方差和极差；
2. 买方之间的产品排名相关；
3. 排名反转率；
4. 不同买方最优产品的重合率；
5. 同一产品在不同买方上的效用符号反转率；
6. 同一买方随历史数据增加的边际价值衰减；
7. 买方任务距离与效用差异的相关性；
8. buyer × product 的交互效应。

### 异质性验收

硬要求：

- 至少 5 个预注册买方任务；
- 至少 30 个相同候选产品被全部买方评估；
- buyer × product 交互效应有统计分析；
- 所有结论给出 seed-level 置信区间。

建议研究目标：

- 至少 20% 产品出现稳定排名反转；
- 至少 10% 产品出现跨买方效用符号差异。

这两个比例是研究目标而非可人为制造的工程 Gate。若真实结果较低，必须诚实报告并收缩“买方条件化价值差异”的贡献强度。

## G2.9：规模与性能

数据规模：20K、50K、100K。验证集至少比较 1K、5K、10K。MoM 组数至少比较 5、11、21、31。

报告：

- 总运行时间；
- 数据读取、seller gradient、validation gradient 时间；
- 每个虚拟更新验证时间；
- 峰值 RSS；
- CPU 利用率；
- 固定点溢出计数；
- 组数的精度—成本关系；
- 行数与运行时间线性拟合 \(R^2\)。

暂定原型性能 Gate（在明确记录的参考硬件上）：

- 100K seller rows、10K validation rows、ARUC-v1 11 组；
- 峰值内存 ≤ 8 GiB；
- 总时间 ≤ 15 分钟；
- 无未处理整数溢出；
- 20K→50K→100K 近似线性，\(R^2\ge0.98\)。

如硬件不同，必须同时报告每核心吞吐量和硬件配置。

---

# 7. 实验阶段与矩阵

## 7.1 Smoke

```text
1 个合成任务
1 个买方
6 个候选产品
1 个模型 seed
2 个污染 seed
2K–5K 行
ARUC-v0/v1 + One-Step + FI
```

验收：全流程一键完成；schema 完整；Python fixed 与 Rust bit-exact；Oracle 与 ARUC 均有正负结果；三次运行确定。

## 7.2 Pilot

```text
3 个买方任务
20–30 个候选产品
3 个模型 seed
3–5 个污染 seed
20K 行
ARUC-v0/v1/v2
全部主要 baseline
初步证书校准
```

Pilot 用于：选择最终 ARUC、Shift、LinearError、组数和学习率，估计资源，删除无效惩罚项。Pilot 后冻结 final config，不得用 final test 调参。

## 7.3 Final

最低要求：

```text
至少 5 个买方任务
合成工业数据 + 至少 1 个真实数据集
每个主要配置至少 5 个模型 seed
每个污染配置至少 10 个污染 seed
至少 10 类候选产品
20K、50K、100K
独立 training / calibration / final-test
```

所有表格和图必须从原始结果自动生成。

---

# 8. 主要评价指标

## 8.1 效用保真度

- Spearman；
- Kendall Tau；
- MAE、RMSE；
- 效用符号准确率；
- Top-k 产品选择准确率；
- 最优产品 regret；
- 有害数据 AUROC、AUPRC；
- 有害数据误接受率。

## 8.2 证书质量

- 单侧覆盖率与违反率；
- 平均/中位证书宽度；
- 正效用证书 precision/recall；
- harmful false acceptance；
- 分买方、污染族、规模覆盖率。

## 8.3 多买方差异

- 跨买方效用方差；
- 排名和符号反转率；
- 买方间排名相关矩阵；
- buyer × product 交互；
- 边际价值随历史数据量衰减。

## 8.4 计算成本

- 评估与 Oracle 训练时间；
- 相对 Oracle 加速比；
- 峰值内存；
- 每行吞吐；
- 溢出、饱和与失败率。

---

# 9. G2 正式验收标准

## 9.1 硬工程 Gate

以下任一失败，G2 不得标记 PASS：

| 编号 | 标准 |
|---|---|
| E1 | 仅使用 `main`，记录精确 commit，工作区 CLEAN |
| E2 | 数据、模型、任务、产品、配置、结果均有哈希 |
| E3 | Oracle 与 ARUC 使用同一 canonical data |
| E4 | Python fixed 与 Rust 冻结向量 0 mismatch |
| E5 | 三次运行可复现 |
| E6 | 至少 5 个买方任务 |
| E7 | 合成数据和至少一个真实公开数据集 |
| E8 | 至少 10 类候选产品 |
| E9 | training/calibration/test 严格隔离 |
| E10 | 所有 baseline 使用统一效用单位 |
| E11 | 全部 seed-level 原始结果归档 |
| E12 | 95% 证书整体测试覆盖率 ≥ 93% |
| E13 | 有害数据误接受率 ≤ 10% |
| E14 | 20K、50K、100K 均可完成且不 OOM |
| E15 | 报告从原始 JSON/Parquet 自动生成 |
| E16 | 研究目标未被表述为既有结果 |

## 9.2 ARUC 研究目标 Gate

| 指标 | 建议目标 |
|---|---:|
| 测试集平均 Spearman | ≥ 0.75 |
| Spearman 95% bootstrap 下界 | ≥ 0.65 |
| Kendall Tau | ≥ 0.55 |
| 有害数据 AUROC | ≥ 0.85 |
| 效用符号准确率 | ≥ 0.80 |
| 有害数据误接受率 | ≤ 0.10 |
| float/fixed 排名 Spearman | ≥ 0.98 |
| float/fixed 符号不一致率 | ≤ 0.02 |

相对 FI 与普通 One-Step，ARUC 至少应满足：排名相关不低于最佳 baseline，并在有害误接受率或相同误接受率下的正效用召回方面显著更优。

不能只选择一个对 ARUC 有利的指标。主要指标必须在 final 前预注册。

## 9.3 证书非空洞性 Gate

除覆盖率外必须同时满足：

- 真实有益产品中存在正 `U_cert`；
- 正 `U_cert` precision ≥ 90%；
- 正 `U_cert` recall 建议 ≥ 60%；
- 证书宽度显著优于常数零下界和全局最小值下界；
- 各主要买方均产生可用证书。

若覆盖达标但证书全部非正，只能标记：

```text
COVERAGE_PASS / UTILITY_FAIL
```

不得整体 PASS。

## 9.4 统计要求

- 相关系数报告 bootstrap CI；
- AUROC/AUPRC 报告分层 bootstrap CI；
- 方法比较使用 paired bootstrap 或配对非参数检验；
- 多重比较做 Holm 或 Benjamini–Hochberg 修正；
- 除 p 值外报告效应量；
- 买方、产品族和 seed 作为分层因素。

---

# 10. 推荐结果 Schema

## 10.1 Oracle

```json
{
  "version": 1,
  "git_commit": "...",
  "buyer_task_hash": "...",
  "product_root": "...",
  "model_seed": 3,
  "pollution_seed": 7,
  "oracle_type": "paired-cold-retrain",
  "base_validation_loss": 0.421,
  "augmented_validation_loss": 0.387,
  "utility": 0.034,
  "train_seconds_base": 12.4,
  "train_seconds_augmented": 18.1,
  "model_base_hash": "...",
  "model_augmented_hash": "..."
}
```

## 10.2 Estimator

```json
{
  "version": 1,
  "method": "aruc-v1",
  "buyer_task_hash": "...",
  "product_root": "...",
  "u_mom": 0.029,
  "mad": 0.004,
  "shift": 0.12,
  "u_first_order": 0.026,
  "one_step_utility": 0.030,
  "linear_error": 0.004,
  "u_raw_cert": 0.021,
  "u_cert_90": 0.017,
  "u_cert_95": 0.013,
  "pass": true,
  "runtime_seconds": 4.2,
  "peak_rss_bytes": 421000000,
  "overflow_count": 0
}
```

## 10.3 Gate

```json
{
  "gate": "G2",
  "status": "PASS",
  "git_commit": "...",
  "config_sha256": "...",
  "raw_manifest_sha256": "...",
  "engineering_gates": {},
  "research_metrics": {},
  "failed_checks": [],
  "warnings": []
}
```

---

# 11. 执行脚本要求

## Smoke

```bash
bash scripts/run-g2-smoke.sh
```

流程：生成数据 → canonicalize → 创建任务 → 训练基础模型 → Oracle → Python baseline → 导出 fixed 模型 → Rust ARUC → parity → 报告。

## Pilot

```bash
bash scripts/run-g2-pilot.sh
```

完成多买方、多产品、多方法、消融、初步校准和 final config 冻结。

## Final

```bash
bash scripts/run-g2-final.sh --config experiments/g2/configs/final.json
```

必须拒绝：dirty worktree、未冻结 config、pilot 后配置哈希变化、calibration/test 重叠、缺失 seed 或 manifest。

## Report

```bash
bash scripts/generate-g2-report.sh
```

至少生成：

```text
experiments/g2/reports/g2-final.md
experiments/g2/reports/g2-gate.json
experiments/g2/reports/tables/*.csv
experiments/g2/reports/figures/*.pdf
experiments/g2/manifests/final-manifest.json
```

---

# 12. 必做消融

1. 去除 MoM；
2. 验证样本 MoM 与候选数据 MoM 对比；
3. 去除 MAD；
4. 去除 Shift；
5. 去除 LinearError；
6. 不同 Shift 定义；
7. 不同 LinearError 定义；
8. 不同 MoM 组数；
9. 不同虚拟更新学习率；
10. 不同梯度裁剪；
11. 不使用 conformal 校准；
12. 手工 lambda 与学习 lambda；
13. float 与 fixed；
14. 冷启动与热启动 Oracle；
15. 固定训练步数与自然拼接训练。

每项同时报告 Spearman、harmful AUROC、harmful false acceptance、coverage、certificate width 和 runtime。

---

# 13. 失败风险与处理

## 13.1 ARUC 与 Oracle 相关性不足

按顺序检查：

1. Oracle 与 ARUC 是否使用同一 canonical data 和预处理；
2. 固定点量化是否改变模型；
3. 学习率与裁剪是否进入线性有效区间；
4. 候选数据分组是否改善局部污染；
5. Shift 是否应改为梯度空间或标准化版本；
6. 是否需要限制证书适用域；
7. 是否应输出效用区间或档位。

不得删除困难产品来提高指标。

## 13.2 覆盖率高但证书过于保守

可增加校准样本、按任务族校准、增加有解释力的误差特征或输出档位。必须报告 coverage-width trade-off。

## 13.3 不同买方差异不明显

检查任务是否真正代表不同基础状态，增加亚群、历史数据和模型成熟度差异；若仍不明显，应诚实报告并缩小主张，而不是事后重构买方任务追求显著性。

## 13.4 Shapley/Banzhaf 成本过高

使用 Truncated Monte Carlo、group-level valuation、小规模精确加大规模近似。必须报告近似预算，不能把低预算近似的失败当作方法本身失败。

## 13.5 float/fixed 差异过大

可限制权重范围、加入量化约束、提高累加器位宽、调整 Q 格式并记录饱和。必要时以量化模型 Oracle 作为协议内主结果，同时报告 float 外部有效性。

---

# 14. G2 完成后的系统对接

## G3：交易绑定

把 G2 冻结的指标和证书写入 TEE report、metrics commitment、UtilityThresholdCircuit、Solidity public inputs、proof replay protection、PolicyRegistry、task epoch 与 expiry。

G3 不允许静默修改 G2 效用定义。修改必须升级估值政策版本并重新校准。

公开输入至少绑定：

```text
chain_id
contract_address
listing_id
seller
buyer
data_root
buyer_task_hash
model_commitment
validation_root
metrics_commitment
valuation_policy_hash
session_hash
utility_bucket
price_policy_hash
expiry
nonce
```

合约必须逐项与 listing、policy 和 session 状态比较，而不是只调用 verifier。

## G4：动态定价和 JABO

G2 输出 `U_cert`、置信等级、harmful false acceptance 和分质量域误差，作为价格和残余风险模型输入。

认证货币价值：

\[
V_b^{\mathrm{cert}}=\phi_p(\max(0,U^{\mathrm{cert}}))
\]

买方最高可接受价格：

\[
P_{\max}=V_b^{\mathrm{cert}}-C_b(a)-[1-p_{\mathrm{det}}(a,q_1)]L_b(q_1)
\]

卖方最低价格：

\[
P_{\min}=R_s+C_s(a)+\kappa B
\]

仅当 \(P_{\max}\ge P_{\min}\) 时成交。成交价：

\[
P^*=P_{\min}+\gamma(P_{\max}-P_{\min})
\]

JABO 优化：

\[
\min_{a,B}C_{\mathrm{audit}}(a)+\kappa B+[1-p_{\mathrm{det}}(a,q_1)]L_b(q_1)
\]

并满足卖方欺诈威慑约束：

\[
p_{\mathrm{det}}(a,q_1)(B+F+P_{\mathrm{withheld}})\ge G_{\max}+\Delta_{\mathrm{safety}}
\]

质量只调整尚未被效用证书吸收的履约、合规和剩余风险，避免同一标签噪声或分布偏移被重复扣价。

## G5：端到端交易

G5 验证系统集成和性能，不再重新定义效用理论。应覆盖正常结算、效用失败、审计拒绝、审计不确定、交付根不一致、争议和超时。

---

# 15. 当前代码对齐清单

| 当前文件 | 当前职责 | G2 处理 |
|---|---|---|
| `tee-evaluator-rust/src/data.rs` | 读取 548-byte canonical rows，最多 100K | 保留 |
| `tee-evaluator-rust/src/model.rs` | Q16.16 128→64→1 MLP、hinge、梯度、一步更新 | 保留并增加 parity vectors |
| `tee-evaluator-rust/src/utility.rs` | ARUC-v0：全局更新、验证 MoM、MAD、Shift、FI、UCert | 保留为 baseline |
| `zk/circuits/utility_threshold.go` | 指标关系与阈值证明 | G2 不重构，G3 完整绑定 |
| `experiments/g0/` | SPRT/JABO 数学基线 | 冻结 |
| `experiments/g1/` | canonical data 与数据根一致性 | 冻结 |
| `experiments/reports/final-report.md` | G0/G1 结果 | 不覆盖，新增 G2 报告 |

当前实现最重要的 G2 解释是：Rust 评估器已经能产生 ARUC-v0 指标，但尚无真实训练 Oracle、买方异质性实验和证书校准，不能把当前 `u_cert` 直接表述为真实价值下界。

---

# 16. 建议参考研究

1. **Data Appraisal Without Data Sharing**：私有模型与未共享数据的前瞻效用评估、forward influence baseline。  
   https://proceedings.mlr.press/v151/xu22e.html

2. **Understanding Black-box Predictions via Influence Functions**：Influence Function 基础。  
   https://proceedings.mlr.press/v70/koh17a.html

3. **Data Shapley**：经典数据价值方法。  
   https://proceedings.mlr.press/v97/ghorbani19c.html

4. **Data Banzhaf**：估值稳定性与随机训练。  
   https://proceedings.mlr.press/v206/wang23e.html

5. **Data-OOB**：低成本数据估值 baseline。  
   https://proceedings.mlr.press/v202/kwon23e.html

6. **Distributionally Robust Data Valuation**：验证分布不确定性。  
   https://proceedings.mlr.press/v235/lin24t.html

7. **FairSwap**：Merkle 争议证据与智能合约公平交付 baseline。  
   https://eprint.iacr.org/2018/740

8. **PriME-Deal**：参考隐私匹配与抵押式公平交换，但不替代 DDTM 的买方条件化效用与 JABO。

---

# 17. G2 Definition of Done

只有同时满足以下条件，G2 才允许 PASS：

1. 完成买方条件化效用与 Oracle 规范；
2. 完成可复现训练 pipeline；
3. 完成至少 5 个买方任务；
4. 完成合成数据和至少一个真实数据集；
5. 完成候选产品目录；
6. 完成配对完整重新训练 Oracle；
7. 完成 ARUC-v0/v1 和主要 baseline；
8. 完成 Python fixed 与 Rust bit-exact Gate；
9. 完成独立证书校准；
10. 95% 证书覆盖达到 Gate；
11. harmful false acceptance 达到 Gate；
12. 完成多买方异质性分析；
13. 完成 20K、50K、100K 性能实验；
14. 完成消融；
15. 完成原始结果、manifest 和自动报告；
16. 所有结论区分已验证结果、失败结果、设计假设和研究目标。

---

# 18. 论文核心贡献建议表述

## 贡献一：买方条件化效用

> We formalize the prospective marginal utility of an unrevealed data product relative to a committed buyer task state, allowing the same dataset to have different and time-varying values across buyers.

## 贡献二：保守效用证书

> We design and calibrate a robust low-cost estimator into a transaction-specific lower-bound certificate against a paired full-retraining oracle, while keeping seller data and buyer task assets private.

## 贡献三：统一交易绑定

> We bind the buyer task state, seller data identity, valuation policy, utility certificate and settlement to a single versioned transaction transcript.

## 贡献四：风险调整定价

> We derive a feasible settlement interval from certified buyer-specific utility, verifiable quality risk, audit cost, residual loss and collateral capital cost, and jointly optimize audit intensity and seller collateral.

---

# 19. 最终冻结原则

DDTM-QAS 证明和定价的对象不是“数据的普遍价值”，而是：

> 某个已承诺、版本化的买方任务状态下，某个已承诺卖方数据产品的保守边际效用。

各层职责：

```text
完整重新训练 Oracle：效用真实性基准
ARUC：低成本估计器
U_cert：独立校准的保守证书
ZK 与 attestation：证明计算关系和执行上下文
区块链：保存不可替换的交易状态与证书引用
ZASA：提供可验证质量风险信号
JABO：决定审计强度和保证金
价格机制：把认证效用、风险和成本转换为成交区间
```

不得混淆：

- ZK 不能替代 Oracle 实验；
- TEE 不能替代效用校准；
- 数据质量不能替代买方任务价值；
- 区块链不能替代链下数据真实性；
- 高保证金不能替代可靠检测；
- 高覆盖率不能替代有信息量的证书。

本原则应作为 DDTM-QAS 后续实现、实验、论文图表和安全主张的最终审查标准。
