# DDTM-QAS：面向大规模表格数据交易的认证鲁棒效用评估、零知识自适应审计与审计-质押联合优化

## 摘要

数据交易中的核心矛盾并非数据能否被加密传输，而是买方在不获得原始数据、卖方不泄露数据内容、买方不泄露模型参数与验证集的条件下，如何在交易前确认候选数据对特定任务具有真实效用，并在交易后保证被评估数据与实际交付数据完全一致。现有区块链数据交易系统主要验证哈希、格式和托管状态；隐私数据估值研究能够在一定程度上计算模型效用，但通常缺少面向大规模数据的公开验证、交付一致性和经济激励闭环。为此，本研究提出 DDTM-QAS（Decentralized Data Trading Mechanism with Quality Attestation and Settlement）。系统面向最多 100000 行、128 维的表格二分类数据，模型结构公开，卖方数据、买方模型参数和验证集保持私密。

DDTM-QAS 包含三个具有严格因果关系的技术创新。第一，提出认证鲁棒效用证书 ARUC，在 Intel TDX 或 AMD SEV-SNP 机密虚拟机中，对完整候选数据执行确定性固定点 MLP 梯度计算、一次受约束更新、Median-of-Means 鲁棒聚合、分布偏移惩罚与一阶近似误差约束，并通过 Groth16 证明隐藏效用指标满足交易阈值。第二，提出零知识自适应语义审计 ZASA，以统一 Poseidon2 Merkle 根绑定挂牌、评估、审计和交付，利用未来 drand 阈值随机信标和 17 位四轮 Feistel 置换生成不可预测且不重复的审计索引，在 Groth16 电路中验证行成员关系、私有审计探针、标签边际、鲁棒距离、缺失率与序贯概率比状态。第三，提出审计-质押联合优化 JABO，在约束检测概率、误拒率和漏检率的同时，联合最小化审计成本、证明成本、保证金资本成本和残余损失，并由激励约束推导最低卖方保证金。

系统采用 XChaCha20-Poly1305 分块加密，买方解密后重算完整 Merkle 根，从而将“字节级一致性”与“语义质量”严格分离。本文给出完整威胁模型、协议、数据规范、电路关系、智能合约状态机和实验方案。已完成的机制仿真表明，在合格异常率 5%、不合格异常率 10%、误拒上界 1%、漏检上界 5% 的默认策略下，对 10% 异常率的检测概率为 95.12%，平均有效抽样量约 214 条；在价格为 10000、欺诈收益上界为 12000、安全裕度为 500 的示例中，最低保证金为 3141.09。其余机器学习、零知识证明和端到端性能结果在原型完成后依照预注册实验表填充，不预先虚构。

**关键词：** 数据交易；数据质量；可信执行环境；零知识证明；数据估值；序贯检验；机制设计

---

## 1 文献综述

### 1.1 数据质量评估从内在指标走向任务效用

传统数据质量评估以准确性、完整性、一致性、时效性和可用性为主，适合发现缺失字段、非法值和过期记录，但无法回答“该数据是否能改善买方具体模型”。同一数据集对不同任务、模型和目标分布的价值可能完全不同，因此数据交易中的质量应表示为条件效用，而非单一静态分数。

Xu 等提出 Data Appraisal Without Data Sharing，使用前向影响函数近似新数据对当前模型损失的一阶改善，并通过安全多方计算避免直接共享双方资产[1]。该研究说明，效用估值可以在不重新训练完整模型的情况下进行，但其一阶近似在强非线性、分布偏移和较大更新步长下会失真。Lin 等提出分布鲁棒数据估值，将价值定义为对分布鲁棒泛化误差的改善，避免依赖唯一、固定且完全可信的验证分布[2]。这类研究推动数据质量从“数据本身是否规整”转向“在不确定目标分布下是否产生稳健价值”。

### 1.2 隐私保护数据估值与可验证计算

