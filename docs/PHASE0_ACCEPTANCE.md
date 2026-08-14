# VALOR Phase 0 验收检查单执行报告

> 检查对象：VALOR 可实施原型系统 Phase 0（Repository / Types / Parameter Governance）
> 检查依据：验收检查单（A–U 节 + 8 大硬 Gate）
> 结论：**全部通过（PASS）** —— `python -m valor gate phase0` 输出 `status: PASS`，
> 8 大硬 Gate 均为 `true`，`hard_gate_all = true`。
> 真实命令输出见 `reports/phase0_acceptance_commands.log`。

## 0. 硬 Gate 汇总（检查单 U）

```
G_0 = G_R ∧ G_T ∧ G_C ∧ G_P ∧ G_U ∧ G_F ∧ G_H ∧ G_Test = 1  ✅
```

| Gate | 含义 | 结果 |
|---|---|---|
| G_R | Repository：包可安装/import/CLI/结构 | PASS |
| G_T | Type：核心类型唯一且严格（DataAsset/RightsBundle/ResolvedParameter/Money/ID） | PASS |
| G_C | Canonicalization：序列化/canonical bytes/hash 跨运行稳定 | PASS |
| G_P | Parameter Provenance：参数有合法来源/证据/单位/版本 | PASS |
| G_U | Unit：经济量与概率量纲正确，禁止非法运算 | PASS |
| G_F | Fail-Closed：缺参/错参/缺证据/错单位必须停止 | PASS |
| G_H | No Hidden Default：AST 扫描 + runtime 证明无业务默认值 | PASS |
| G_Test | Verification：正向/负向/round-trip/property 全过 | PASS |

---

## A. Repository 与 Python Package — PASS

- 分支确认 `VALOR-v1`（`git branch --show-current`），无旧 DDTM 实现（清理提交 `58138fe`）。
- `.gitignore` 排除 `__pycache__/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`、`.venv/`、`dist/`、`build/`、`.env`、`configs/local/`、实验缓存与原始下载数据。
- `pyproject.toml` 存在：`requires-python = ">=3.11"`；主依赖与 `[project.optional-dependencies]`（quality/torch/parquet/dev）分离；直接依赖显式声明。
- `python -m pip install -e .` 成功（rc=0）；`python -c "import valor; print(valor.__version__)"` → `0.2.0`。
- `python -m valor --version` / `--help` 成功。
- import 无网络/数据下载/随机副作用；不依赖 CWD。
- 最小目录存在：`valor/{__init__,cli}.py`、`valor/core|params|asset|rights`、`configs/schemas`、`tests/{unit,property}`。

## B. 核心类型冻结 — PASS

### B1. ResolvedParameter
- 单一 canonical 定义于 `valor/params/models.py`，后续模块不各自声明。
- 字段：`name, value, dtype, unit, source_kind, source_ref, resolved_at, version_hash, uncertainty/Interval` 齐全。
- `value` 无业务默认值；`dtype` 缺省时由 value 推断；`source_ref` 缺失抛 `MISSING_EVIDENCE_REF`。
- `resolved_at` 强制 UTC ISO-8601；`version_hash` 用 `validate_hash`（小写 hex 8..128）拒绝任意字符串。
- `uncertainty` 用 `Interval`（明确 schema：lower/upper/unit/confidence），非自由字典。
- 对象 `@dataclass(frozen=True)` 不可变。

### B2. ParamSource 模式门禁
- `ParamSource` 含 `TEST_FIXTURE`（8 类来源齐全，检查单要求冻结）。
- `validate_source_mode()`：`mode==TEST` 允许 `TEST_FIXTURE`；`EXPERIMENT/PRODUCTION` 拒绝。
- 有自动测试（`test_source_mode_fixture_gate`、`test_q6`）；不允许改名绕过（source_ref scheme 校验 + 代码审查）。

### B3. 机制输出与外部参数分离
- 新增 `ComputedValue`/`MechanismResult`（`derived_from` + `input_hashes` + `formula_ref`），与 `ResolvedParameter` 严格分离。
- config 无法直接填 `seller_bond_star`/`clearing_price` 绕过对应公式（这些只能由机制计算产生）。

## C. Canonical Serialization — PASS

