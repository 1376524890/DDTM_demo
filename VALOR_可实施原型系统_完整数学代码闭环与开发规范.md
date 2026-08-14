# VALOR：权利感知、质量可验证与用途可审计的数据交易原型系统

> **Value-Aware Liability and Optimal Risk Allocation for Data Transactions**  
> 完整数学机制、质量验证基线、分布式审计、数据流向与用途审计、代码接口、实验协议与开发验收规范

## 摘要

VALOR 面向可复制、可重复授权、可按不同权利范围交易的数据要素。系统将一笔可交易产品定义为数据资产、元数据声明和机器可读权利束的组合，并把交易决策严格组织为“权利可授予性与合规硬门槛 → 质量验证 → 买方特定数据价值 → 审计信息价值 → 分布式验证采购与可信执行 → 系统违约检测能力 → 卖方责任资本 → 权利感知价格区间 → 数据交付与用途控制 → 结算 → 可验证反馈”的闭环。

质量验证不从分布式节点机制开始设计。原型系统先对已有数据质量算法建立单节点参考复现层：结构、完整性、唯一性和约束检查采用 Deequ 类声明式质量验证语义；标签错误采用 Confident Learning；数值和类别分布变化采用经典两样本统计检验；多变量分布变化采用 MMD；重复记录采用确定性哈希和可选近重复算法。只有参考算法、原生 Python 实现和受控 ground truth 之间满足预先声明的复现 Gate，某个质量 primitive 才能进入分布式审计层。分布式层不改变 primitive 的数学定义，而把其封装为绑定数据哈希、算法哈希、参数来源和执行环境的可重放任务，由多个独立节点执行并提交证据，市场通过反向 VCG 发现审计成本，并由 BFT、随机强验证、质押和任务重分配约束拜占庭、理性和失效节点。

数据交易完成后，系统继续维护 Rights Bundle、Usage State、Data Flow Event 和 Usage Receipt。API/Compute-Only 模式通过 Policy Decision Point 和 Policy Enforcement Point 在每次使用前执行时间、次数、用途、主体、环境、隐私预算和转授权约束；Download 模式不声称能够阻止离线复制，只通过接收方特定指纹、事件日志、合同责任与事后证据提高可追责性。所有数据流向事件进入带哈希链的 lineage ledger，并可映射为 OpenLineage 风格的 dataset/run/job 事件；权利表达保持与 W3C ODRL 的 permission/prohibition/duty/constraint 语义兼容。

整个原型禁止以无来源默认值代替应由数据、市场、校准、合同或优化过程得到的量。所有进入核心公式的参数必须携带来源类型、证据引用、单位和版本；任何无法解析来源的参数都必须 fail closed。固定数值仅允许出现在数学恒等式、密码学/数据类型标准或测试 fixture 中，不允许作为论文实验和交易决策参数。

完整主链为：

\[
\boxed{
Entitlement
\rightarrow
QualityReference
\rightarrow
DistributedQualityAudit
\rightarrow
\underline V_{D,R}^{gross}
\rightarrow
\Pi_A^*
\rightarrow
\underline p_B^{sys}
\rightarrow
B_S^*
\rightarrow
(P_\tau^{min},P_\tau^{max})
\rightarrow
P_\tau^*
\rightarrow
UsageControl
\rightarrow
\mathcal S_T
\rightarrow
\Theta_{t+1}
}
\]

---

# 1. 系统目标与边界

VALOR 的目标不是重新建设一个完整数据交易所，也不把区块链、BFT、TEE、MPC、ZK、数据水印或某种特定共识链作为并列创新。系统要实现的是一套可嵌入现有数据交易平台、可信数据空间或数据服务市场的交易决策与经济执行层。

核心问题依次为：

1. 卖方是否有资格提供该数据和该权利；
2. 数据在结构、标签、分布、声明和完整性方面是否满足可验证条件；
3. 同一数据对当前买方和当前权利束究竟能够创造多少经济价值；
4. 为减少交易错误决策，继续购买多少审计信息是经济合理的；
5. 不可信审计节点如何通过市场采购、冗余验证、挑战、质押和 BFT 形成可靠证书；
6. 当前系统检测能力对应多大的卖方最低责任资本；
7. 数据复制销售、排他权、使用期限、次数、用途和未来许可机会如何进入价格；
8. 成交后如何控制、记录或追踪数据使用；
9. 如何把可确认的真实结果反馈到下一笔交易，而不让系统用自己的 PASS 结果自我强化。

原型的主实验域为 public tabular binary classification。该约束用于保证 Data-VOI、标签质量、分布适配和真实重训练 Oracle 能够完整实现。资产、权利、审计、交易和使用控制接口不依赖表格二分类的具体模型，可在后续接入其他模态。

---

# 2. 参与方与信任边界

系统包含四类必要参与方：

- Seller \(S\)：提供数据资产、元数据声明、可授予权利、基础审计托管和卖方责任资本；
- Buyer \(B\)：提供 buyer context、业务收益结构、预算、增量审计需求和权利需求；
- Auditor Pool \(\mathcal A=\{A_1,\ldots,A_N\}\)：执行质量验证 primitive、提交证据、参与 challenge 和证书形成；
- Market Protocol \(M\)：对象绑定、参数解析、审计采购、证书状态、资金托管、权利登记、用途授权、结算和反馈。

可信边界分为：

\[
\boxed{
AlgorithmCorrectness
\neq
NodeTrustworthiness
\neq
ContractEnforceability
}
\]

其中：

- 算法正确性由参考复现、单元测试和 calibration 证明；
- 节点可信性由分布式执行、challenge、stake、BFT 和信誉处理；
- 合同可执行性由 escrow、bond、usage gateway 和外部法律/治理接口处理。

BFT 只能保证在指定故障模型下形成唯一协议证书，不能把多数意见自动解释为数据质量真相。

---

# 3. 数据资产、权利束与可交易产品

## 3.1 Data Asset

数据资产定义为：

\[
A_D=(assetID,versionID,D,M_D,H(D),H(M_D),ProvenanceRef).
\]

其中 \(D\) 是实际数据对象；\(M_D\) 是元数据、质量声明和卖方合同声明；`versionID` 保证后续更新不复用旧对象承诺。

## 3.2 Rights Bundle

一笔交易授予的权利束定义为：

\[
R_\tau=(r^{class},a,t_0,t_1,q,\Psi,G,e,\delta,\chi,\varepsilon,retention,deleteDuty).
\]

含义分别为：

- \(r^{class}\)：权利类别；
- \(a\)：访问模式；
- \([t_0,t_1]\)：有效时间；
- \(q\)：最大使用次数；
- \(\Psi\)：允许用途集合；
- \(G\)：地域/组织范围；
- \(e\)：排他性；
- \(\delta\)：转授权/再分发权限；
- \(\chi\)：衍生数据/模型权限；
- \(\varepsilon\)：若使用差分隐私查询时的总隐私预算；
- `retention`：允许保留周期；
- `deleteDuty`：删除义务。

权利表达采用 ODRL-compatible profile：Permission、Prohibition、Duty 和 Constraint 可以映射到上述字段，但原型内部保持类型化结构，避免在核心计算里解析任意 RDF 图。

## 3.3 Tradable Product

\[
\boxed{Z_\tau=(A_D,R_\tau)}.
\]

交易价格、Data-VOI 和责任均针对 \(Z_\tau\)，而不是只针对裸数据 \(D\)。

---

# 4. 交易承诺与对象绑定

每笔交易生成：

\[
\boxed{
\tau=(
 txID,sellerID,buyerID,assetID,versionID,
 H(D),H(M_D),H(R_\tau),
 policyVersion,timestamp
)
}
\]

必须满足：

\[
D_{valuation}=D_{quality}=D_{audit}=D_{delivery}
\]

以及：

\[
H(R_{authorization})=H(R_\tau).
\]

任何对象哈希、版本或权利束不一致均为确定性合同错误；若来自卖方替换或虚假交付，则进入 SELLER_BREACH。

---

# 5. 参数来源治理：禁止无来源默认值

## 5.1 Resolved Parameter

任何进入论文公式和交易决策的参数都表示为：

```text
ResolvedParameter:
    name
    value
    dtype
    unit
    source_kind
    source_ref
    resolved_at
    version_hash
    uncertainty / interval (optional)
```

`source_kind` 只能来自：

```text
OBSERVED_DATA
CALIBRATED
CONTRACT_INPUT
MARKET_DISCOVERED
OPTIMIZER_OUTPUT
THREAT_SCENARIO
STANDARD_CONSTANT
```

## 5.2 允许的参数来源

例如：

- \(\Lambda_j\)：CALIBRATED；
- \(\underline p_B^{sys}\)：CALIBRATED / certification；
- \(b_i\)：MARKET_DISCOVERED；
- \(p_i^A\)：机制输出；
- \(m,q,\rho\)：OPTIMIZER_OUTPUT 或显式 CONTRACT_INPUT；
- \(\alpha_V,\alpha_D\)：CONTRACT_INPUT / experiment protocol；
- \(G_S^{dev},G_i^{dev}\)：THREAT_SCENARIO 或可验证上界；
- \(B_S^*,P_\tau^*,MC_A^{pay}\)：机制输出；
- SHA-256、IEEE dtype machine epsilon：STANDARD_CONSTANT。

## 5.3 Fail-Closed

核心算法调用前执行：

\[
ResolveAll(RequiredParams)=1.
\]

否则返回：

```text
UNRESOLVED_PARAMETER
OUT_OF_CERTIFIED_RANGE
MISSING_EVIDENCE_REF
UNIT_MISMATCH
```

禁止如下实现：

```python
alpha = config.get("alpha", 0.05)
rho = config.get("rho", 0.1)
m = config.get("committee_size", 7)
```

必须使用：

```python
alpha = require_resolved("alpha")
rho = require_resolved("rho")
m = require_resolved("committee_size")
```

测试 fixture 可以使用显式数值，但必须标记 `source_kind=TEST_FIXTURE`，且该来源类型不得进入 experiment/production schema。

---

# 6. Entitlement 与 Compliance Hard Gate

在价值评估前验证：

\[
Entitled(S,A_D,R_\tau)=1
\]

与：

\[
Compliant(A_D,R_\tau,B)=1.
\]

