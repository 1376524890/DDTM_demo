# VALOR 目录归档规范（ARCHIVE_SPEC）

> 唯一 normative source：`VALOR_可实施原型系统_完整数学代码闭环与开发规范.md`。
> 本文件定义仓库目录结构、归档边界、命名与复现性要求。任何目录变更须与本文件同步。

## 1. 顶层目录结构（对齐规范 §53）

```text
VALOR 可实施原型系统_完整数学代码闭环与开发规范.md   # 唯一规范文档（冻结版，不入代码路径）
pyproject.toml                                       # 包元数据 + 依赖（Phase 0 交付）
README.md                                            # 项目入口说明
.gitignore                                           # 分层忽略规则

valor/               # 机制实现 + 实验代码（Python 包）
configs/             # 实验配置（JSON + JSON Schema；参数显式无默认值）
docs/                # 项目文档（本文件 + VERSION_CONTROL_SPEC + DESIGN_DECISIONS）
scripts/             # 一键复现 / 编排脚本
data/                # 数据集（raw/prepared 不入库）
raw/                 # 实验原始结果（gitignore，可再生成）
reports/             # 实验报告（figures 不入库）
tests/               # 测试（unit/property/reproduction/distributed/integration/attacks/e2e）
```

## 2. 归档边界

| 内容 | 是否入库 | 说明 |
|---|---|---|
| 代码 `valor/`、`tests/` | ✅ | 全部入库 |
| 配置 `configs/`（除 local/）| ✅ | 参数显式，无默认值 |
| 文档 `docs/`、`README.md`、本规范 md | ✅ | 唯一规范文档入库 |
| 依赖声明 `pyproject.toml` | ✅ | — |
| `.venv/` | ❌ | 本地环境 |
| `data/raw/`、`data/prepared/` | ❌ | 大文件/可重建 |
| `raw/`、`reports/figures/`、`*.pdf/*.png/*.parquet/*.npz` | ❌ | 实验输出，可再生成 |
| `.env`、`configs/local/` | ❌ | 密钥/本地配置 |
| 实验二进制向量 `experiments/vectors/` | ❌ | 可再生成 |

## 3. 命名规范

- 包内模块使用 `snake_case.py`；目录名使用 `snake_case`。
- 配置文件名使用 `kebab-case` 或 `snake_case`，与对应 JSON Schema 同名。
- 结果/报告文件一律携带可追溯标识：`experiment_id`、`git_commit`、`param_hash`。

## 4. 复现性要求（对齐规范 §5 参数溯源 + §68 日志字段）

- 所有进入核心公式的参数必须能解析来源；无来源默认值一律 fail closed。
- 每个结果文件必须可追溯到：git commit + 数据集 SHA-256 + 参数哈希。
- 日志/结果 JSON 采用确定性序列化（canonical JSON，sorted keys）。

## 5. 变更流程

- 新增/删除/重命名目录或顶层文件，须同步更新本文件与 `VERSION_CONTROL_SPEC.md`。
- 目录变更作为一个独立 git commit 提交，便于回滚与审计。
