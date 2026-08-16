# VALOR 设计决策记录（DESIGN_DECISIONS）

> 唯一 normative source：`VALOR_可实施原型系统_完整数学代码闭环与开发规范.md`。
> 记录实现过程中相对规范的取舍、澄清与对照。每个决策给出规范依据与影响。
> 编号从 D100 起续接（历史 D1–D20 属旧规范，已随旧实现移除，不再沿用）。

## Phase 0 决策

### D100 参数溯源模型采用「类型化 ResolvedParameter + require_resolved()」
- **规范依据**：§5 参数来源治理（ResolvedParameter / source_kind / ResolveAll fail-closed）、§73 第 1 条。
- **决策**：`valor/params/resolver.py` 提供 `require_resolved(name)`，任何未解析/来源不明的参数直接抛 `UNRESOLVED_PARAMETER`；禁止 `config.get("alpha", 0.05)` 式默认值。业务参数无默认值（`dataclass` 字段 `required`，无 default）。
- **影响**：所有后续 Phase 的核心函数必须显式传 `ResolvedParameter`，保证可复现、可审计。

### D101 核心 dataclass 统一实现 `canonicalize()` / `content_hash()` 接口
- **规范依据**：§4 对象绑定（H(D), H(M_D), H(R_τ)）、§54.5（receipt 可 canonicalize/hash/签名）、Phase 0 验收（dataclass 可序列化/canonicalize/hash）。
- **决策**：在 `valor/core/canonical_json.py` 定义确定性 canonical 序列化（sorted keys、ensure_ascii、无多余空白）；在 `valor/core/hashing.py` 提供 `content_hash()`（SHA-256）。各核心 dataclass 复用该接口，保证跨平台哈希一致。
- **影响**：承诺/绑定（commitments）与证书可复现。

### D102 货币统一用 [CU] 标量 + unit 字段，不引入自定义 Money 类
- **规范依据**：§12/§24/§25 统一 Currency Unit `[CU]`；§5.2 参数带 unit。
- **决策**：`valor/core/money.py` 定义 `CURRENCY_UNIT` 常量与 `assert_unit()` 单位校验；经济量以浮点标量 + unit 表示，避免在核心计算中引入对象开销，同时保证单位可检查。
- **影响**：单位不一致在赋值处即抛 `UNIT_MISMATCH`。

### D103 三状态枚举与终态枚举集中定义于 valor/core/enums.py
- **规范依据**：§8 X∈{G,L,B}；§43 终态 S_T∈{TRADE,NO_TRADE,SELLER_BREACH,BUYER_BREACH}；§63 持续 RightsState。
- **决策**：定义 `TradeState`(G/L/B)、`TerminalState`、`RightsState`、`DeliveryMode`、`ParamSource`、`QualityImplementationKind`、`MigrationClass` 等枚举。
- **影响**：全项目共享，避免字符串魔法值，便于契约校验。

### D104 RightsBundle 字段全部 required，不适用字段用显式 None + reason
- **规范依据**：§54.4（核心字段均 required；不适用用 `None + not_applicable_reason`，不用隐式 default）。
- **决策**：`RightsBundle` 用 dataclass，可选语义字段（如差分隐私预算）为 `Optional` 并配合 `not_applicable_reason`。
- **影响**：避免"值为空却被当作有值"的隐式默认。

### D105 Phase 0 不引入重依赖，仅用 stdlib + pydantic（可选）
- **规范依据**：§72 依赖清单（pydantic 在列）。
- **决策**：Phase 0 的 core/params/asset/rights 用标准库 `dataclasses`/`hashlib`/`json` 实现，不强制 pydantic 运行时依赖（pyproject 声明其为依赖，后续 Phase 需要时使用）。
- **影响**：降低 Phase 0 启动成本，核心逻辑可独立单测。

### D106 configs 采用 JSON + JSON Schema（configs/schemas/）双重校验
- **规范依据**：§53 配置目录含 `schemas/`；§5 fail-closed。
- **决策**：提供 JSON Schema 文件（draft-07）校验配置结构；运行时再用类型化 loader 校验单位与来源。空业务配置（缺必需参数）在加载时即抛错，无法进入 transaction。
- **影响**：满足 Phase 0 验收「空业务配置不能运行 transaction」。

## Phase 0 强化决策（验收检查单 A–U）

### D107 类型化 ID 系统（检查单 E）
- 定义 `ValorID` 基类 + `AssetID/VersionID/TransactionID/SellerID/BuyerID/AuditorID/PolicyID/CalibrationID/RightsID/EventID`。
- 随机 ID 用 `secrets.token_hex`，内容寻址 ID 用 content_hash，语义分离；不同类型 ID 不相等。
- canonicalize 对 ValorID 输出 `{id_type, value}`，保证不同 ID 类型哈希不同。

### D108 ResolvedParameter 补 dtype 与严格校验（检查单 B1）
- 增加 `dtype` 字段（缺省由 value 推断）；`version_hash` 用 `validate_hash`（小写 hex）校验；
  `source_ref` 用统一 URI schema（`params/refs.py`）校验；`resolved_at` 强制 UTC。

### D109 参数模式门禁 TEST/EXPERIMENT/PRODUCTION（检查单 B2）
- `validate_source_mode()`：TEST 允许 `TEST_FIXTURE`，EXPERIMENT/PRODUCTION 拒绝。

### D110 ComputedValue/MechanismResult 与输入参数分离（检查单 B3）
- 机制输出带 `derived_from`/`input_hashes`/`formula_ref`；config 无法直接填机制输出绕过公式。