PrivaDE 面向区块链数据市场提出双边隐私数据效用评估，综合经验损失、预测熵和特征多样性，并采用模型蒸馏、模型切分和 cut-and-choose 等技术提高恶意安全性[3]。其贡献在于同时保护数据和模型，但在线评估仍属于重型密码学计算。ZK-Value 通过 LSH-Shapley、桶级直方图和结构化证明优化，使数据估值可以生成公开验证的零知识证明[4]。该工作表明，只有将估值算法和证明结构共同设计，才能避免把传统机器学习算法直接搬入电路导致的不可接受成本。

现有研究仍存在三项不足。其一，隐私估值和公开验证通常分开处理；其二，多数方法只证明“某个算法按给定输入计算正确”，却没有解决评估数据与实际交付数据是否完全相同；其三，效用评分往往未直接进入保证金、审计强度和结算机制。

### 1.3 交易前污染检验与序贯审计

Vejling 等提出 Conformal Data Contamination Tests，将保形异常检测用于数据交易或共享，在较弱分布假设下检验外部数据是否超过污染阈值，并支持多供应方场景中的错误发现率控制[5]。该类方法适合作为语义质量检验，但不能替代数据完整性承诺：即使一份数据完全未被替换，也可能含有错误标签；反之，抽样语义检验也无法确定性证明两个大文件完全相同。

序贯概率比检验允许系统在每获得一个或一批审计结果后更新证据，在明显合格或明显不合格时提前停止。与固定样本审计相比，它可以降低期望抽样量，但必须明确两个质量区域：合格上界 τ0 和不合格下界 τ1。介于两者之间的灰色区不应被强制解释为通过或拒绝。

### 1.4 数据市场中的激励相容机制

Hu、Wainwright 和 Bates 研究未知质量数据采购，使用 Fisher 信息衡量质量，并通过事后统计检验约束卖方质量虚报[6]。Chen 等研究均值估计数据市场，通过基于参与者报告差异的支付调整，使遵守采集要求和如实提交形成纳什均衡[7]。这些研究说明，质量检验的统计能力必须直接进入支付机制；固定比例押金没有普适理论依据。

现有机制往往独立决定抽样量和保证金，忽略二者的替代关系。审计越强，检测概率越高，所需保证金可以下降；保证金越高，平台可在保持欺诈威慑的同时减少昂贵审计。因此需要联合优化，而非单独设计动态押金。

### 1.5 区块链、密码学承诺与可信执行环境

Poseidon2 等代数友好哈希适合零知识电路中的 Merkle 树，gnark 0.15 提供 BN254 Groth16、Poseidon2、Solidity 验证器导出和多方可信设置支持[8-10]。Groth16 验证开销小，但证明者仍需执行与约束规模相关的重型计算，且每个固定电路需要安全可信设置。

Intel TDX 和 AMD SEV-SNP 提供虚拟机级内存机密性、完整性和远程认证[11-13]。TEE 可以执行完整的 100000 行私密效用计算，但认证证明的是特定测量值代码运行于受保护环境，而非纯密码学意义上的任意计算正确性。因此本研究不将 TEE 报告等同于完整零知识计算证明，而使用独立随机零知识审计降低实现错误、输入替换和选择性欺诈风险。

4090 不属于 NVIDIA 机密计算 GPU 支持范围，因此两张 RTX 4090 仅用于本地模型训练和实验性 Groth16 GPU 加速，不纳入硬件保密边界[14]。正式安全演示使用 CPU 机密虚拟机；若需要机密 GPU，应迁移至 H100、H200、B200 或支持的 RTX Pro 数据中心平台。

### 1.6 研究空白

综合现有工作，可以归纳出一个尚未被完整解决的技术链：

1. 在卖方数据、买方模型参数和验证集均私密时，对完整大规模数据计算任务相关且抗异常值的效用；
2. 公开验证效用满足阈值，并确保评估数据、抽样审计数据和最终交付数据由同一根承诺绑定；
3. 在有限抽样下给出可解释的质量接受、拒绝和不确定状态；
4. 将检测概率、证明成本和资金锁定成本共同纳入押金与审计参数选择。

DDTM-QAS 以同一数据承诺和同一交易状态机连接上述四点。

---

## 2 系统设计与核心创新点

### 2.1 研究目标和系统对象

系统支持最多 100000 行、固定物理维数 128 的表格二分类数据。逻辑特征不足 128 维时零填充，但必须保留缺失掩码和逻辑维数。模型结构公开为 128-64-1 MLP：

