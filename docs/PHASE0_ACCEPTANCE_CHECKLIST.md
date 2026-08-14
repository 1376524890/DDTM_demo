# VALOR Phase 0 开发验收检查单（已勾选）

> 逐项勾选并附证据。全部通过 → `python -m valor gate phase0` 输出 `status: PASS`，
> 8 大硬 Gate 全 `true`。命令输出见 `reports/phase0_acceptance_commands.log`。

## A. Repository 与 Python Package ✅
- [x] Git 分支为 `VALOR-v1`，无旧 DDTM 实现（清理提交 `58138fe`）。
- [x] `git status` 无意外文件（`__pycache__/.venv/raw/` 等均 gitignore）。
- [x] `.gitignore` 排除 `__pycache__/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`、`.venv/`、`dist/`、`build/`、`.env`、`configs/local/`、实验缓存、原始数据。
- [x] 存在合法 `pyproject.toml`。
- [x] `requires-python = ">=3.11"` 显式声明。
- [x] 主依赖与 `[project.optional-dependencies]`（quality/torch/parquet/dev）分离。
- [x] 直接依赖显式声明（numpy/pandas/scipy/sklearn/pydantic/fastapi/uvicorn/httpx/cryptography/networkx/matplotlib）。
- [x] `python -m pip install -e .` 成功（rc=0）。
- [x] 新 shell `import valor; valor.__version__` → `0.2.0`。
- [x] `python -m valor --help` 成功。
- [x] `python -m valor --version` 成功。
- [x] import 无网络/数据下载/随机副作用。
- [x] import 不依赖 CWD。
- [x] 项目根无与 `valor/` 重名的 shadowing 文件。
- [x] 最小目录存在：`valor/{__init__,cli}.py`、`core/params/asset/rights`、`configs/schemas`、`tests/{unit,property}`。

## B. 核心类型冻结 ✅
### B1. ResolvedParameter
- [x] 唯一 canonical 定义于 `valor/params/models.py`，后续模块不各自声明。
- [x] 字段齐全：`name, value, dtype, unit, source_kind, source_ref, resolved_at, version_hash, uncertainty/Interval`。
- [x] `value` 无业务默认值（dataclass 字段无 default）。
- [x] `source_ref` 缺失抛 `MISSING_EVIDENCE_REF`（非空校验）。
- [x] `resolved_at` 强制 UTC ISO-8601（`Z`/`+00:00`）。
- [x] `version_hash` 经 `validate_hash`（小写 hex 8..128），拒绝任意字符串。
- [x] uncertainty/Interval 有明确 schema（`Interval{lower,upper,unit,confidence}`），非自由字典。
- [x] `@dataclass(frozen=True)` 不可变。

### B2. 当前规范冲突已消除（source_kind 模式门禁）
- [x] `ParamSource` 冻结 8 类，含 `TEST_FIXTURE`。
- [x] `validate_source_mode()`：TEST 允许 TEST_FIXTURE；EXPERIMENT/PRODUCTION 拒绝。
- [x] 对应自动测试（`test_source_mode_fixture_gate`、`test_q6`）。
- [x] TEST_FIXTURE 无法通过 production config parser。
- [x] 不允许改名绕过（source_ref scheme 校验 + 代码审查）。

### B3. 机制输出与外部参数分离
- [x] `ComputedValue`/`MechanismResult`（`derived_from`+`input_hashes`+`formula_ref`）与 `ResolvedParameter` 分离。
- [x] config 无法填 `seller_bond_star`/`clearing_price` 绕过公式。
- [x] 算法输出带 `derived_from`/input hashes 可向前追踪。
- [x] `OPTIMIZER_OUTPUT` 仅用于优化器求得的后续输入参数。