- 唯一实现 `canonicalize()` / `canonical_bytes()` / `canonical_dumps()`（`valor/core/canonical_json.py`），所有模块复用。
- 规则明确：dict 按 str(key) 排序；UTF-8；Unicode NFC；datetime/date 统一 UTC ISO-8601（`Z`）；Enum 取 `.value`；tuple/list → list；set/frozenset 确定性排序；`None` → null；bytes → lowercase hex；Decimal 定点字符串；float 禁止 NaN/Inf；类型化 ID 含 id_type。
- 不纳入 object address / repr / set 迭代顺序（不支持类型显式抛 `CANONICALIZATION_ERROR`）。
- schema `version = "1"`（`CANONICAL_SCHEMA_VERSION`）。
- 固定 test vector 覆盖：key 重排、set 顺序、Unicode NFC、None、tuple/list（`tests/property/test_canonicalization_properties.py`）。

## D. Hashing 与 Commitments — PASS

- SHA-256 集中于 `valor/core/hashing.py`（`HASH_ALGORITHM`/`HASH_VERSION`），统一 lowercase hex。
- `hash_object(x) = H(Canonicalize(x))`；`content_hash` 一致。
- `validate_hash` 拒绝错误长度/字符；tamper 测试（committed 字段变化 → hash 变化，见 `test_hash_properties.py`）。
- `version_hash`（参数版本）与对象内容 hash 语义分离。

## E. ID 系统 — PASS

- 类型化：`AssetID/VersionID/TransactionID/SellerID/BuyerID/AuditorID/PolicyID/CalibrationID/RightsID/EventID`。
- 随机 ID 用 `secrets.token_hex`（非 Python `hash()`）；内容寻址 ID 用 content_hash，语义分离。
- ID 可序列化（`to_plain`）/严格解析（`of`）；无效 ID fail closed（`INVALID_ID`）；禁止空串。
- 不同类型 ID 不相等（`AssetID("a") != TransactionID("a")`），防止混用。

## F. Money 与单位系统 — PASS

- 统一 `[CU]`；`Money` 值对象仅接受 CU，禁止与 probability 相加（`UNIT_MISMATCH`）。
- `KnownUnits` 区分 money/rate/duration/time/count/ratio/probability/hash，带 `UNIT_DIMENSION` 维。
- probability dimensionless，`require_probability` 强制 `0<=p<=1`。
- 资本成本"年利率×小时"由 `RATE` vs `TIME/DURATION` 维度区分，`assert_compatible` 拦截。
- resolver 在算法调用前执行 unit compatibility validation。

## G. Parameter Resolver — PASS

- `require_resolved(name)` / `resolver.require()` 存在；找不到即抛 `UNRESOLVED_PARAMETER`，不返回 None/0。
- 不读环境变量/默认 section；禁止 `config.get("x", default)`（AST 扫描 + resolver 设计）。
- 错误含参数名；`source_ref` 缺失 → `MISSING_EVIDENCE_REF`；范围 → `OUT_OF_CERTIFIED_RANGE`；单位 → `UNIT_MISMATCH`。
- 同名参数来源/单位冲突 → `PARAMETER_CONFLICT`（`resolver.register` 检测，检查单 Q#20/21）。

## H. 默认值静态扫描 — PASS

- 实现 `scripts/check_business_defaults.py`（AST）：抓 `config.get("x",d)`、`getattr(...,d)`、`x or 0.1`、`Field(default=...)`、业务字段注解默认值。
- 运行 `python scripts/check_business_defaults.py --root valor` → `OK: 未发现业务默认值`（rc=0）。
- tests/fixtures 目录豁免；大写常量名 + `ALLOWED_CONSTANTS` 白名单（受代码审查）。

## I. Config Schema — PASS

- `configs/schemas/transaction.schema.json`（draft-07）；`schema_version` 强制 `"1"`，不支持抛 `CONFIG_VERSION_UNSUPPORTED`。
- unknown field 拒绝（`additionalProperties:false` + 运行时 `_reject_unknown`），拼写错误不静默。
- 缺 required/类型错误 → 解析失败；NaN/Inf 拒绝；`mode`（TEST/EXPERIMENT/PRODUCTION）区分。
- config hash `H_config = H(Canonicalize(Config))` 可复现；key 重排不影响（有测试）。

## J. DataAsset 基础类型 — PASS

- `DataAsset`/`AssetVersion` 存在；`asset_id`/`version_id`/data+metadata commitment 均 required。
- provenance_ref 为 Optional（absent 语义明确）；canonicalize/hash/round-trip 稳定。
- 数据内容不入哈希（存承诺 H(D)）；原始数据位置与 dataset hash 分离（`DatasetManifest`）。
- 版本变化 → 对象 hash 变化（`test_version_change_changes_hash`）。