\[
h=\operatorname{ReLU}(W_1x+b_1),\qquad f_\theta(x)=w_2^Th+b_2.
\]

模型参数 θ、买方验证集 V 和审计探针 A 私密。候选数据 D 属于卖方私有资产。系统输出的公开信息限于承诺、阈值是否满足、审计累计计数、状态和最终结算。

### 2.2 威胁模型

卖方可能虚报效用、构造投毒数据、只优化可能被检查的样本、评估后调包或重放证明。买方可能在看到数据后修改模型或验证集、构造恶意审计规则、虚报交付不一致。宿主机、对象存储、认证中继和少数链节点可能恶意。

系统依赖以下假设：TEE 硬件和认证链未被攻破；至少一个 Groth16 仪式参与者销毁随机性；drand 未达到阈值数量的串谋；密码学原语满足标准安全性；买方承诺先于卖方数据评估；单笔欺诈收益存在治理定义的保守上界 Gmax。

### 2.3 统一数据承诺

每行采用确定性 Q16.16 定点编码，包含 row_id、valid、label、timestamp、missing_mask 和 128 个 int32 特征。行叶子定义为：

\[
L_i=H_P(\text{TAG}_{row},h_{schema},v_D,i,valid_i,y_i,t_i,mask_i,Pack(x_i)),
\]

其中 HP 为 Poseidon2。树容量固定为 2^17=131072，空位使用与索引绑定的规范化填充叶子。节点哈希为：

\[
N_{l,j}=H_P(\text{TAG}_{node},l,N_{l-1,2j},N_{l-1,2j+1}).
\]

得到唯一根 cD。所有效用证书、抽样证明、密文清单和争议报告必须绑定同一 cD。该设计提供确定性的对象一致性：若交付后重算根不同，则交付对象与评估对象不一致；随机审计不承担文件同一性证明。

### 2.4 创新点一：ARUC 认证鲁棒效用证书

#### 2.4.1 完整数据效用计算

TEE 对完整卖方数据计算平均梯度：

\[
g_D=\frac1N\sum_{i=1}^{N}\nabla_\theta \ell(\theta;x_i,y_i),
\]

采用 hinge loss：

\[
\ell(\theta;x,y)=\max(0,1-yf_\theta(x)).
\]

将梯度逐参数裁剪到 [-Cg,Cg]，执行一次虚拟更新：

\[
\theta'=\theta-\eta\operatorname{clip}(g_D,-C_g,C_g).
\]

对验证集每条样本计算真实一步更新收益：