## C. Canonical Serialization ✅
- [x] 唯一 `canonicalize()/canonical_bytes()/canonical_dumps()`（`valor/core/canonical_json.py`）。
- [x] 所有核心 dataclass 复用同一实现。
- [x] 禁止模块各自 `json.dumps` 后哈希。
- [x] dict key 顺序变化不改 canonical bytes（test）。
- [x] Python 进程重启不变（幂等测试）。
- [x] 不同机器相同输入结果一致。
- [x] UTF-8 编码明确（ensure_ascii=True）。
- [x] Unicode 统一 NFC 归一化。
- [x] datetime 统一 UTC ISO-8601（`Z`）。
- [x] Enum 取 `.value`。
- [x] tuple/list → list；set/frozenset 确定性排序（规则明确）。
- [x] `None` → null。
- [x] float 禁止 NaN/Infinity（`CANONICALIZATION_ERROR`）。
- [x] 浮点不依赖 locale（json repr）。
- [x] 不纳入 object address / repr / set 迭代顺序；不支持类型显式抛错。
- [x] Decimal 定义定点字符串表示。
- [x] canonicalization schema `version="1"`。
- [x] 固定 test vector（key 重排/set 顺序/Unicode/None/tuple-list）。

## D. Hashing 与 Commitments ✅
- [x] SHA-256 集中于 `core/hashing.py`（`HASH_ALGORITHM`/`HASH_VERSION`）。
- [x] 不四处调用不同 hash library。
- [x] lowercase hex 统一。
- [x] `sha256_hex(data: bytes)` 接受 bytes。
- [x] `hash_object(x) == H(Canonicalize(x))`。
- [x] 同一对象 hash 可重复。
- [x] committed 字段变化 → hash 变化（tamper/mutation 测试）。
- [x] 未 committed 运行时 metadata 不改变业务对象 hash。
- [x] `version_hash` 与对象内容 hash 语义分离。
- [x] hash 算法/版本写入 metadata。
- [x] 错误长度/字符 hash 被 `validate_hash` 拒绝。
- [x] tamper 测试存在（`test_hash_properties.py`）。

## E. ID 系统 ✅
- [x] 类型化 ID：`AssetID/VersionID/TransactionID/SellerID/BuyerID/AuditorID/PolicyID/CalibrationID/RightsID/EventID`。
- [x] 创建规则明确（`new()`/`of()`）。
- [x] 随机 ID（secrets.token_hex）与内容寻址 ID 分离。
- [x] ID 不依赖 Python `hash()`（token_hex）。
- [x] 可序列化（`to_plain`）。
- [x] 可严格解析（`of`）。
- [x] 无效 ID fail closed（`INVALID_ID`）。
- [x] 禁止空 ID。
- [x] 类型不同不混用（`AssetID("a") != TransactionID("a")`）。

## F. Money 与单位系统 ✅
- [x] 统一货币单位 `[CU]`。
- [x] `Money` 值对象（非裸 float）。
- [x] Money 不与 probability 相加（`UNIT_MISMATCH`）。
- [x] 不兼容单位相加抛 `UNIT_MISMATCH`。
- [x] probability 明确 dimensionless。
- [x] probability 自动校验 `0<=p<=1`（`require_probability`）。
- [x] rate/duration/money/count/ratio 有区别（`UNIT_DIMENSION`）。
- [x] 时间单位统一。
- [x] 资本成本"年利率×小时"由 RATE vs TIME/DURATION 维度拦截。
- [x] resolver 在算法调用前做 unit compatibility validation。
- [x] 同一符号全 schema 用相同单位。
- [x] 核心接口无裸 `amount: float` 而不知单位。

## G. Parameter Resolver ✅
- [x] `require_resolved(name)` 存在。
- [x] 找不到参数 fail closed。
- [x] 不返回 `None` 让下游继续算。
- [x] 不返回 0 代替缺失参数。
- [x] 不读环境变量作为隐式默认。
- [x] 不读默认 section 静默补值。
- [x] 不用 `config.get("x", default)` 处理业务参数。
- [x] 不用 `config.x or default` 绕过。
- [x] dataclass/Pydantic 字段无业务数字默认值。
- [x] 错误含参数名/来源（caller 见栈帧）。
- [x] `source_ref` 缺失 → `MISSING_EVIDENCE_REF`（非 warning）。
- [x] 范围越界 → `OUT_OF_CERTIFIED_RANGE`。
- [x] 单位不兼容 → `UNIT_MISMATCH`。
- [x] 未解析 → `UNRESOLVED_PARAMETER`。

