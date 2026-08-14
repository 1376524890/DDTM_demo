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