\[
\Delta_j=\operatorname{clip}(\ell(\theta;v_j)-\ell(\theta';v_j),-B_\Delta,B_\Delta).
\]

该定义不把一次更新冒充完整重训练收益，而将其作为可复现的交易效用函数。

#### 2.4.2 Median-of-Means 鲁棒聚合

利用交易前承诺的随机种子将验证集分为 G=31 个组：

\[
\bar\Delta_g=|V_g|^{-1}\sum_{j\in V_g}\Delta_j,
\]

\[
U_{MoM}=\operatorname{median}(\bar\Delta_1,\ldots,\bar\Delta_{31}),
\]

\[
D_{MAD}=\operatorname{median}(|\bar\Delta_g-U_{MoM}|).
\]

MoM 降低少量异常验证样本对均值的影响，MAD 表示组间不稳定性。

#### 2.4.3 一阶近似一致性约束

计算验证梯度 gV，一阶方向效用为：

\[
U_{FI}=\eta g_V^T\operatorname{clip}(g_D,-C_g,C_g).
\]

定义线性近似误差：

\[
E_{lin}=|U_{MoM}-U_{FI}|.
\]

若 E_lin 超过阈值，说明影响近似在该候选数据上失真，系统拒绝使用其质量证书。

#### 2.4.4 分布偏移惩罚

TEE 计算卖方数据与验证集的逐特征中心、尺度差异，形成有界偏移指标 S_shift。最终证书分数为：

\[
U_{cert}=U_{MoM}-\lambda_{mad}D_{MAD}-\lambda_{shift}S_{shift}-\lambda_{lin}E_{lin}.
\]

通过条件为：

\[
U_{cert}\ge\theta_U,\quad E_{lin}\le\theta_{lin},\quad S_{shift}\le\theta_{shift}.
\]

#### 2.4.5 Groth16 阈值证明

TEE 将私有指标写入承诺 cMetrics。UtilityThresholdCircuit 证明：承诺正确打开；Ucert 按公开权重由 UMoM 和惩罚项计算；三个阈值关系成立；承诺与 tid、cD、cM、cV、policyHash 和 sessionHash 绑定。电路不重复完整 MLP 运算，从而将大规模计算留在认证环境，将公开验证限制为数万级约束。

ARUC 的技术贡献不是单独使用 TEE 或 ZKP，而是把完整私密计算、鲁棒效用定义、近似误差约束和公开阈值证明组合为可编程证书。

### 2.5 创新点二：ZASA 零知识自适应语义审计

#### 2.5.1 私有审计探针

买方在卖方数据评估前承诺线性探针：

\[
f_A(x)=w_A^Tx+b_A.
\]

探针同时包含逐特征中心 μk、逆尺度平方 qk、边际阈值、距离阈值和缺失阈值。审计分数采用无除法整数算术：特征为 Q16.16，权重为 Q8.8，线性值和阈值使用同一原始尺度。

对样本 i：

\[
m_i=y_i(w_A^Tx_i+b_A),
\]

\[
d_i=\sum_k present_{ik}q_k(x_{ik}-\mu_k)^2,
\]

\[
r_i=\sum_k missing_{ik}.
\]

当 m_i 低于边际阈值、d_i 高于距离阈值或 r_i 高于缺失阈值时，审计失败标记 Yi=1。

#### 2.5.2 不可预测且不重复的索引

卖方挂牌时选择未来 drand 轮次。轮次公布后，系统验证 BLS 阈值签名并生成采样种子。ZK 电路使用四轮不平衡 Feistel 置换将序号映射到 17 位索引空间，前 8/9 位交替作为左右半部。因为置换为双射，批内和跨批索引不重复；未来随机数在承诺时不可预测，卖方无法提前只优化将被抽样的行。

若 Feistel 结果大于等于真实行数，协调器跳过该序号并继续生成有效序号；实际实现必须将有效 ordinal 列表或 skip count 绑定到交易 transcript，避免选择性跳过。正式版以电路可验证的 ordinal 为准，不允许调用方自由提交任意索引。

#### 2.5.3 AuditBatchCircuit

每个电路批次验证 64 条有效样本：索引来自采样置换；row_id 等于索引；叶子和 17 层路径重建为 cD；特征、权重、中心和尺度满足范围约束；审计探针承诺正确；线性边际、距离和缺失数量计算正确；累计有效样本数和失败数从前一状态过渡到后一状态。

#### 2.5.4 序贯概率比检验

定义合格异常率 τ0=0.05，不合格异常率 τ1=0.10，误拒上界 α=0.01，漏检上界 β=0.05。累计对数似然比为：

\[
L_n=F_n\log\frac{\tau_1}{\tau_0}+(n-F_n)\log\frac{1-\tau_1}{1-\tau_0},
\]

其中 Fn 为失败数。边界：

\[
A=\log\frac{1-\beta}{\alpha},\qquad B=\log\frac{\beta}{1-\alpha}.
\]

当 Ln≥A 拒绝，当 Ln≤B 通过，否则继续。达到最大样本数 1536 仍未越界时输出 INCONCLUSIVE，不得自动视为通过。

ZASA 的创新性来自统一根承诺、未来随机索引、私有语义探针、零知识成员证明和序贯停止的联合，而非单纯 Merkle 抽样。

### 2.6 创新点三：JABO 审计-质押联合优化

设诚实生产成本为 CH，低质量生产成本为 CL，平台对单笔欺诈收益给出上界 Gmax。若作弊未被发现，卖方获得价格 P 并节省生产成本；若被发现，失去 P 且保证金 B 被罚没。保守激励约束为：

\[
p_{det}(P+B)\ge G_{max}+\delta.
\]

最低保证金：

\[
B_{min}=\max\left(0,\frac{G_{max}+\delta}{p_{det}}-P\right).
\]

策略 π 的成本函数为：

\[
J(\pi,B)=c_{TEE}+c_{proof}E[K]+c_{row}E[T]+r_BB\frac{T_{lock}}{365}+L_{max}p_{miss}(\pi).
\]

优化问题：

\[
\min_{\pi,B}J(\pi,B)
\]

满足激励约束、合格区误拒概率不超过 α、不合格区漏检概率不超过 β。策略空间包含 τ0、τ1、α、β、批大小和最大样本数。动态规划精确计算各污染率下的接受、拒绝、不确定概率和期望样本量，再求最低保证金和总成本。

JABO 将审计与押金从独立经验参数变成同一优化问题。审计更强时保证金下降，审计更昂贵时可通过提高保证金保持威慑。

### 2.7 加密交付与争议

规范化数据按 8 MiB 分块，使用 XChaCha20-Poly1305 加密。AAD 绑定 tid、cD、schemaHash、chunkIndex 和 totalChunks。数据密钥通过 X25519 派生的密钥封装给买方。买方解密后对完整数据重建 Poseidon2 Merkle 根，只有 cD'=cD 时确认。

发生争议时，新的 TEE 会话验证链上绑定的密文清单、密钥和对象摘要，对全部数据解密并重算根，输出 DELIVERY_MATCH 或 DELIVERY_MISMATCH 认证回执。买方无法用不同密文制造退款证据。

---

## 3 系统实现与实验设计

### 3.1 实现架构

系统由七层组成：确定性规范化与 Merkle 构建；买方模型训练；TEE 效用评估；gnark Groth16 电路；认证与 drand 中继；Solidity 合约；MinIO/PostgreSQL 服务。开发环境使用本地 Mock Attestation，正式安全验证使用 TDX 或 SEV-SNP。

技术栈固定如下：Ubuntu 24.04；Go 1.25、gnark 0.15、gnark-crypto 0.20.1；Rust 2024 edition；Python 3.11 和 PyTorch；Solidity 0.8.30 与 Foundry；PostgreSQL 16；MinIO；XChaCha20-Poly1305；BN254 Groth16；Poseidon2；drand。

### 3.2 硬件分配

本地工作站使用 16-32 核 CPU、64-128 GB 内存和 2×RTX 4090。GPU0 用于模型训练、污染生成和完整重训练 oracle；GPU1 用于实验性 ICICLE Groth16 证明或并行证明队列。两张 4090 不属于正式机密计算边界。安全演示在 TDX/SEV-SNP 机密虚拟机中使用 CPU 执行完整效用评估和 CPU Groth16 回退。

### 3.3 数据集与规模

实验至少选择三类公开表格二分类数据：Covertype 二分类重标记、HIGGS 的 100000 行子集、信用/欺诈或人口收入数据。统一生成 N∈{10000,25000,50000,100000}，d∈{64,128} 的配置。每个数据集划分为买方基础训练集、买方私有验证集和卖方候选集；验证集和模型承诺在污染实验前固定。

### 3.4 污染模型

设置 label flip、Gaussian feature noise、missingness、duplicate injection、class imbalance、covariate shift、targeted gradient poisoning 和混合污染。污染率取 1%、2%、5%、8%、10%、12%、15%、20%。所有随机种子、被污染索引和污染参数写入实验配置，确保可重复。

### 3.5 对比方法

效用对比：静态质量分、普通平均一步收益、前向影响函数、一步更新效用、MoM 一步效用、ARUC、完整重训练 oracle。审计对比：固定 64/128/256/512 样本审计、传统置信区间审计、ZASA 序贯审计。机制对比：固定 10% 押金、仅由质量分数决定押金、仅由检测概率决定押金、JABO。

### 3.6 评价指标

效用指标包括与完整重训练收益的 Spearman 相关系数、有害数据识别 AUROC、Top-k 数据集排序重合率、E_lin、误接受率。审计指标包括合格区误拒率、不合格区检出率、平均/P95 样本数、INCONCLUSIVE 比例。密码学指标包括约束数、setup/prove/verify 时间、峰值内存、proof size 和 Solidity gas。系统指标包括规范化、Merkle 构建、TEE 评估、加密、上传、解密和根重算的时间。机制指标包括最低保证金、资金成本、审计成本、欺诈期望收益和残余损失。

### 3.7 消融实验

1. 去除 MoM，仅用普通均值；
2. 去除 S_shift；
3. 去除 E_lin；
4. 使用静态随机样本替代序贯审计；
5. 使用整体哈希替代行级 Merkle，比较局部审计能力；
6. 使用固定 10% 押金替代 JABO；
7. AuditBatch 64 与 128 的证明时间、内存和总 gas 对比；
8. TEE Mock、本地 CPU 和真实 TDX/SNP 的性能差异。

### 3.8 安全实验

测试评估后调包、Merkle path 篡改、错误 row_id、审计规则替换、旧 drand 轮次、证明跨交易重放、TEE 报告重放、密文块篡改、nonce/AAD 错误、买方假争议和状态机超时。每项攻击必须导致密码学拒绝、认证拒绝或经济惩罚。

### 3.9 预注册验收标准

- 100000×128 数据完成规范化和完整根构建；
- 买方解密后完整根一致性检测率为 100%；
- UtilityThresholdCircuit 约束数不超过 100000；
- AuditBatch-64 约束数目标不超过 2500000；
- 10% 异常率检出概率不低于 95%；
- 5% 合格边界误拒概率不高于 1%；
- ARUC 对完整重训练效用排序的 Spearman 相关系数目标不低于 0.75；
- 4090 GPU 证明失败时仍可使用 CPU 完成端到端流程；
- 任何 INCONCLUSIVE 状态不自动结算给卖方。

---

## 4 实验结果

### 4.1 已获得的机制仿真结果

本研究已经实现 JABO 中截断 Wald SPRT 的动态规划计算。默认参数为 τ0=0.05、τ1=0.10、α=0.01、β=0.05、批大小 128、最大样本数 1536。边界为 B=-2.98568、A=4.55388。

| 实际异常率 | 接受概率 | 拒绝概率 | 不确定概率 | 期望有效样本数 |
|---:|---:|---:|---:|---:|
| 0% | 1.000000 | 0 | 0 | 56.00 |
| 2% | 0.9999996 | 0.0000004 | 约0 | 77.20 |
| 5% | 0.9921153 | 0.0078760 | 0.0000087 | 176.67 |
| 8% | 0.3436533 | 0.6497705 | 0.0065762 | 365.96 |
| 10% | 0.0487690 | 0.9512150 | 0.0000160 | 214.34 |
| 12% | 0.0072138 | 0.9927862 | 约0 | 133.73 |
| 15% | 0.0005088 | 0.9994912 | 约0 | 83.15 |
| 20% | 0.0000082 | 0.9999918 | 约0 | 50.73 |

结果体现序贯审计的预期性质：明显合格和明显不合格的数据快速停止，接近 5%-10% 灰色区的数据需要更多样本。对 10% 异常率，拒绝概率 95.12%，满足 β=5% 的设计目标。

在示例参数 P=10000、Gmax=12000、安全裕度 δ=500 时：

\[
B_{min}=\frac{12500}{0.951215}-10000=3141.09.
\]

该数值不是通用保证金比例，而是给定检测能力和欺诈收益上界下的计算结果。

### 4.2 待实测结果表

尚未运行的机器学习、TEE、ZKP 和链上实验不得填入虚构数字。原型完成后按以下表格填充。

**表：ARUC 效用准确性**

| 数据集 | N | 污染类型/率 | FI 相关系数 | 一步更新相关系数 | ARUC 相关系数 | AUROC |
|---|---:|---|---:|---:|---:|---:|
| 待测 | | | | | | |

**表：ZKP 性能**

| 电路 | 约束数 | PK/VK | CPU prove | GPU prove | verify | proof size | gas |
|---|---:|---:|---:|---:|---:|---:|---:|
| UtilityThreshold | 待测 | | | | | | |
| AuditBatch-64 | 待测 | | | | | | |

**表：端到端性能**

| N×d | 规范化 | Merkle | TEE ARUC | ZASA 总证明 | 加密上传 | 解密重算根 | 总时间 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 100000×128 | 待测 | | | | | | |

### 4.3 预期结果解释边界

即使 ARUC 与完整重训练具有较高相关性，也只能说明定义的固定模型、一步更新和验证分布下具有预测能力，不能声称数据拥有与任务无关的绝对价值。ZASA 证明审计探针下的异常率证据，不等同于绝对真实标签。JABO 的诚实激励成立依赖 Gmax 上界、风险中性和可执行罚没条件。

---

## 5 总结

本文设计 DDTM-QAS，以统一 Poseidon2 数据承诺为主线，将完整私密任务效用计算、公开阈值证明、随机零知识语义审计、确定性交付验证和经济机制连接为一个可实现协议。ARUC 解决“数据是否对买方任务有稳健效用”，ZASA 解决“同一份数据是否含有超阈值语义异常”，JABO 解决“审计成本、检测能力和保证金如何共同选择”。

该方案刻意避免两个常见错误：一是把 TEE 认证报告描述为完整密码学计算证明；二是用随机抽样替代完整交付一致性。系统使用 TEE 执行全部 100000 行效用计算，Groth16 证明隐藏阈值与抽样关系，Merkle 根和 AEAD 保证最终交付对象的确定性一致性。

后续工作包括完成真实 TDX/SNP 部署、评估 gnark ICICLE 在双 4090 上的稳定性、对审计探针进行保形校准、完成 Groth16 多方设置仪式，以及在多数据集、多污染类型和不同交易价值下验证 JABO 的经济效果。

---

## 参考文献

[1] Xu X, Hannun A, van der Maaten L. Data Appraisal Without Data Sharing. AISTATS, 2022.

[2] Lin X, Xu X, Wu Z, et al. Distributionally Robust Data Valuation. ICML, 2024.

[3] Wong W K, Torkamani S, Ciampi M, Sarkar R. PrivaDE: Privacy-preserving Data Evaluation for Blockchain-based Data Marketplaces. arXiv:2510.18109, 2025.

[4] Wang Z, Ma P, Xue Z, et al. ZK-Value: A Practical Zero-Knowledge System for Verifiable Data Valuation. arXiv:2605.03581, 2026.

[5] Vejling M V, Pandey S R, Biscio C A N, Popovski P. Conformal Data Contamination Tests for Trading or Sharing of Data. arXiv:2507.13835, 2025.

[6] Hu Y, Wainwright M J, Bates S. Buying Data of Unknown Quality: Fisher Information Procurement Auctions. arXiv:2604.08821, 2026.

[7] Chen K, Clinton A, Kandasamy K. Incentivizing Truthful Submissions in a Data Marketplace for Mean Estimation. AISTATS, 2026.

[8] Consensys. gnark v0.15 Documentation and Package Reference. 2026.

[9] Consensys. gnark-crypto BN254 Poseidon2 Package v0.20.1. 2026.

[10] Consensys. gnark Groth16 BN254 MPC Setup Package. 2026.

[11] Intel. Intel Trust Domain Extensions Documentation and DCAP Attestation Specifications. 2026.

[12] AMD. SEV-SNP Firmware ABI Specification and Platform Attestation Guide. 2025-2026.

[13] Confidential Containers Project. Trustee and TEE Attestation Architecture Documentation.

[14] NVIDIA. Confidential Containers Supported Platforms. 2026.

[15] drand. Protocol Specification and Threshold BLS Cryptography Documentation. 2026.

[16] Libsodium. XChaCha20-Poly1305 Construction Documentation. 2026.

[17] Wald A. Sequential Analysis. Wiley, 1947.

[18] Koh P W, Liang P. Understanding Black-box Predictions via Influence Functions. ICML, 2017.

[19] Lugosi G, Mendelson S. Mean Estimation and Regression under Heavy-Tailed Distributions: A Survey. Foundations of Computational Mathematics, 2019.

[20] Grassi L, Khovratovich D, Rechberger C, et al. Poseidon: A New Hash Function for Zero-Knowledge Proof Systems. USENIX Security, 2021.
