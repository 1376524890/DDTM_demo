# VALOR-v1 目录归档规范

本文件定义 VALOR-v1 仓库的目录结构、命名约定与归档规则，作为所有代码与文档的统一组织标准。

## 1. 顶层目录

```
DDTM/  (VALOR-v1 分支工作树根)
├── valor/                 # 机制实现 + 实验代码（Python 包，核心）
├── docs/                  # 项目文档（本规范、版本控制规范、机制冻结版等）
├── configs/               # 实验配置（JSON，参数显式、无默认值）
│   └── economics/         # 经济参数：payoff.json, audit_loss_matrix.json
├── data/                  # 数据集（gitignore：raw/prepared 不入库）
│   ├── raw/               # 原始公开数据（下载，gitignore）
│   ├── prepared/          # 预处理后数据（gitignore）
│   └── manifest/          # dataset_manifest.json（入库）
├── scripts/               # 一键复现 shell 脚本（run-valor.sh）
├── raw/                   # 实验原始结果 JSON（gitignore）
├── reports/               # 实验报告 Markdown + figures/（figures gitignore）
├── logs/                  # 运行日志（gitignore）
├── .gitignore
├── README.md
└── <冻结版机制文档>.md     # 唯一 normative source（D20）
```

## 2. valor/ Python 包结构

```
valor/
├── __init__.py            # 版本号、包导出
├── config.py              # 类型化 dataclass + JSON 加载 + 参数完整性/单位校验
├── models.py              # 结果 dataclass + to_plain()
├── metadata.py            # reproducibility 元数据（git commit / sha256 / 参数哈希）
├── calibration/           # 三级似然 + 认证（D1/D2/D19）
│   ├── __init__.py
│   ├── audit_profile.py   # audit_profile_id + 有限 certified cells Ω_c
│   ├── primitive.py       # Phase 1.5A: λ^prim + ResourceCostModel_j
│   ├── compose_action.py  # Phase 1.5B: λ^prim → Λ_a^action
│   ├── certification.py   # Phase 2.5: R1→R2→R3→Freeze→R_cert + 样本量计算
│   └── registry.py        # key → p̲_B^sys；PROFILE_OUT_OF_CERTIFIED_RANGE
├── valuation/             # Data-VOI（RQ1）
├── audit/                 # Audit-VOI（RQ2）
├── market/                # 反向审计市场（RQ3）
├── security/              # 节点安全（BFT/challenge/slashing/liveness/detection_calibration）
├── contract/              # 合同与结算（RQ4-6）
├── feedback/              # 贝叶斯反馈闭环
├── evaluation/            # 实验评估（oracle/utilities/welfare/metrics/statistics/matched_security）
├── data/                  # 数据管线（download/preprocess/contamination/states_gt/provenance）
├── plotting/              # 图表生成
├── report.py              # CLI + JSON/Markdown + gate
└── run.py                 # 一键编排
```

## 3. 命名约定

| 项 | 约定 | 示例 |
|---|---|---|
| Python 模块/函数 | snake_case | `build_initial_prior` |
| Python 类 | PascalCase | `AuditPolicySpec`, `AuditTrace` |
| 常量 | UPPER_SNAKE | `PROFILE_OUT_OF_CERTIFIED_RANGE` |
| 配置 key | 与机制文档符号一致 | `policy_hash`, `p_breach_lcb` |
| 数据文件 | `<dataset>_<role>.csv` | `covertype_seller_pool.csv` |
| 结果 JSON | `<phase>_result.json` | `phase2_audit_result.json` |
| 报告 | `<topic>-report.md` | `rq1-datavoi-report.md` |

## 4. 归档规则

- **入库**：源码、配置模板、manifest、冻结文档、规范文档、报告 Markdown。
- **不入库**（gitignore）：`data/raw`、`data/prepared`、`raw/`、`reports/figures/`、`logs/`、`*.png`、`*.npz`、`*.parquet`、`*.arff`。
- 数据文件**永不入库**；通过 `dataset_manifest.json` 记录来源/哈希/许可，可重下载复现。
- 实验结果 JSON 若需入库（作为 release 快照），置于 `raw/` 并显式 `git add -f`，附 git commit 元数据。

## 5. 复现原则

- 所有随机操作使用固定 seed，seed 记录于配置。
- 每个结果文件必须可追溯到：git commit + dataset sha256 + 完整参数哈希。
- 禁止"无来源默认值"：任何论文参数必须在 `configs/` 显式配置，缺失即报错（Phase 0 gate）。