### D111 canonical 一次性冻结规则（检查单 C）
- Unicode NFC、datetime UTC、Decimal 定点、set 确定性排序、tuple/list→list、None→null、
  float 禁 NaN/Inf、类型化 ID、schema version="1"；不支持类型显式抛错。

### D112 单位维度系统（检查单 F）
- `KnownUnits` + `UNIT_DIMENSION`；区分 money/rate/duration/time/count/ratio/probability/hash；
  `assert_compatible` 拦截维度不兼容（含"年利率×小时"）。

### D113 错误模型补全（检查单 M）
- 新增 `INVALID_SCHEMA/INVALID_HASH/INVALID_ID/CANONICALIZATION_ERROR/INVALID_RIGHTS/
  CONFIG_VERSION_UNSUPPORTED/INVALID_SOURCE_KIND/INVALID_SOURCE_REF/PARAMETER_CONFLICT`。

### D114 config schema 版本 + 未知字段拒绝 + config hash（检查单 I）
- `SUPPORTED_CONFIG_SCHEMA_VERSION="1"`，不支持抛 `CONFIG_VERSION_UNSUPPORTED`；
  unknown field 拒绝；`H_config=H(Canonicalize(Config))` 可复现，key 重排不变。

### D115 `valor gate phase0` 机器可读 Gate（检查单 T/U）
- 17 项 checks + 8 大硬 Gate 落为可执行函数，输出机器可读 JSON；任一项 FAIL → status FAIL。

## Phase 1 决策（数据管线 + 质量 primitive + 复现 Gate B）

### D116 数据管线四角色划分与候选批次（规范 §55/§56）
- `valor/data/split_roles.py`：BaseTrain/SellerPool/ValuationValidation/FinalEvaluation 四角色互斥（`assert_disjoint`）。
- `valor/data/transaction_batches.py`：`CandidateBatch` 为交易单位（§56），K 与行数由 config 显式提供。
- `valor/data/download.py`：默认用 sklearn 内置真实公开二分类数据集（breast_cancer/digits），离线安全、可复现。

### D117 受控注入 InjectionSpec（规范 §15.4）
- `InjectionKind` 覆盖 9 类：missingness/schema_violation/exact_duplicate/near_duplicate/
  label_flip/covariate_shift/label_shift/metadata_false_claim/committed_dataset_replacement。
- `InjectionSpec.seed` 为 required（无默认值，满足 fail-closed + 默认值扫描）。

### D118 质量 primitive 复现等价规则（规范 §15.1–15.3）
- deterministic：canonical output 哈希完全一致（structural/exact_duplicates/metadata）。
- floating：仅比较 reference 与 native 共同数值指标，绝对+相对容差（ks/categorical/mmd）。
- stochastic/model-based（confident_learning）：cleanlab reference 与 native(mean-threshold)
  版本语义等价——仅比较 error-rate 共享指标 + 注入 ground-truth 召回阈值（§10）。

### D119 Gate B 控制 distributed_enabled（规范 §14/§15）
- 复现 Gate 通过前 `distributed_enabled=False`；全算法通过后才置 True。
- ground-truth 召回阈值仅在该算法针对的错误类型确实被注入（positive>0）时启用。

### D120 canonical 支持 numpy 标量/数组
- canonicalize 增加 numpy integer/float/bool/ndarray 处理（质量指标含 np.int64 等），
  保证跨实现输出哈希可比较。

### D121 cleanlab>=2.x API 适配
- 使用 `cleanlab.count.compute_confident_joint(labels, probs)` 与
  `cleanlab.filter.find_label_issues(labels, probs)`（2.9 签名）。

## Phase 2–8 决策（分布式 / Audit-VOI / 估值 / 责任定价 / 用途 / 状态机 / 实验）

### D122 分布式节点用独立进程（进程管理器方案，§17）
- 无 docker，用 `subprocess` 拉起多个独立 FastAPI 节点进程；HTTP 派发任务/证据/
  challenge；调度器完成 VCG 分配→BFT 证书→聚合（§48 Q1）。

### D123 Reverse VCG 用组合枚举保证精确最优
- 小委员会规模用 `itertools.combinations` 求精确最小成本委员会，保证
  AllocationOptimalityGap=0（§72）；删除 winner 无替补 → COUNTERFACTUAL_INFEASIBLE（§18）。

### D124 Audit-VOI 用认证动作目录 + VOI 停止规则
- action 似然 Λ_j 由校准数据估计（§21.2）；MV_A/VOI 按 §24/§25，max≤0 → STOP。

### D125 检测认证用有限 certified cells + Beta 保守下界
- p̲_B^sys = min_h Q_{α_D}[Beta(a_D+TP_h,b_D+FN_h)]（§22）；样本量按 §67 搜索。

### D126 定价/责任全按 §30/§31/§38–§41 公式
- B_S^*/B_S^pre/C_B^cap、P_max/P_min、M_T<0→NO_TRADE、P*=P_min+β_bar M_T。

### D127 结算资金流按终态（§43）+ double-entry 守恒（§42）
- TRADE/NO_TRADE/SELLER_BREACH/BUYER_BREACH 各自资金流；Ledger 校验守恒。

### D128 反馈仅 ground-truth-eligible 事件更新 posterior（§45/§46）
- GroundTruthEligibilityGate；PASS 不⇒TN；Beta posterior 更新。

### D129 全流程交易编排（engine/orchestrator.py）
- 正式交易唯一入口 `python -m valor transaction run` → config → `CapstoneScenario` →
  `TransactionOrchestrator`，把主链各阶段串成一次可运行交易，输出全部数值与成交决策。
- `run.py` / `experiment.py` 已删除；不存在第二套交易入口。

### D130 实验统计规范（§66）
- mean/median+CI、Wilson 比例区间、Holm 校正、paired t/Wilcoxon。