## H. 默认值静态扫描 ✅
- [x] `scripts/check_business_defaults.py`（AST）存在。
- [x] 抓 `config.get("x",d)`、`getattr(...,d)`、`x or 0.1`、`Field(default=...)`、`default_factory`、业务字段注解默认值。
- [x] CI 中自动运行（`gate phase0` 内调用）。
- [x] 命中业务默认值直接失败（rc!=0）。
- [x] tests/fixtures 目录允许显式测试常量。
- [x] 数学/dtype/密码学常量白名单（大写常量名 + `ALLOWED_CONSTANTS`）。
- [x] 白名单受代码审查（显式集合）。
- 运行结果：`OK: 未发现业务默认值`（rc=0）。

## I. Config Schema ✅
- [x] `configs/schemas/` 生产 schema 存在。
- [x] experiment/test/production 用 `mode` 区分。
- [x] unknown field 拒绝（`additionalProperties:false` + `_reject_unknown`）。
- [x] 拼写错误不静默忽略（`challange_rate` → `INVALID_SCHEMA`）。
- [x] 缺 required field 解析失败。
- [x] 类型错误解析失败。
- [x] `"0.05"` 字符串不在 strict 下静默转 float。
- [x] NaN/Inf 拒绝。
- [x] source kind 与 evidence 组合检查（`validate_source_ref`）。
- [x] config schema 版本号（`SUPPORTED_CONFIG_SCHEMA_VERSION="1"`）。
- [x] 不支持的 schema 版本 fail closed（`CONFIG_VERSION_UNSUPPORTED`）。
- [x] `H_config=H(Canonicalize(Config))`。
- [x] 相同 config 重复运行 hash 一致。
- [x] 修改字段 → config hash 改变。
- [x] key 重排不改 config hash（test）。

## J. DataAsset 基础类型 ✅
- [x] `DataAsset`/`AssetVersion` 存在。
- [x] `asset_id` required。
- [x] `version_id` required。
- [x] dataset commitment required。
- [x] metadata commitment required。
- [x] provenance absent/not-applicable 语义明确（Optional）。
- [x] 可 canonicalize。
- [x] 可 hash。
- [x] round-trip 后 hash 不变。
- [x] version 变化 → 对象 hash 变化。
- [x] 数据内容不被 Python object reference 序列化（存承诺 H(D)）。
- [x] 原始数据位置与 dataset hash 分离（`DatasetManifest`）。

## K. RightsBundle 基础类型 ✅
- [x] `RightsBundle` 存在。
- [x] 核心字段 schema 齐全（right_class/access_mode/valid_from/valid_until/max_uses/purpose/scope/exclusivity/redistribution/derivative_right/privacy_budget/retention/delete_duty）。
- [x] 不适用字段不能单独 `None`（须配 `not_applicable_reason`）。
- [x] `t1<t0` 拒绝。
- [x] 负 usage count 拒绝。
- [x] 负 privacy budget 拒绝。
- [x] 无效枚举拒绝。
- [x] contradictory rights 被 schema 校验捕获（DP 预算×DOWNLOAD 矛盾）。
- [x] canonicalize 稳定。
- [x] `H(R_τ)` 可稳定计算。
- [x] 任意权利字段变化 → `H(R_τ)` 变化。

## L. Serialization Round-Trip ✅
- [x] ResolvedParameter、Money、DataAsset、RightsBundle、IDs、enums、Interval、config manifest 均 round-trip，满足 `x==x'` 且 `H(x)==H(x')`。

## M. Error Model ✅
- [x] 稳定 error code：`UNRESOLVED_PARAMETER/OUT_OF_CERTIFIED_RANGE/MISSING_EVIDENCE_REF/UNIT_MISMATCH/INVALID_SCHEMA/INVALID_HASH/INVALID_ID/CANONICALIZATION_ERROR/INVALID_RIGHTS/CONFIG_VERSION_UNSUPPORTED/INVALID_SOURCE_KIND/INVALID_SOURCE_REF/PARAMETER_CONFLICT`。
- [x] human message 与 machine code 分离（`VALORError.code`/`.message`）。
- [x] error 含 context。
- [x] 不泄露 secret/path/token。
- [x] CLI 错误非零退出码。
- [x] exception 不被 catch 成"成功+warning"。