该层处理不可通过经济权衡放松的硬约束，例如卖方无权授予某种排他权、买方不具备必要访问资格、权利菜单与既有许可冲突、数据版本被撤销等。

若硬约束失败，交易不进入 Data-VOI 和 Audit-VOI。

---

# 7. 数据质量验证的总体结构

质量验证被分为三个严格不同的对象：

\[
\boxed{
QualityPrimitive
\rightarrow
QualityAction
\rightarrow
AuditPolicy
}
\]

`QualityPrimitive` 是单一已有算法或确定性检查；`QualityAction` 是在指定委员会、安全配置和证据规则下对 primitive 的一次系统执行；`AuditPolicy` 是根据 posterior、成本和历史结果动态选择下一 QualityAction 或 STOP 的规则。

进一步区分：

\[
\lambda_p^{prim}(o\mid x)
\]

为单节点 primitive 的输出分布；

\[
\Lambda_a^{action}(y\mid x,\Gamma)
\]

为分布式动作的输出分布；

\[
p_B^{sys}(\Pi_A)
\]

为完整审计策略最终识别卖方违约的系统概率。

这三层禁止混用。

---

# 8. 质量维度与 Ground Truth

质量验证不压缩成任意加权的“总质量分”。原型输出可解释的质量证据向量：

\[
Q(D)=
(Q_{schema},Q_{complete},Q_{valid},Q_{unique},Q_{label},Q_{shift},Q_{claim},Q_{commit}).
\]

每个维度对应独立 contract predicate 和原始统计量。

交易状态仍为：

\[
X\in\{G,L,B\}.
\]

判定优先级：

```text
if SellerContractViolation:
    X = B
elif TechnicalSuitabilityPredicate(D, C_b, R_tau) == 0:
    X = L
else:
    X = G
```

`L` 表示卖方诚实但对当前买方技术适配性不足；单纯经济价值低不定义为 L，经济价值不足由价格可行性产生 NO_TRADE。

---

# 9. 质量 Primitive QP-01：声明式结构与完整性验证

该类 primitive 复现 Deequ 类数据约束验证语义，Python 原生实现与 reference adapter 使用相同数据、相同约束和相同对象承诺。

对列 \(j\) 的完整率：

\[
Completeness_j
=
1-\frac{1}{n}\sum_{i=1}^{n}\mathbf1[x_{ij}\in Missing].
\]

有效域比例：

\[
Validity_j
=
\frac{1}{n}\sum_{i=1}^{n}\mathbf1[x_{ij}\in\Omega_j].
\]

唯一值比例：

\[
Uniqueness_j
=
\frac{|\{x_{ij}:i=1,\ldots,n\}|}{n}.
\]

整行重复率使用 canonical row serialization 的哈希：

\[
h_i=H(Canonicalize(row_i)),
\]

\[
DuplicateRate
=1-\frac{|\{h_i\}|}{n}.
\]

所有阈值必须来自卖方声明、买方要求、独立 clean reference 的 calibration 或 protocol optimization；不得在代码里固化缺失率、唯一率等阈值。

Reference Gate：

- integer/count 统计必须完全一致；
- schema/domain 判定必须逐行一致；
- 浮点聚合使用由 dtype 和运算误差上界导出的 numeric tolerance；
- 任一 reference mismatch 必须保留完整输入 hash、算法版本和差异记录。

---

# 10. 质量 Primitive QP-02：Confident Learning 标签错误验证

二分类表格数据的标签错误验证采用 Confident Learning 作为主要已有算法基线。

给定 observed label \(\tilde y\) 和严格 out-of-sample 的预测概率：

\[
\hat p_i(k)=P(y=k\mid x_i,\theta^{-fold(i)}).
\]

每个类别的 confident threshold 由该类别样本的 out-of-sample probability 统计得到：

\[
t_k=T(\{\hat p_i(k):\tilde y_i=k\}),
\]

其中 \(T\) 的具体定义必须与所复现的 Confident Learning 版本绑定，不由 VALOR 自定义常数代替。

由 thresholded confident assignment 形成 confident joint：

\[
C_{ab}
=
\sum_i
\mathbf1[\tilde y_i=a,\hat y_i^{conf}=b].
\]

原型至少输出：

```text
confident_joint
label_issue_indices
label_quality_scores
estimated_label_error_rate
out_of_sample_pred_probs_hash
model_spec_hash
```

交叉验证折数、基础分类器、随机种子和概率校准方法全部必须在 `QualityAlgorithmSpec` 中显式提供。主实验不得把训练内预测概率用于标签错误检测。

复现分为两条执行路径：

1. `CleanlabReferenceAdapter`：调用锁定版本的 cleanlab；
2. `NativeConfidentLearning`：按论文定义实现关键 confident joint、issue ranking 和统计输出。

Gate 不要求两个实现内部代码相同，但要求在相同 OOF probabilities 下：

- confident joint 一致或在明确版本语义下等价；
- issue ranking 的一致性指标可计算；
- injected label-noise ground truth 上输出 TP/FP/FN/TN；
- 差异超过 reproduction tolerance 时禁止进入 distributed catalog。

---

# 11. 质量 Primitive QP-03：单变量分布变化

对连续特征采用两样本 Kolmogorov–Smirnov statistic：

\[
D_j^{KS}
=
\sup_x|F_{D,j}(x)-F_{ref,j}(x)|.
\]

对类别特征使用合同指定的类别分布检验，并保存 contingency statistics。显著性水平 \(\alpha_{shift}\) 必须作为 `ResolvedParameter`，不允许使用库的隐式决策阈值。

当同时测试多个列时，是否进行多重比较校正以及校正方法属于实验/合同策略；主实验提供 Holm procedure 并要求 \(\alpha_{family}\) 显式输入。

输出既包含 test statistic，也包含 p-value 和 effect size。系统不得只保存 PASS/FAIL。

---

# 12. 质量 Primitive QP-04：多变量 MMD

给定 source/reference 样本 \(X=\{x_i\}_{i=1}^{n}\) 和 candidate 样本 \(Y=\{y_j\}_{j=1}^{m}\)，使用无偏 MMD 统计量：

\[
\widehat{MMD}_u^2
=
\frac{1}{n(n-1)}\sum_{i\ne i'}k(x_i,x_{i'})
+
\frac{1}{m(m-1)}\sum_{j\ne j'}k(y_j,y_{j'})
-
\frac{2}{nm}\sum_{i,j}k(x_i,y_j).
\]

kernel 类型与参数必须来自 `KernelSpec`。若使用 RBF median heuristic，则带宽由当前 calibration data 计算并记录为 OBSERVED/CALIBRATED，不写成固定常数。

若使用 permutation test，置换次数由目标 p-value resolution \(\epsilon_p\) 决定：

\[
B_{perm}\ge \left\lceil\frac{1}{\epsilon_p}\right\rceil-1.
\]

因此代码要求的是 `target_pvalue_resolution`，而不是任意默认 `n_permutations`。

---

# 13. 质量 Primitive QP-05：重复、近重复与数据声明

精确重复使用 canonical row hash，不依赖相似度阈值。

近重复检测属于可选 primitive。若使用 MinHash/LSH 或向量相似性：

- similarity threshold 必须来自 injected near-duplicate calibration 或 buyer contract；
- hash permutation count / sketch size 必须由 target error bound 或 experiment config 显式解析；
- 近重复输出不能覆盖精确重复结果。

`MetadataClaimAudit` 将卖方声明写成机器可执行 predicate，例如：

```text
max_missing_rate(column)
allowed_categories(column)
label_error_upper_bound
schema_version
class_coverage_requirement
provenance_claim
```

系统直接记录 predicate、observed metric、comparison 和 evidence hash。

---

# 14. Quality Algorithm Catalog

每个可用 primitive 必须注册：

```text
QualityAlgorithmSpec:
    algorithm_id
    family
    implementation_kind: REFERENCE | NATIVE
    source_title
    source_version / package_version
    code_hash
    runtime_image_hash
    input_schema_hash
    output_schema_hash
    required_parameters[]
    determinism_spec
    distributed_migration_class
```

`distributed_migration_class` 只允许：

```text
MERGEABLE_EXACT
GLOBAL_STATISTIC
MODEL_BASED_REPLICATED
SECURE_EXECUTION_ONLY
```

解释：

- `MERGEABLE_EXACT`：计数、missing、domain counts 等可用代数状态精确聚合；
- `GLOBAL_STATISTIC`：KS/MMD 等需要全局统计或严格定义的合并算法；
- `MODEL_BASED_REPLICATED`：Confident Learning 等由每个委员会节点在同一 committed dataset/model spec 上独立完整执行；
- `SECURE_EXECUTION_ONLY`：只能在受控计算环境中执行，节点获取 capability 而非明文副本。

任何 primitive 在 Reference Reproduction Gate 通过前：

```text
distributed_enabled = false
```

---

# 15. Reference Reproduction Gate

质量算法进入论文实验和分布式层之前必须生成 `QualityReproductionCertificate`：

```text
certificate_id
algorithm_id
reference_impl_hash
native_impl_hash
reference_dataset_hashes
injection_spec_hashes
parameter_manifest_hash
metric_comparison
runtime_comparison
statistical_equivalence_result
created_at
```

Gate 条件按算法类型定义，不使用统一拍脑袋阈值。

## 15.1 Deterministic primitive

要求 canonical output 完全相等：

\[
H(Output_{native})=H(Output_{reference}).
\]

## 15.2 Floating statistical primitive

比较误差界由 numeric analysis 和 dtype 计算：

\[
|v_{native}-v_{ref}|\le \epsilon_{alg}(dtype,n,operationGraph).
\]

`epsilon_alg` 由实现声明的数值误差模型求出并写入证书。

## 15.3 Stochastic/model-based primitive

固定 `RandomnessSpec` 后比较输出；若算法本身包含不可消除随机性，则执行 paired repetitions，比较目标 metric 的 CI，而不是使用单次固定容差。

## 15.4 Ground-truth injection

为每种质量错误建立受控注入：

```text
missingness_injection
schema_violation
exact_duplicate
near_duplicate
label_flip
covariate_shift
label_shift
metadata_false_claim
committed_dataset_replacement
```