## K. RightsBundle 基础类型 — PASS

- 核心字段 required；可选字段须配 `not_applicable_reason`（否则 `INVALID_RIGHTS`）。
- 拒绝：`t1<t0`、负 usage count、负 privacy budget、无效枚举、DP 预算与 DOWNLOAD 矛盾。
- `H(R_τ)` 可稳定计算；任意权利字段变化 → hash 变化。

## L. Serialization Round-Trip — PASS

- 覆盖 ResolvedParameter/Money/Interval/DataAsset/RightsBundle/IDs/enums/manifest，均满足 `x==x'` 且 `H(x)==H(x')`（`test_roundtrip.py` + `tests/property/test_serialization_roundtrip.py`）。

## M. Error Model — PASS

- 机器可读错误码齐全：`UNRESOLVED_PARAMETER`/`OUT_OF_CERTIFIED_RANGE`/`MISSING_EVIDENCE_REF`/`UNIT_MISMATCH`/`INVALID_SCHEMA`/`INVALID_HASH`/`INVALID_ID`/`CANONICALIZATION_ERROR`/`INVALID_RIGHTS`/`CONFIG_VERSION_UNSUPPORTED`/`INVALID_SOURCE_KIND`/`INVALID_SOURCE_REF`/`PARAMETER_CONFLICT`。
- `VALORError` 带 `code` 与 `message` 分离，`to_plain()` 供日志；CLI 错误用非零退出码；不泄露 secret。

## N. CLI Fail-Closed — PASS

- `python -m valor transaction run`（无 --config）→ argparse 报错，rc=2。
- 空 config → `配置校验失败: 缺失必需参数: transaction`，rc=1。
- 不自动寻找 default/sample/home 配置；仅 RequiredParameter 全部满足才进入业务入口。

## O. Provenance 与 Evidence Reference — PASS

- `source_ref` 有统一 URI schema（`params/refs.py`）：`dataset://`、`calib://`、`contract://`、`market://`、`optimizer://`、`threat://`、`standard://`、`fixture://`。
- `validate_source_ref` 校验格式与 scheme 匹配来源；缺失 → `MISSING_EVIDENCE_REF`，不匹配 → `INVALID_SOURCE_REF`。
- Phase 0 定义 reference contract（不生成真实 artifact，但约束已冻结）。

## P. Reproducibility Metadata — PASS

- `valor/core/reproducibility.py` 输出：`valor_version/git_commit/git_dirty/python_version/platform/dependency_lock_hash/config_hash/schema_version/timestamp_utc`。
- git commit 可获取、dirty 可识别、timestamp 用 UTC、元数据可序列化。

## Q. 必测负向用例（24 项）— PASS

`tests/unit/test_negative.py` 覆盖全部 24 项，目标均为"必须失败"；连同 round-trip 等，`pytest -q` 全绿（84 passed）。

## R. Property Tests — PASS

`tests/property/`：
- `test_canonicalization_properties.py`：幂等、key/set 顺序无关、Unicode NFC、None。
- `test_hash_properties.py`：可重复、round-trip 保持、逐字段 mutation → hash 变化。
- `test_parameter_properties.py`：随机参数 round-trip、source 模式门禁、dtype 推断。
- `test_money_units_properties.py`：Money 算术、维度区分、概率范围。
- `test_serialization_roundtrip.py`：核心对象 round-trip 保持 hash。

## S. 自动验收命令 — PASS

全部命令真实输出已保存至 `reports/phase0_acceptance_commands.log`（11 条命令，含 `gate phase0`）。

## T. `valor gate phase0` — PASS

`python -m valor gate phase0 --config tests/fixtures/phase0_valid.json` → `status: PASS`，17 项 checks 全 PASS，8 大硬 Gate 全 true，`hard_gate_all: true`。无 `PASS_WITH_WARNINGS`。

---

## 测试统计
- 单元测试 `tests/unit`：65 passed
- 属性测试 `tests/property`：19 passed
- 合计：**84 passed**（`pytest -q`）
- 默认值扫描：`OK: 未发现业务默认值`
- 关键命令退出码：empty config rc=1、no config rc=2、gate phase0 rc=0

## 结论
Phase 0 全部检查项 PASS，8 大硬 Gate 全通过，满足进入 **Phase 1（数据管线 + 质量 primitive reference/native + 复现 Gate B）** 的条件。