## N. CLI Fail-Closed ✅
- [x] `python -m valor transaction run`（无 config）失败（rc=2）。
- [x] exit code != 0。
- [x] 明确报告 missing config。
- [x] 不自动找 `default.yaml`。
- [x] 不加载 home 配置。
- [x] 不加载 sample config。
- [x] 空 config 失败（rc=1）。
- [x] 仅全部 RequiredParameter 满足才进入业务入口。

## O. Provenance 与 Evidence Reference ✅
- [x] 每个参数有 `source_ref`。
- [x] `source_ref` 统一 URI schema（`params/refs.py`）。
- [x] 非自然语言（`dataset://`、`calib://`、`contract://`、`market://`、`optimizer://`、`threat://`、`standard://`、`fixture://`）。
- [x] calibration artifact 可经 ref 定位。
- [x] optimizer output 关联 optimization run。
- [x] market value 关联 bid/auction。
- [x] observed value 关联 dataset/artifact hash。
- [x] threat scenario 关联 scenario manifest。
- [x] source artifact version/hash 可记录（`version_hash`）。
- [x] artifact 修改后 version/hash 可检测（哈希校验）。
- [x] Phase 0 已冻结 reference contract。

## P. Reproducibility Metadata ✅
- [x] `build_repro_metadata()` 输出完整 JSON。
- [x] git commit 可获取。
- [x] dirty state 可识别。
- [x] dirty 工作树不伪报 clean（无法确认时保守 dirty）。
- [x] Python 版本记录。
- [x] package version 记录。
- [x] config hash 记录。
- [x] schema version 记录。
- [x] timestamp 用 UTC。
- [x] 元数据自身可序列化。

## Q. 必测负向用例（24 项）✅
- [x] 1 空 business config
- [x] 2 缺少 required parameter
- [x] 3 value=None
- [x] 4 缺 source_ref
- [x] 5 未知 source_kind
- [x] 6 TEST_FIXTURE 在 production
- [x] 7 money + probability
- [x] 8 probability > 1
- [x] 9 probability < 0
- [x] 10 非法 duration/unit
- [x] 11 NaN/Inf
- [x] 12 无效 hash
- [x] 13 无效 ID
- [x] 14 RightsBundle 缺字段
- [x] 15 RightsBundle None 无 N/A reason
- [x] 16 valid_until < valid_from
- [x] 17 config 未知字段
- [x] 18 config schema version 不支持
- [x] 19 canonicalization unsupported type
- [x] 20 同名参数来源冲突
- [x] 21 同名参数 unit 冲突
- [x] 22 config 未提供但代码 fallback
- [x] 23 CLI 未提供 --config
- [x] 24 production 加载 test/sample fixture

## R. Property Tests ✅
- [x] `tests/property/test_canonicalization_properties.py`：幂等/key/set 顺序/Unicode/None。
- [x] `test_hash_properties.py`：可重复/round-trip/逐字段 mutation → hash 变化。
- [x] `test_parameter_properties.py`：随机参数 round-trip/source 模式/dtype。
- [x] `test_money_units_properties.py`：Money 算术/维度/概率范围。
- [x] `test_serialization_roundtrip.py`：核心对象 round-trip 保持 hash。

## S. 自动验收命令 ✅
- [x] 全部 11 条命令运行并保存至 `reports/phase0_acceptance_commands.log`（含 `gate phase0`）。

## T. `valor gate phase0` ✅
- [x] 输出机器可读 JSON（17 项 checks + 8 大硬 Gate + evidence）。
- [x] 任一项非 PASS → `status: FAIL`。
- [x] 无 `PASS_WITH_WARNINGS`。

## U. 8 大硬 Gate ✅
```
G_0 = G_R ∧ G_T ∧ G_C ∧ G_P ∧ G_U ∧ G_F ∧ G_H ∧ G_Test = 1
```
- [x] G_R Repository ✅
- [x] G_T Type ✅
- [x] G_C Canonicalization ✅
- [x] G_P Parameter Provenance ✅
- [x] G_U Unit ✅
- [x] G_F Fail-Closed ✅
- [x] G_H No Hidden Default ✅
- [x] G_Test Verification ✅

**Phase 0 验收结论：PASS，满足进入 Phase 1 条件。**（Phase 1 已实施：88 passed，7 primitive 复现 Gate 全 PASS）