注入参数同样必须有 `InjectionSpec`，实验扫描值来自实验设计，不隐藏在代码中。

---

# 16. 从单节点质量算法到分布式审计节点

分布式迁移的目标不是把已有算法改写成新的“分布式算法”，而是保持算法语义不变，改变执行和信任模型。

每次审计任务：

\[
T_a=(
 txID,dataCommitment,rightsCommitment,
 algorithmSpecHash,paramManifestHash,
 executionSpecHash,deadline
).
\]

节点输出：

\[
E_i=(
 nodeID,T_a,result,rawMetrics,
 evidenceArtifacts,executionHash,timestamp,signature
).
\]

必须满足：

\[
H(D_{node})=H(D)_\tau
\]

以及：

\[
H(AlgorithmSpec_{node})=H(AlgorithmSpec)_{T_a}.
\]

分布式结果与质量算法本身严格分层：节点是否作恶由 security layer 判断；数据是否满足质量 predicate 由 primitive result 判断。

---

# 17. 分布式原型的实际运行方式

为了在代码层面真实体现“不同节点”，P0 原型使用独立 OS process / Docker container 运行 auditor node，并通过 HTTP 传输任务和证据，而不是在同一 Python 函数中循环模拟多个节点。

每个节点服务至少暴露：

```text
GET  /health
POST /audit/tasks
GET  /audit/tasks/{task_id}
GET  /audit/evidence/{evidence_id}
POST /challenge/{evidence_id}
```

网络编排由 `docker compose` 或进程管理器提供。

公共 tabular 实验可以使用 read-only shared object store；敏感数据模式通过 `SecureExecutionProvider` 接口执行，节点收到 data capability，不直接接收可导出的明文数据。

---

# 18. 审计节点市场

节点 \(A_i\) 的实际参与私人成本为：

\[
\boxed{
c_i^{part}=k_i+\kappa_A B_{A,i}T_A
}
\]

其中：

- \(k_i\)：节点内部执行资源的私有成本，不含由协议统一核算的链、共享网络、BFT、challenge 和 dispute 资源成本；
- \(\kappa_AB_{A,i}T_A\)：质押资本机会成本。

节点唯一允许战略报告的 private type 是：

\[
b_i.
\]

capability、availability、stake 和历史 reliability 均由协议观测或认证得到，不由节点自行声明。

对候选动作 \(a_j\)，委员会分配：

\[
\mathbf x_j^*
=
\arg\min_{\mathbf x}\sum_i b_{ij}x_i
\]

满足委员会规模、capability、availability、minimum stake、异质性和安全约束。

被选节点的 Reverse VCG payment：

\[
\boxed{
p_{ij}^A=b_{ij}+C_{j,-i}^*-C_j^*}
\]

其中 \(C_{j,-i}^*\) 必须是删除 winner 后仍可行的精确最优解。若不存在替补委员会：

```text
COUNTERFACTUAL_INFEASIBLE
```

该 audit configuration 不可进入 VCG payment。

VCG truthfulness 的主实验只在单参数成本、准线性效用和公开可行集假设下声明。

---

# 19. Rational IC、Challenge 与质押

节点诚实效用：

\[
U_i^H=p_i^A-k_i-\kappa_AB_{A,i}T_A.
\]

定义 \(G_i^{dev}\) 为相对于诚实执行能够得到的全部额外收益，包括节省成本、贿赂和串谋收益。

若 challenge probability 为 \(\rho\)，强验证成功证明作恶概率为 \(p_{v,i}\)，slash fraction 为 \(\lambda_A\)：

\[
\rho p_{v,i}\lambda_AB_{A,i}
\ge
G_i^{dev}+\epsilon_A.
\]

最低 stake：

\[
\boxed{
B_{A,i}^{min}
=
\frac{G_i^{dev}+\epsilon_A}
{\rho p_{v,i}\lambda_A}
}
\]

\(\rho\)、\(p_{v,i}\)、\(G_i^{dev}\) 都必须解析来源。不存在全局默认 challenge rate。

---

# 20. BFT Safety 与 Offline Liveness

对于一个 certified profile 中给定的 Byzantine tolerance \(f\)：

\[
m=3f+1,\qquad q=2f+1.
\]

IID 大池近似下：

\[
K_B\sim Binomial(m,\eta_B),
\]

\[
P_{safe}=P(K_B\le f).
\]

在线诚实概率：

\[
p_H=(1-\eta_B)(1-\eta_O),
\]

\[
P_{live}=P(K_H\ge q).
\]

有限池使用 hypergeometric。correlated outage 和 correlated collusion 单独通过 simulator 评价，不用 IID 解析式强行拟合。

委员会规模不硬编码，允许由安全成本优化器求：

\[
\boxed{
\omega_{sec}^*
=
\arg\min_{m,q,\rho,B_A,\lambda_A}
ExpectedSecurityCost
}
\]

subject to：

\[
\underline p_B^{sys}\ge p_{target},
\quad
\overline p_{FP}^{sys}\le fp_{target},
\quad
P_{live}\ge l_{target},
\quad
DG_A\le0.
\]

目标阈值均由 experiment/contract config 明确提供。

---

# 21. Primitive Likelihood、Action Likelihood 与 Calibration

## 21.1 Primitive Likelihood

对 primitive \(p\)：

\[
\lambda_p^{prim}(o,x)=P(O_p=o\mid X=x,p).
\]

使用独立 calibration data 和受控注入估计。

## 21.2 Action-Level Likelihood

对分布式动作：

\[
a_j=(primitive,m,q,\rho,securityProfile,aggregationRule),
\]

\[
\boxed{
\Lambda_j(y,x)=P(Y_j=y\mid X=x,a_j).
}
\]

它包含节点故障、恶意报告、challenge 和 quorum 影响，不能直接等同于单节点 primitive accuracy。

## 21.3 Full Policy Detection

\[
\boxed{
p_B^{sys}(\Pi_A)
=P(System\ finally\ identifies\ SellerBreach\mid X=B,\Pi_A)}.
\]

完整 policy certification 使用独立数据，不允许用当前交易 ground truth 计算当前保证金。

---

# 22. Certified Audit Profile Cells

连续参数空间不能无证明地宣称求得真实 worst-case infimum。原型采用有限 certified cells：

\[
\Omega_c=\{\omega_1,\ldots,\omega_K\}.
\]

对 breach family \(h\)：

\[
p_{B,h,c}\sim Beta(a_D+TP_{h,c},b_D+FN_{h,c}).
\]

保守下界：

\[
\underline p_{B,h,c}
=Q_{\alpha_D}[p_{B,h,c}].
\]

合同同时保护多个 breach family 时：

\[
\boxed{
\underline p_B^{sys}
=
\min_{h\in\mathcal H_{contract}}
\underline p_{B,h,c}
}
\]

输入不属于任何认证 cell：

```text
PROFILE_OUT_OF_CERTIFIED_RANGE
```

---

# 23. 三状态先验

卖方 breach posterior：

\[
\theta_S\sim Beta(a_S,b_S),
\]

\[
\pi_B=E[\theta_S].
\]

利用交易前可见 metadata/context 建立 suitability prior：

\[
q_L=P(L\mid X\ne B,\mathcal C_b,PreTradeFeatures).
\]

于是：

\[
\boxed{
\pi_L=(1-\pi_B)q_L,
\qquad
\pi_G=(1-\pi_B)(1-q_L).
}
\]

禁止使用 realised utility 生成当前 \(q_L\)。

---

# 24. Bayes Risk 与 Audit-VOI

决策：

\[
d_Q\in\{ACCEPT,REJECT,TERMINATE\}.
\]

损失矩阵 \(\ell(d,x)\) 必须以统一 Currency Unit `[CU]` 表示。

\[
R(\boldsymbol\pi)
=
\min_{d_Q}\sum_x\pi_x\ell(d_Q,x).
\]

动作结果概率：

\[
P(y\mid\boldsymbol\pi,a_j)
=
\sum_x\Lambda_j(y,x)\pi_x.
\]

Bayes update：

\[
\pi'_x
=
\frac{\Lambda_j(y,x)\pi_x}
{\sum_{x'}\Lambda_j(y,x')\pi_{x'}}.
\]

期望后验风险：

\[
ER(a_j)
=
\sum_y P(y\mid\boldsymbol\pi,a_j)R(\boldsymbol\pi'^{(y)}).
\]

边际信息价值：

\[
\boxed{MV_A(a_j)=R(\boldsymbol\pi)-ER(a_j)}.
\]

---

# 25. 预期审计成本与实际审计支付

在选择下一审计动作时使用事前预期现金成本：

\[
\widehat{MC}_A^{pay}(a_j)
=
E[Payments+ChainFee+ChallengeCost+DisputeCost\mid a_j].
\]

Audit-VOI：

\[
\boxed{
VOI_A^{private}(a_j)
=
MV_A(a_j)-\widehat{MC}_A^{pay}(a_j)
}
\]

选择：

\[
a_{t+1}^*=\arg\max_{a_j}VOI_A^{private}(a_j).
\]

若：

\[
\max_jVOI_A^{private}(a_j)\le0,
\]

则 STOP。

交易定价、结算和效用只使用实际发生支付：

\[
C_A^{pay,realized}
=
\sum_t ActualPayment_t.
\]

每个动作带：

```text
payer: SELLER | BUYER
trigger: BASE_LISTING | BUYER_INCREMENTAL
```

从而得到 \(C_{A,S}^{pay}\) 和 \(C_{A,B}^{pay}\)。

---

# 26. Rights-Aware Data-VOI

买方已有数据为 \(D_b^{existing}\)，真实 marginal task utility：

\[
\Delta U_D^*
=
U(\theta_{D_b^{existing}\cup D})
-
U(\theta_{D_b^{existing}}).
\]

使用 cost-sensitive payoff matrix：

\[
R_b=
\begin{bmatrix}
r_{TN}&r_{FP}\\
r_{FN}&r_{TP}
\end{bmatrix}.
\]

\[
U_b(\theta)
=N_b\sum_{y,\hat y}P(y,\hat y;\theta)r_{y,\hat y}.
\]

同一数据被多个竞争主体获得可能降低私人竞争优势。定义当前 buyer-relevant market exposure：

\[
\nu_{b,t}=Exposure(D,R_\tau,b,t).
\]

竞争外部性损失：

\[
L_b^{comp}=L^{comp}(\nu_{b,t},R_\tau,\mathcal C_b).
\]

权利感知毛价值：

\[
\boxed{
V_{D,R}^{gross,*}
=
U_b(\theta_{base+D},R_\tau)
-U_b(\theta_{base},\varnothing)
-L_b^{comp}
}
\]

若某种数据没有竞争稀释效应，模型允许 \(L_b^{comp}=0\)，不得强制“销售次数越多价值越低”。

估值方法可包括 Oracle retraining、Forward Influence、KNN-Shapley、Data Shapley、Data Banzhaf、Data-OOB 和 LOO。

---

# 27. Secure Valuation

真实交易中不能假定买方在付款前已经获得完整明文数据。因此：

\[
SecureValuation(
H(D),BuyerModelSpec,ValuationSpec
)
\rightarrow
\widehat{\Delta U}_D.
\]

P0 public-data prototype 可以直接读取本地 committed dataset 完成算法验证；接口仍使用 `DataAccessHandle`。敏感数据 deployment 将 `DataAccessHandle` 解析到 Compute-Only、TEE 或 MPC provider。

Forward Influence 等不共享数据估值方法作为隐私估值 baseline。

---

# 28. Data-VOI 不确定性

估计毛价值：

\[
\hat V_{D,R}^{gross}=g_b(\widehat{\Delta U}_D;\mathcal C_b,R_\tau,\nu_{b,t}).
\]

保守下界：

\[
\underline V_{D,R}^{gross}
=Q_{\alpha_V}(V_{D,R}^{gross}\mid\mathcal I_V),
\]

或经过校准的正态近似。

价值 calibration 使用严格独立 residual：

\[
e_t=V_t^{real}-\hat V_t^{gross}.
\]

\[
\underline V_{t+1}^{gross}
=
\hat V_{t+1}^{gross}+Quantile_{\alpha_V}(\mathcal E_t).
\]

报告：

\[
Coverage_V=P(V^{real}\ge\underline V^{gross}).
\]

---

# 29. 数据复制成本与卖方机会成本

数据生产固定成本 \(F_D\) 与单笔复制/交付边际成本分开：

\[
F_D\neq c_{D,\tau}^{marg}.
\]

单笔交易不重复计入全部 \(F_D\)。

授予权利束的未来许可机会成本：

\[
\boxed{
OC_S(R_\tau)
=
E[Rev^{future}\mid\mathcal L_D]
-
E[Rev^{future}\mid\mathcal L_D\cup\{R_\tau\}]
}
\]

非排他授权可以使 \(OC_S\) 很小；独占或 capped license 可因放弃未来出售机会产生显著 \(OC_S\)。

生命周期经济性单独统计：

\[
\sum_{\tau\in\mathcal T_D}
(P_\tau-C_\tau^{marg})-F_D.
\]

---

# 30. Seller Bond

卖方偏离收益：

\[
G_S^{dev}
=C_{honest}-C_{deviation}+G_{external}.
\]

检测后 bond 自动执行概率为 \(p_{e,Bond}\)，链下额外处罚执行概率为 \(p_{e,F}\)。比用一个统一 \(p_e\) 更符合托管保证金与法律处罚不同的执行路径。

Seller IC：

\[
\underline p_B^{sys}
( p_{e,Bond}\lambda_SB_S+p_{e,F}F_S )
\ge
G_S^{dev}+\epsilon_S.
\]

最低保证金：

\[
\boxed{
B_S^*
=
\max\left\{
0,
\frac{
\frac{G_S^{dev}+\epsilon_S}{\underline p_B^{sys}}
-p_{e,F}F_S
}{p_{e,Bond}\lambda_S}
\right\}
}
\]

若任何分母关键参数为零或未解析，返回 `INFEASIBLE_SECURITY`。

---

# 31. Seller Bond Pre-Lock

为了让 audit-stage SELLER_BREACH 确实存在可罚没资金，在进入需要卖方责任覆盖的审计前：

\[
B_S^{pre}
=
\max_{\omega\in\Omega_{allowed}}B_S^*(\omega).
\]

卖方预锁：

\[
Seller\rightarrow Protocol:B_S^{pre}.
\]

审计完成后根据实际 certified profile 得到 \(B_S^*\)，释放差额。

资本成本使用资金时间积分：

\[
\boxed{
C_B^{cap}
=\kappa_S\int B_S(t)dt
}
\]

P0 分段实现：

\[
C_B^{cap}
=\kappa_S(
B_S^{pre}T_{pre}
+B_S^*T_{post}
).
\]

时间区间不得重叠计费。

卖方不能提供预锁资金属于 participation infeasible / NO_TRADE，不自动等于 Seller Breach。

---

# 32. Rights Registry 与重复出售约束

活跃许可集合：

\[
\mathcal L_D(t)=\{R_k:Active(R_k,t)=1\}.
\]

新权利授予前执行：

\[
Compatible(R_\tau,\mathcal L_D(t))=1.
\]

例如已有 exclusive license 与新的冲突授权不得同时存在。

权利 dominance：若 \(R_1\succeq R_2\)，即 \(R_1\) 包含 \(R_2\) 的所有许可，则同一 buyer、同一价格快照下应满足：

\[
P(R_1)\ge P(R_2).
\]

若 \(R\) 可以由一组较小权利组合获得，则无组合套利要求：

\[
P(R)\le\sum_iP(R_i).
\]

该约束作用于 rights menu generation，而不是强行把不同 buyer 的个性化价格排序到同一全局菜单。

---

# 33. 数据流向跟踪模型

系统维护 Data Flow Graph：

\[
G_F=(V_F,E_F).
\]

节点包括：

```text
DataAssetVersion
Actor
AuditRun
ValuationRun
UsageRun
DerivedArtifact
ExecutionEnvironment
```

边表示：

```text
READ
WRITE
DERIVE
TRANSFER
COMPUTE_ON
AUDIT
EXPORT
DELETE
REVOKE
```

每个事件：

\[
e_t=(eventID,txID,actor,action,inputRefs,outputRefs,rightsRef,purpose,time,env,evidence).
\]

采用 canonical JSON 序列化并建立哈希链：

\[
\boxed{
h_t=H(h_{t-1}\Vert Canonical(e_t))}
\]

从而检测日志删除、重排和篡改。

事件 schema 设计成可映射到 OpenLineage 的 RunEvent/DatasetEvent/JobEvent，但 VALOR 内部保留交易、rights 和 purpose 字段。

---

# 34. Usage Control State

每个已授予权利维护：

\[
U_\tau(t)=(n_t,t,purpose_t,actor_t,env_t,\varepsilon_t,revoked_t,retentionState).
\]

授权函数：

\[
Authorize(R_\tau,U_\tau,Request)=1
\]

当且仅当所有 applicable constraints 均满足，例如：

\[
t_0\le t\le t_1,
\]

\[
n_t<q,
\]

\[
purpose_t\in\Psi,
\]

\[
ActorAuthorized=1,
\]

\[
EnvironmentAllowed=1,
\]

\[
revoked_t=0,
\]

以及存在隐私预算时：

\[
\varepsilon_t+\varepsilon_{request}\le\varepsilon_{max}.
\]

使用成功：

\[
n_{t+1}=n_t+1.
\]

用途字段必须来自受控 vocabulary，不使用任意自由文本作为机器决策依据。

---

# 35. PDP / PEP / PIP / PXP

原型实现用途控制的四类组件：

- PDP：Policy Decision Point，执行 `Authorize`；
- PEP：Policy Enforcement Point，拦截 API、compute、export 请求；
- PIP：Policy Information Point，提供当前时间、使用次数、身份、环境、隐私预算等状态；
- PXP：Policy Execution Point，执行扣次数、更新 privacy budget、生成 receipt、触发删除等 duty。

其设计与 IDS usage control 的 policy enforcement 思路兼容。

---

# 36. 三种交付模式

## 36.1 DOWNLOAD_TRACEABLE

买方获得可用副本。系统无法可靠阻止离线复制，因此只声明：

\[
PreventionStrength<API/Compute.
\]

采取：

- recipient-specific fingerprint；
- delivery receipt；
- hash/version binding；
- contractual purpose constraints；
- leak tracing；
- Buyer Usage Liability。

## 36.2 API_GATEWAY

数据不整体下载，所有查询经过 PEP。可执行次数、时间、速率、操作集合和 output policy。

## 36.3 COMPUTE_ONLY

原始数据留在控制域，授权算法在受控环境运行，买方只获得允许输出。该模式适合高敏感度数据、估值和部分质量审计。

Rights Enforcement Mode 由经济优化器在权利可满足的候选集合中选择：

\[
\boxed{
e^*
=\arg\max_{e\in\mathcal E(R_\tau)}ExpectedSW(e)}
\]

subject to rights feasibility、privacy/security constraints。禁止默认所有交易都使用最强或最弱模式。

---

# 37. Usage Receipt

每次被允许的使用生成：

```text
UsageReceipt:
    receipt_id
    tx_id
    rights_hash
    asset_version_hash
    buyer_id
    executor_id
    requested_action
    declared_purpose
    algorithm_hash
    input_refs
    output_refs
    privacy_cost
    usage_count_before
    usage_count_after
    decision
    timestamp
    environment_attestation_ref
    prev_event_hash
    event_hash
    signature
```

`decision=DENY` 的请求也生成审计事件，从而观察超期、超次和异常用途尝试。

---

# 38. Buyer Misuse Detection 与责任

Buyer misuse 包括：

```text
USE_AFTER_EXPIRY
USAGE_COUNT_EXCEEDED
UNAUTHORIZED_PURPOSE
UNAUTHORIZED_REDISSEMINATION
SUBLICENSE_VIOLATION
EXPORT_BYPASS
DELETE_DUTY_VIOLATION
PRIVACY_BUDGET_EXCEEDED
```

对于 API/Compute mode，很多违规可在 PEP 前直接阻断；对于 Download，主要依靠事后 fingerprint/evidence。

系统误用检测保守概率：

\[
\underline p_U^{sys}.
\]

买方偏离收益 \(G_B^{misuse}\)，买方 usage bond \(B_B\)：

\[
\underline p_U^{sys}
(p_{e,UBond}\lambda_BB_B+p_{e,UF}F_B)
\ge
G_B^{misuse}+\epsilon_B.
\]

最低 usage bond：

\[
\boxed{
B_B^{use,*}
=
\max\left\{
0,
\frac{
\frac{G_B^{misuse}+\epsilon_B}{\underline p_U^{sys}}
-p_{e,UF}F_B
}{p_{e,UBond}\lambda_B}
\right\}
}
\]

该功能为可配置合同责任；不需要 usage bond 的场景可以通过显式合同参数令额外处罚/风险结构满足约束，而不是在代码中默认为零。

---

# 39. Buyer Maximum Willingness to Pay

Rights enforcement cash cost 为 \(C_R^{pay}\)，买方剩余风险为 \(R_B^{post}\)。

\[
\boxed{
P_\tau^{max}
=
\max\left\{
0,
\min\left[
W_B^{rem},
\underline V_{D,R}^{gross}
-C_I
-C_{A,B}^{pay}
-C_R^{pay}
-C_{B,use}^{cap}
-R_B^{post}
\right]
\right\}
}
\]

其中 Buyer Usage Bond 本金不扣除，只扣资本机会成本 \(C_{B,use}^{cap}\)。

---

# 40. Seller Minimum Acceptable Price

\[
\boxed{
P_\tau^{min}
=
c_{D,\tau}^{marg}
+C_{A,S}^{pay}
+C_B^{cap}
+C_{R,S}^{pay}
+R_S^{post}
+OC_S(R_\tau)
+\Pi_S^0
}
\]

固定数据生产成本 \(F_D\) 不在每笔交易重复加入。

---

# 41. Trade Margin 与成交价

\[
M_T=P_\tau^{max}-P_\tau^{min}.
\]

若：

\[
M_T<0,
\]

则：

\[
NO\_TRADE.
\]

若：

\[
M_T\ge0,
\]

则采用固定 bargaining rule：

\[
\boxed{
P_\tau^*
=P_\tau^{min}+\beta_{bar}M_T
}
\]

\(\beta_{bar}\) 是显式 contract input 或实验扫描变量，不在代码中赋默认值。

---

# 42. 资金账户

账户至少包括：

\[
E_S^A,E_B^A,E_B^P,B_S^{pre},B_S^*,B_B^{use},\{B_{A,i}\}.
\]

任意资金动作记为 double-entry ledger：

```text
from_account
to_account
amount
currency_unit
reason
state_before
state_after
```

每个 transaction 必须满足：

\[
\sum Inflow-\sum Outflow=0
\]

除非显式 burn/deadweight 账户被定义。

---

# 43. 终态与持续权利状态

交易终态：

\[
\mathcal S_T\in
\{TRADE,NO\_TRADE,SELLER\_BREACH,BUYER\_BREACH\}.
\]

`TRADE` 并不表示权利生命周期结束。Rights state 继续存在：

```text
ACTIVE
SUSPENDED
EXPIRED
REVOKED
CONSUMED
DELETION_PENDING
DELETED_ATTESTED
```

## TRADE

支付数据成交价，支付有效审计，调整/返还卖方 bond，激活 RightsBundle。

## NO_TRADE

不支付数据价；返还 purchase escrow；已经发生的基础审计由卖方审计托管支付，买方增量审计由买方审计托管支付；无违约时 seller bond 返回。

## SELLER_BREACH

停止数据价结算，买方 purchase escrow 退款，卖方 bond 依据可证明 breach 罚没，正确完成的审计仍支付。

## BUYER_BREACH

包括拒绝已触发责任、取消违约以及可证明的权利滥用。结算依据 breach type 执行取消成本、usage bond、补偿、rights revocation 等。

---

# 44. 私人效用与社会福利

买方：

\[
U_B
=V_{D,R}^{real}
-P_\tau^*
-C_I
-C_{A,B}^{pay}
-C_R^{pay}
-C_{B,use}^{cap}
-L_B^{real}.
\]

卖方：

\[
\Pi_S
=P_\tau^*
-c_D^{marg}
-C_{A,S}^{pay}
-C_B^{cap}
-C_{R,S}^{pay}
-OC_S^{real}
-Penalty_S^{real}.
\]

Auditor：

\[
U_{A,i}
=p_i^A-k_i-\kappa_AB_{A,i}T_A-Slash_i^{real}.
\]

社会资源成本严格拆分：

\[
C_{audit-service}^{res}=\sum_i k_i,
\]

\[
C_{protocol}^{res}
=C_{BFT}+C_{network}+C_{chain}+C_{challenge}+C_{dispute}+C_{lineage}+C_{usage-enforcement}.
\]

避免与 \(MC_A^{res}\) 重复计费。

完整福利：

\[
\boxed{
SW^{full}
=V^{real}
-C_D^{marg}
-C_I
-C_{audit-service}^{res}
-C_{protocol}^{res}
-C_B^{cap}
-C_{A,cap}
-C_{B,use}^{cap}
-ExpectedResidualLoss
}
\]

交易价、审计支付和可重新分配的罚没是内部转移，不在包含全部参与者的社会福利里重复扣除。

---

# 45. Feedback Ground-Truth Eligibility Gate

普通 PASS、TRADE 或 unchallenged report 不能自动作为 ground truth。

只有：

```text
ADJUDICATED_DISPUTE
STRONG_CHALLENGE
INDEPENDENT_FULL_AUDIT
CONTROLLED_CANARY
EXTERNAL_VERIFIED_GROUND_TRUTH
VERIFIED_LEAK_FINGERPRINT
```

等事件才能更新需要真实标签的 posterior。

因此：

\[
PASS\not\Rightarrow TN.
\]

并且：

\[
ExperimentalOracleFeedback
\neq
ProductionObservableFeedback.
\]

NO_TRADE 的数据在真实生产里通常没有 realised downstream value；实验 Oracle 可以计算，但不能让 production feedback 假装观察到。

---

# 46. Seller、Audit、Usage 与 Value Feedback

Seller breach：

\[
\theta_S\sim Beta(a_S,b_S).
\]

仅 ground-truth-eligible outcome 更新。

Primitive sensitivity：

\[
s_j\sim Beta(a_j^s,b_j^s),
\]

\[
s_j|D\sim Beta(a_j^s+TP_j,b_j^s+FN_j).
\]

False-positive：

\[
f_j|D\sim Beta(a_j^f+FP_j,b_j^f+TN_j).
\]

Auditor reliability：

\[
r_i|D\sim Beta(a_i^r+Correct_i,b_i^r+Incorrect_i).
\]

Usage enforcement：

\[
u_e|D\sim Beta(a_e^u+DetectedMisuse,b_e^u+MissedMisuse).
\]

所有 posterior 更新保存 evidence IDs。

---

# 47. Engineering Algorithm Q0：Reference Quality Reproduction

```text
Input:
    DatasetManifest
    QualityAlgorithmSpec
    ParameterManifest
    InjectionSpecSet
    ReferenceAdapter
    NativeImplementation

1. resolve all required parameters; fail closed on unresolved value
2. load immutable dataset version and verify hash
3. for each injection spec:
       build controlled case with ground truth
       execute reference implementation
       execute native implementation
       compare outputs by algorithm-specific equivalence rule
       compute ground-truth metrics
4. create QualityReproductionCertificate
5. if all required gates pass:
       publish algorithm to DistributedQualityCatalog
   else:
       distributed_enabled = false
6. return certificate and full artifacts
```

该算法属于工程前置条件，不改变论文 Audit-VOI 数学定义。

---

# 48. Engineering Algorithm Q1：Distributed Quality Audit Action

```text
Input:
    tau
    QualityAlgorithmSpec (must have valid reproduction certificate)
    ResolvedParameterManifest
    CommitteeSpec
    SecuritySpec
    AuditEscrow

1. verify transaction/data/rights commitments
2. verify algorithm reproduction certificate and code hash
3. run exact Reverse VCG allocation
4. verify counterfactual feasibility for every winner
5. verify expected payment <= available audit escrow
6. dispatch identical TaskEnvelope to committee nodes
7. nodes run isolated quality primitive and sign AuditEvidence
8. handle timeout/offline reassignment
9. form BFT certificate according to q/f rules
10. sample strong challenge according to resolved rho
11. slash only ProvableMalice evidence
12. aggregate action outcome y without equating minority report with malice
13. emit ActionAuditRecord + lineage events
14. return y, evidence, payments, resource costs
```

---

# 49. Algorithm 1：Rights-Bound Gross Data Valuation

```text
Input:
    tau
    DataAccessHandle
    BuyerContext
    RightsBundle
    MarketExposureState
    ValuationEstimatorSpec
    EconomicPayoffSpec
    ValueCalibrationState

1. verify commitments and entitlement/compliance status
2. execute estimator through SecureValuation interface
3. map marginal task utility to monetary gross value [CU]
4. account for rights scope and buyer-relevant market exposure
5. estimate valuation uncertainty
6. apply calibrated lower-bound procedure
7. emit ValuationRecord and lineage event
8. return V_hat_gross, V_lower_gross, uncertainty
```

---

# 50. Algorithm 2：VOI-Guided Distributed Quality Audit

```text
Input:
    tau
    initial belief pi_0
    CertifiedActionCatalog
    AuditorPool
    MonetaryLossMatrix
    AuditEscrowState

repeat:
    for each feasible certified action a_j:
        load action likelihood Lambda_j
        compute current Bayes risk R(pi)
        compute expected post-action risk ER(a_j)
        MV_A <- R(pi) - ER(a_j)
        estimate procurement payment by actual qualified market bids
        MC_hat_pay <- expected cash cost including challenge/dispute expectation
        VOI_j <- MV_A - MC_hat_pay

    if no feasible action or max_j VOI_j <= 0:
        STOP

    a_star <- argmax VOI_j
    execute Engineering Algorithm Q1
    observe certified outcome y
    pi <- BayesianUpdate(pi, Lambda_a_star, y)
    append AuditTrace

return:
    AuditPolicyTrace
    FinalAuditCertificate
    realized buyer/seller audit payments
    realized resource costs
    posterior pi
```

---

# 51. Algorithm 3：Liability and Rights-Aware Price Clearing

```text
Input:
    V_lower_gross
    certified pB_lower_sys
    seller enforcement parameters
    seller deviation gain bound
    realized audit payments by payer
    integration / marginal provision / rights enforcement costs
    seller bond capital-time record
    buyer residual risk
    seller residual liability
    license opportunity cost
    buyer remaining budget
    seller outside option
    bargaining weight
    optional usage-liability parameters

1. resolve and unit-check all parameters
2. compute B_S_star from Detect-and-Enforce IC
3. compute exact seller capital cost from bond-time intervals
4. if usage bond applicable, compute B_B_use_star and capital cost
5. compute P_max
6. compute P_min
7. TradeMargin <- P_max - P_min
8. if TradeMargin < 0: return NO_TRADE
9. P_star <- P_min + beta_bar * TradeMargin
10. verify rights-menu dominance/arbitrage constraints for same pricing snapshot
11. return bond, bounds, price, decision
```

---

# 52. Algorithm 4：Usage-Aware State Transition, Settlement and Feedback

```text
Input:
    tau
    audit certificate
    posterior
    price decision
    escrow/bond accounts
    RightsBundle
    DeliveryMode
    PolicyEnforcementSpec
    FeedbackState

1. verify object and rights bindings
2. if provable seller breach during audit:
       settle SELLER_BREACH from pre-locked bond
       goto FEEDBACK
3. if NO_TRADE:
       refund/settle incurred audits
       return seller pre-lock
       goto FEEDBACK
4. verify buyer purchase escrow and any usage bond
5. adjust seller pre-lock to required B_S_star
6. deliver or activate selected access mode
7. activate RightsBundle and UsageState
8. for each online usage request:
       PDP evaluates Authorize
       PEP allow/deny
       PXP updates counts/privacy budget/duties
       emit UsageReceipt and DataFlowEvent
9. if provable seller breach: settle SELLER_BREACH
10. if provable buyer misuse/default: revoke rights as applicable and settle BUYER_BREACH
11. on successful commercial settlement: transfer P_star and valid audit rewards
12. at expiry/consumption: transition RightsState
13. FEEDBACK only with GroundTruthEligibilityGate
14. compute utilities, welfare and friction
15. emit immutable settlement + lineage logs
```

---

# 53. 完整代码目录

```text
valor/
├── __init__.py
├── cli.py
├── core/
│   ├── enums.py
│   ├── money.py
│   ├── hashing.py
│   ├── canonical_json.py
│   ├── errors.py
│   └── ids.py
├── params/
│   ├── models.py                 # ResolvedParameter / manifests
│   ├── resolver.py               # fail-closed source resolution
│   ├── units.py
│   └── validators.py
├── asset/
│   ├── models.py                 # DataAsset / version
│   ├── manifest.py
│   ├── commitments.py
│   ├── entitlement.py
│   └── compliance.py
├── rights/
│   ├── models.py                 # RightsBundle / RightsState
│   ├── odrl_profile.py
│   ├── registry.py
│   ├── compatibility.py
│   ├── dominance.py
│   └── opportunity_cost.py
├── data/
│   ├── download.py
│   ├── preprocess.py
│   ├── split_roles.py
│   ├── transaction_batches.py
│   ├── injection.py
│   └── ground_truth.py
├── quality/
│   ├── models.py                 # QualityAlgorithmSpec / Evidence
│   ├── catalog.py
│   ├── reproduction.py
│   ├── equivalence.py
│   ├── evidence.py
│   ├── reference/
│   │   ├── deequ_adapter.py
│   │   ├── cleanlab_adapter.py
│   │   └── scipy_stats_adapter.py
│   ├── native/
│   │   ├── structural.py
│   │   ├── duplicates.py
│   │   ├── confident_learning.py
│   │   ├── ks_shift.py
│   │   ├── categorical_shift.py
│   │   ├── mmd.py
│   │   └── metadata_claims.py
│   └── calibration/
│       ├── primitive.py
│       ├── action.py
│       └── metrics.py
├── distributed/
│   ├── task_models.py
│   ├── scheduler.py
│   ├── client.py
│   ├── executor.py
│   ├── node_server.py
│   ├── node_state.py
│   └── docker_runtime.py
├── market/
│   ├── bidder.py
│   ├── committee_allocation.py
│   ├── reverse_vcg.py
│   ├── payments.py
│   └── escrow_guard.py
├── security/
│   ├── bft.py
│   ├── liveness.py
│   ├── challenge.py
│   ├── slashing.py
│   ├── attacks.py
│   └── certification.py
├── audit/
│   ├── state_model.py
│   ├── likelihood.py
│   ├── bayes_update.py
│   ├── loss.py
│   ├── voi.py
│   ├── action_catalog.py
│   ├── policy.py
│   └── trace.py
├── valuation/
│   ├── estimator_protocol.py
│   ├── oracle.py
│   ├── forward_influence.py
│   ├── knn_shapley.py
│   ├── data_shapley.py
│   ├── data_banzhaf.py
│   ├── data_oob.py
│   ├── loo.py
│   ├── economic_mapping.py
│   ├── exposure.py
│   └── calibration.py
├── liability/
│   ├── seller_bond.py
│   ├── seller_prelock.py
│   ├── buyer_usage_bond.py
│   └── capital_cost.py
├── pricing/
│   ├── buyer_max.py
│   ├── seller_min.py
│   ├── clearing.py
│   ├── rights_menu.py
│   └── lifecycle.py
├── execution/
│   ├── access_handle.py
│   ├── delivery.py
│   ├── download_traceable.py
│   ├── api_gateway.py
│   ├── compute_only.py
│   └── secure_valuation.py
├── usage/
│   ├── models.py
│   ├── pdp.py
│   ├── pep.py
│   ├── pip.py
│   ├── pxp.py
│   ├── receipt.py
│   ├── privacy_budget.py
│   ├── fingerprint.py
│   └── misuse.py
├── lineage/
│   ├── models.py
│   ├── graph.py
│   ├── hash_chain.py
│   ├── openlineage_adapter.py
│   └── query.py
├── contract/
│   ├── accounts.py
│   ├── escrow.py
│   ├── state_machine.py
│   └── settlement.py
├── feedback/
│   ├── eligibility.py
│   ├── seller_risk.py
│   ├── audit_performance.py
│   ├── auditor_reliability.py
│   ├── usage_performance.py
│   └── value_calibration.py
├── evaluation/
│   ├── metrics.py
│   ├── utilities.py
│   ├── welfare.py
│   ├── statistics.py
│   ├── matched_security.py
│   ├── oracle_trade.py
│   └── report_schema.py
├── simulation/
│   ├── actors.py
│   ├── network.py
│   ├── transaction.py
│   └── scenarios.py
├── plotting/
├── report.py
└── run.py

tests/
├── unit/
├── property/
├── reproduction/
├── distributed/
├── integration/
├── attacks/
└── e2e/

configs/
├── schemas/
├── datasets/
├── quality/
├── economics/
├── security/
├── rights/
└── experiments/

scripts/
├── run-quality-reference.sh
├── run-distributed-audit.sh
├── run-transaction.sh
└── run-experiments.sh
```

---

# 54. 核心类型接口

## 54.1 Parameter

```python
@dataclass(frozen=True)
class ResolvedParameter[T]:
    name: str
    value: T
    unit: str
    source_kind: ParamSource
    source_ref: str
    version_hash: str
```

不得给 `value` 设置业务默认值。

## 54.2 QualityAlgorithmSpec

```python
@dataclass(frozen=True)
class QualityAlgorithmSpec:
    algorithm_id: str
    family: str
    implementation_kind: str
    code_hash: str
    runtime_image_hash: str
    input_schema_hash: str
    output_schema_hash: str
    required_parameter_names: tuple[str, ...]
    migration_class: str
```

## 54.3 AuditPolicySpec 与 AuditTrace

认证对象必须是 rule：

```python
class AuditPolicySpec:
    policy_id: str
    action_catalog_hash: str
    decision_rule_hash: str
    certified_cell_id: str
```

某笔交易实际产生：

```python
class AuditTrace:
    tx_id: str
    steps: list[AuditStep]
```

禁止使用交易结束后的 trace 作为事前 policy certification hash。

## 54.4 RightsBundle

核心字段均 required；不适用字段使用显式 `None + not_applicable_reason`，而不是隐式 default。

## 54.5 UsageReceipt

receipt 必须可 canonicalize、hash 和签名。

---

# 55. 数据四角色划分

逻辑上必须满足：

\[
BaseTrain\cap SellerPool\cap ValuationValidation\cap FinalEvaluation=\varnothing.
\]

- BaseTrain：买方已有训练信息；
- SellerPool：候选 seller batches；
- ValuationValidation：估值器允许使用的 reference/evaluation-gradient data；
- FinalEvaluation：只用于 Oracle realised utility 和最终实验评价。

Quality calibration/certification 数据还应与最终 RQ evaluation 分离。

---

# 56. Candidate Seller Batch

RQ1 的交易单位为：

\[
D_k=CandidateSellerBatch_k.
\]

不把每一行默认视作一笔市场交易。

provider/batch-level Shapley 优先直接把 batch 当 player；天然 point-level 方法才允许聚合：

\[
Score(D_k)=\sum_{z_i\in D_k}v_i.
\]

主质量实验和 scalability experiment 的 batch 数量由 experiment config 显式提供。

---

# 57. Experiment RQ1：Data-VOI

比较：

```text
Random
Similarity
LOO
TMC/Data Shapley
Beta-Shapley
Data Banzhaf
Data-OOB
Forward Influence
KNN-Shapley
Exact Retraining Oracle
```

指标：

```text
Spearman
Kendall tau
MAE
RMSE
Top-k regret
Coverage_V
runtime
communication overhead
```

所有 baseline 使用相同 candidate batches、buyer context 和随机种子。

---

# 58. Experiment RQ2：质量验证已有算法是否被正确复现

这是实现可信度实验，不宣称 VALOR 发明新的质量算法。

比较：

```text
Reference implementation
Native reproduction
Injected ground truth
```

分别报告：

- structural metrics exact agreement；
- label issue precision/recall/ranking agreement；
- KS/MMD statistic agreement；
- runtime / memory；
- 不同污染强度下的 detection curve。

核心结论只允许是“参考语义能否在统一 VALOR primitive interface 中被忠实执行”。

---

# 59. Experiment RQ3：质量算法迁移到分布式节点后是否保持语义

比较：

```text
Single-node native primitive
Distributed honest committee
Distributed + offline
Distributed + Byzantine reports
Distributed + collusion
Distributed + challenge/stake/BFT
```

对于没有攻击的委员会，验证：

\[
Output_{distributed}=Output_{single}
\]

在算法允许的数值误差规则下成立。

同时报告：

```text
SemanticAgreement
CorrectCertificateRate
FalseCertificateRate
P_safe
P_live
AuditLatency
CommunicationBytes
ReassignmentCount
ChallengeCost
```

这一步回答“已有质量验证是否能迁移到不可信分布式节点执行”，而不是重新比较数据质量算法优劣。

---

# 60. Experiment RQ4：Audit-VOI

Baselines：

```text
No Audit
Full Audit
Fixed-rate Audit
Random Audit
Static Threshold
Bayesian EVSI without market cost
VALOR Audit-VOI + actual procurement market
```

\[
NetAuditGain=AvoidedDecisionLoss-C_A^{pay}.
\]

在 matched decision-risk 和 matched budget 下比较。

---

# 61. Experiment RQ5：节点安全与采购激励

分别验证：

### Procurement truthfulness

固定其他 bids，对 \(b_i\) 扫描，验证在单参数假设下：

\[
b_i=c_i^{part}
\]

最大化 auditor procurement utility。

### Execution IC

\[
DG_A
=U_A^{best\ deviation}-U_A^{honest}.
\]

在理论 IC region 内要求 \(DG_A\le0\)，区域外允许观察 \(DG_A>0\)。

### BFT/Liveness

IID 场景与解析概率比较；correlated failure 单独实验。

---

# 62. Experiment RQ6：Detection → Seller Bond

固定 seller deviation gain，改变 certified audit/security profile：

\[
\underline p_B^{sys}\uparrow
\Rightarrow
B_S^*\downarrow.
\]

报告：

```text
pB_LCB
B_S_star
B_S_pre
C_B_cap
C_A_pay
C_A_pay + C_B_cap
DG_S
```

---

# 63. Experiment RQ7：Rights-Aware Pricing 与重复出售

改变：

```text
exclusivity
license cap
market exposure
rights duration
usage quota
redistribution right
```

验证：

- fixed production cost 不被每笔重复扣除；
- exclusive rights 的 opportunity cost 能进入 seller minimum；
- 无竞争外部性时 sales count 不应机械压低 buyer value；
- 有竞争外部性时 market exposure 对 private buyer value 的影响可被识别；
- rights dominance / bundle arbitrage constraints 成立。

---

# 64. Experiment RQ8：Usage Control 与 Data Flow Audit

比较：

```text
DOWNLOAD without fingerprint
DOWNLOAD_TRACEABLE
API_GATEWAY
COMPUTE_ONLY
```

攻击：

```text
expired access
count overflow
wrong purpose
unauthorized export
credential sharing
redistribution
privacy budget overrun
delete-duty violation
```

指标：

```text
PreventedMisuseRate
DetectedMisuseRate
AttributionRate
FalseDenialRate
UsageControlLatency
RightsEnforcementCost
ResidualMisuseLoss
LineageCompleteness
ReceiptVerificationRate
```

对于 DOWNLOAD，明确区分“阻止率”和“事后归因率”。

---

# 65. Experiment RQ9：End-to-End Welfare / NO_TRADE

Baselines：

```text
Always Trade
Value-only Trade
NoAudit + FixedBond
FullAudit + LowBond
FixedAudit + RiskBond
AuditVOI + AdaptiveBond
Full without Usage Control
Full VALOR
```

共同 security constraints 下比较：

\[
\min TCF\quad s.t.\quad SecurityConstraints.
\]

NO_TRADE Oracle：

\[
Y^{oracle}=\mathbf1[P_{max}^{oracle}\ge P_{min}^{oracle}].
\]

报告 precision/recall、false trade/reject 和 welfare regret。

---

# 66. 统计规范

所有 baseline 共享：

```text
dataset
buyer context
candidate batches
corruption seed
node population
attack seed
rights snapshot
```

连续指标：mean/median + 95% CI；比例指标：Beta credible interval 或 Wilson interval；paired difference 近似正态时 paired t-test，否则 Wilcoxon signed-rank；effect size 使用 Cohen's d 或 Cliff's delta；多 baseline 使用 Holm correction。

顺序 Audit-VOI 主结果使用独立 calibration/evaluation split；如开展连续在线统计，则使用 anytime-valid inference / confidence sequences 等专门方法。

---

# 67. Certification Sample Size

系统检测率不能用任意固定样本数认证。

若先验：

\[
p_B^{sys}\sim Beta(a_D,b_D),
\]

认证目标为：

\[
Q_{\alpha_D}[Beta(a_D+TP,b_D+FN)]\ge p_{target}.
\]

`certification.py` 必须根据 \((a_D,b_D,\alpha_D,p_{target},FN_{allow})\) 搜索满足条件的最小样本数，生成 `CertificationPlan`。

FPR 和 liveness 也分别按照其目标 confidence criterion 规划样本量/Monte Carlo repetitions。

---

# 68. 日志最小字段

```yaml
transaction:
  tx_id:
  asset_id:
  asset_version:
  data_hash:
  metadata_hash:
  rights_hash:
  seller_id:
  buyer_id:

parameters:
  manifest_hash:
  unresolved_count:
  source_summary:

quality_reference:
  algorithm_id:
  reproduction_certificate_id:
  reference_version:
  native_code_hash:

valuation:
  estimator_id:
  utility_hat:
  gross_value_hat:
  gross_value_lower:
  uncertainty:
  realised_value_if_observable:

quality_audit:
  action_ids:
  primitive_ids:
  raw_metrics:
  posterior_history:
  evidence_ids:
  committee_members:
  bids:
  payments_expected:
  payments_realized:

security:
  profile_cell_id:
  byzantine_ratio:
  offline_ratio:
  challenge_probability:
  p_safe_analytic:
  p_live_analytic:
  p_breach_lower:
  p_false_positive_upper:
  slashed_nodes:

liability:
  seller_deviation_gain:
  seller_bond_pre:
  seller_bond_required:
  seller_bond_capital_cost:
  buyer_usage_bond:

pricing:
  buyer_max:
  seller_min:
  trade_margin:
  clearing_price:

usage:
  delivery_mode:
  rights_state:
  usage_count:
  privacy_budget_used:
  receipts:
  denied_requests:
  misuse_evidence:

lineage:
  graph_root_hash:
  event_count:
  last_event_hash:

settlement:
  terminal_state:
  account_transfers:
  rights_transition:

evaluation:
  buyer_utility:
  seller_profit:
  auditor_utility:
  social_welfare:
  transaction_friction:
  oracle_decision:
  welfare_regret:
```

---

# 69. 工程 Gate

## Gate A — Parameter Provenance

- 核心算法不存在业务默认值；
- RequiredParameter 全部可解析；
- unit checker 通过；
- config hash 可复现。

## Gate B — Quality Reference

- 每个 distributed-enabled primitive 有 reproduction certificate；
- deterministic primitive 与 reference 完全一致；
- stochastic primitive 的 equivalence rule 有统计证据；
- injection ground truth 可重建。

## Gate C — Distributed Semantic Preservation

- honest committee 与 single-node 语义一致；
- task/evidence/data/algorithm commitment 全部校验；
- node 是独立 process/container；
- offline reassignment 可运行。

## Gate D — Audit Market

- exact allocation；
- AllocationOptimalityGap=0；
- counterfactual feasible；
- payment 不超过 escrow；
- truthfulness test 与 execution IC test 分离。

## Gate E — Security Certification

- primitive/action/full-policy 三层 likelihood 分离；
- current transaction 不读取未来 ground truth；
- input 落在 certified cell；
- FPR、detection、liveness 都有 uncertainty bound。

## Gate F — Liability and Accounting

- seller pre-lock 发生在可罚没 audit 之前；
- bond capital cost 使用时间区间；
- principal 与 capital cost 分离；
- social welfare 不重复扣内部 transfer。

## Gate G — Rights and Repeat Sale

- rights compatibility；
- fixed cost / marginal cost 分离；
- opportunity cost 可计算；
- dominance / arbitrage check 可运行。

## Gate H — Usage / Lineage

- every online use passes PEP/PDP；
- count/time/purpose/privacy constraints 可测试；
- every decision emits receipt；
- lineage hash chain 可验证；
- tamper/delete/reorder 能被检测；
- Download 模式不虚假声称技术上可阻止所有离线滥用。

## Gate I — State Machine

- TRADE/NO_TRADE/SELLER_BREACH/BUYER_BREACH 全路径有测试；
- 资金守恒；
- rights state 和 transaction state 相互一致；
- feedback 只接收 eligible evidence。

---

# 70. 本地 Agent 开发阶段

以下阶段按依赖关系执行。每一阶段只有 Gate 通过才能进入下一阶段。

## Phase 0 — Repository / Types / Parameter Governance

交付：

```text
pyproject.toml
valor/core
valor/params
valor/asset
valor/rights
configs/schemas
tests/unit/test_parameter_fail_closed.py
```

验收：空业务配置不能运行 transaction；所有核心 dataclass 可序列化、canonicalize、hash。

## Phase 1 — Data Pipeline + Quality Reference Reproduction

交付：

```text
quality/reference/*
quality/native/*
quality/reproduction.py
data/injection.py
tests/reproduction/*
reports/quality_reproduction/*.json
```

执行顺序：

1. structural/Deequ semantics；
2. exact duplicate；
3. Confident Learning；
4. KS/category shift；
5. MMD；
6. metadata claims。

在任何算法进入 distributed catalog 前完成 Gate B。

## Phase 2 — Real Distributed Quality Nodes

交付：

```text
distributed/node_server.py
distributed/executor.py
docker-compose.yml
market/*
security/bft.py
security/liveness.py
```

至少启动多个独立 auditor 服务，并完成一个 committed dataset 上的真实 HTTP 审计任务。

## Phase 3 — Audit Calibration + Audit-VOI

交付：

```text
quality/calibration/*
audit/*
security/certification.py
```

完成 primitive likelihood、action likelihood、policy certification、Bayes update、VOI stop。

## Phase 4 — Data-VOI

交付：

```text
valuation/*
evaluation/oracle.py
```

实现 batch-level exact retraining oracle 和论文 baseline；保持四角色数据划分。

## Phase 5 — Liability + Pricing + Escrow

交付：

```text
liability/*
pricing/*
contract/accounts.py
contract/escrow.py
```

完成 seller bond/pre-lock、buyer max/seller min、NO_TRADE、clearing price、重复出售经济性。

## Phase 6 — Data Flow / Usage Control

交付：

```text
lineage/*
usage/*
execution/api_gateway.py
execution/compute_only.py
execution/download_traceable.py
```

必须实现真实 event hash chain、PDP/PEP、UsageReceipt 和至少一套 recipient-specific fingerprint provider 的可运行接口/方案。

## Phase 7 — Full State Machine + Feedback

交付：

```text
contract/state_machine.py
contract/settlement.py
feedback/*
```

覆盖四终态、持续 RightsState、GroundTruthEligibilityGate。

## Phase 8 — Experiments / Reports

交付：

```text
evaluation/*
plotting/*
report.py
run.py
scripts/run-experiments.sh
```

一键生成 raw JSON、summary parquet/csv、Markdown report 和 figures。

---

# 71. CLI Contract

```bash
python -m valor quality reproduce --config <required-path>
python -m valor quality certify --config <required-path>
python -m valor node serve --config <required-path>
python -m valor audit run --config <required-path>
python -m valor valuation run --config <required-path>
python -m valor transaction run --config <required-path>
python -m valor experiment run --config <required-path>
python -m valor report build --run-dir <required-path>
```

除 `--help` 和 `--version` 外，需要业务参数的 CLI 不接受省略 `--config`。

---

# 72. 依赖与技术选择

Python 原型：

```text
numpy
pandas
scipy
scikit-learn
torch
cleanlab
pydantic
fastapi
uvicorn
httpx
cryptography
networkx
matplotlib
pyarrow (需要 parquet 时)
```

Deequ reference reproduction 可以通过独立 Spark/Deequ 环境运行，结果通过 JSON artifact 接入 Python 主工程；这样不要求主包把 JVM 作为运行时硬依赖。

`scipy.optimize.milp` 或等价 exact MILP solver 用于 VCG allocation。若 solver 返回非零 optimality gap 或未证明 optimal，则 truthfulness experiment 不通过。

---

# 73. 不允许的实现捷径

以下实现视为设计违规：

1. 用 `0.05`、`7 nodes`、`10% challenge` 等代码常量代替 experiment/contract/calibration 参数；
2. 用随机生成的 `p_B^{sys}` 代替 certification；
3. 用当前 transaction ground truth 计算当前 bond；
4. 用单节点算法 accuracy 直接当 system detection；
5. 用 committee majority 自动当真实质量标签；
6. 把 minority report 自动 slash；
7. 用训练内 prediction probability 做 Confident Learning 主结果；
8. 用一个任意加权 QualityScore 取代可解释质量向量；
9. 把固定数据生产成本在每笔复制出售中重复扣除；
10. 把 bond principal 当社会成本；
11. 在 Social Welfare 中再次扣 transaction price 或 auditor payment；
12. 声称 Download 模式可以技术上阻止所有离线复制；
13. 把 PASS/TRADE 自动写成 TN/ground truth；
14. 在同一 final holdout 上既调参/calibrate 又报告最终效果；
15. 用同一进程中的函数循环冒充分布式 auditor node；
16. VCG 使用 heuristic allocation 却继续声明标准 truthfulness；
17. 未绑定 code/data/parameter hash 的审计结果进入证书。

---

# 74. Prototype Definition of Done

满足以下条件时，代码层面覆盖论文全部核心运算逻辑：

\[
\boxed{
DoD=
A\land B\land C\land D\land E\land F\land G\land H\land I
}
\]

其中：

A. 真实公开 tabular dataset 可以下载、分割、commit 和生成 candidate seller batches；  
B. 已有质量算法可以在单节点参考层复现并生成证书；  
C. 至少多个独立 auditor 服务可执行相同 quality primitive，并在故障/攻击下形成可验证 action certificate；  
D. Audit-VOI 能以 calibrated action likelihood 和实际市场成本选择/停止审计；  
E. Data-VOI 和完整重训练 Oracle 可运行，输出货币化 value lower bound；  
F. certified detection 能计算 seller bond、pre-lock、buyer/seller price bounds 和 clearing price；  
G. repeat-sale / rights constraints 能进入 opportunity cost、market exposure 和 rights menu；  
H. API/Compute usage 可以实时 enforcement，Download 可以生成 traceable delivery evidence；  
I. 四终态、资金守恒、lineage、feedback 和全部 RQ experiment 可一键运行。

---

# 75. 研究与实践映射

质量验证基础：

- Sebastian Schelter et al., **DEEQU - Data quality validation for machine learning pipelines**, NeurIPS 2018. Deequ 使用声明式方式表达数据假设并对大规模数据执行自动验证。
- Sebastian Schelter et al., **Differential data quality verification for partitioned data**, ICDE 2019. 该工作通过 algebraic states/monoid 性质支持分区数据的增量质量验证，为 mergeable primitives 的分布式实现提供直接启发。
- Curtis G. Northcutt, Lu Jiang, Isaac L. Chuang, **Confident Learning: Estimating Uncertainty in Dataset Labels**, JAIR 2021. 用于标签错误估计和 issue ranking。
- TableShift 可作为真实 tabular distribution shift 的外部验证数据源之一；VALOR 的质量层不依赖它作为唯一数据源。

数据价值：

- Xinlei Xu, Awni Hannun, Laurens van der Maaten, **Data Appraisal Without Data Sharing**, AISTATS 2022. Forward Influence 与不共享数据的 appraisal 为 SecureValuation 提供基线。
- Kevin Jiang et al., **OpenDataVal**, NeurIPS 2023. 提供统一 data valuation benchmark 和多种算法实现。
- Jiachen T. Wang, Ruoxi Jia, **Data Banzhaf**, AISTATS 2023. 提供数据估值稳定性与 MSR 估计方法。

权利与用途：

- W3C **ODRL Information Model 2.2 / Vocabulary 2.2**：Permission、Prohibition、Duty、count、datetime、device 等机器可读使用约束。
- International Data Spaces Reference Architecture：Usage Control 的 PDP/PEP 等 enforcement 思路，将 access control 与 post-access usage restrictions 区分。
- OpenLineage：以 RunEvent、DatasetEvent、JobEvent 记录数据处理 lineage 的开放事件模型。
- Ocean Protocol Compute-to-Data：数据留在数据持有者环境，只允许授权算法在隔离环境运行，为 SecureValuation/Compute-Only 提供实际架构参考。
- Tianxi Ji et al., **Privacy-Preserving Database Fingerprinting**：关系数据库共享中的隐私保护与 recipient-specific liability/traceability。

---

# 76. 主要参考链接

1. Deequ, Amazon Science: https://www.amazon.science/publications/deequ-data-quality-validation-for-machine-learning-pipelines
2. Differential data quality verification for partitioned data: https://www.amazon.science/publications/differential-data-quality-verification-for-partitioned-data
3. Confident Learning: https://research.google/pubs/confident-learning-estimating-uncertainty-in-dataset-labels/
4. Data Appraisal Without Data Sharing: https://proceedings.mlr.press/v151/xu22e.html
5. OpenDataVal: https://proceedings.neurips.cc/paper_files/paper/2023/hash/5b047c7d862059a5df623c1ce2982fca-Abstract-Datasets_and_Benchmarks.html
6. Data Banzhaf: https://proceedings.mlr.press/v206/wang23e.html
7. W3C ODRL Information Model: https://www.w3.org/TR/odrl-model/
8. W3C ODRL Vocabulary: https://www.w3.org/TR/odrl-vocab/
9. IDS Policy Enforcement: https://docs.internationaldataspaces.org/ids-knowledgebase/ids-ram-4/layers-of-the-reference-architecture-model/3-layers-of-the-reference-architecture-model/3_4_process_layer/3_4_6_policy_enforcement
10. IDS Usage Control: https://docs.internationaldataspaces.org/ids-knowledgebase/ids-ram-4/perspectives-of-the-reference-architecture-model/4_perspectives/4_1_security_perspective/4_1_6_usage_control
11. OpenLineage API: https://openlineage.io/apidocs/openapi/
12. Ocean Compute-to-Data: https://docs.oceanprotocol.com/developers/compute-to-data
13. Privacy-Preserving Database Fingerprinting: https://arxiv.org/abs/2109.02768

---

# 77. 总纲

\[
\boxed{
\begin{aligned}
&SellerEntitlement+RightsBundle\\
&\Downarrow\\
&ReferenceQualityAlgorithms\\
&\Downarrow\\
&DistributedQualityEvidence\\
&\Downarrow\\
&BuyerSpecificRightsAwareDataVOI\\
&\Downarrow\\
&BayesianAuditVOI+AuditMarket\\
&\Downarrow\\
&CertifiedDetection+SellerLiability\\
&\Downarrow\\
&RepeatSaleEconomics+RightsAwarePricing\\
&\Downarrow\\
&UsageControl+DataFlowAudit\\
&\Downarrow\\
&Trade/NoTrade/SellerBreach/BuyerBreach\\
&\Downarrow\\
&GroundTruthEligibleFeedback
\end{aligned}
}
\]

质量算法的正确性先由已有研究和 reference implementation 建立；分布式节点机制只改变执行信任模型，不偷换质量算法定义。Data-VOI 与 Audit-VOI 仍是经济决策主线，质量验证提供可解释证据，审计市场发现验证服务成本，系统检测能力决定卖方责任资本，权利束和可复制性进入买卖双方价格边界，数据流向与用途控制把成交后的真实使用行为继续连接到 BUYER_BREACH、责任和反馈。所有无法由数据、校准、合同、市场、优化器或威胁模型解析的参数都被拒绝进入核心计算，从而使论文中的每一条公式、每一个状态和每一个实验变量在代码层面均有明确来源、可复现输入和可审计输出。
