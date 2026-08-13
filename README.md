# VALOR-v1：双层信息价值数据交易闭环

在空孤儿分支 **VALOR-v1** 上，以冻结版机制文档为唯一设计依据，从零实现"双层信息价值驱动数据要素交易闭环"的完整机制与实验层。

> **唯一 normative source**：`双层信息价值数据交易闭环_完整数学机制_四算法_实验与Baseline.md`（冻结版 v2）。本仓库不参考任何 DDTM 历史代码；其他分支仅作历史存档。

## 核心主线（机制文档 §34 闭环）
```
Data-VOI → Audit-VOI → AuditMarket → TrustedAudit → p̲_B^sys → B_S* → Price → State → Feedback
```

## 设计决策（D1–D20）
详见 `docs/DESIGN_DECISIONS.md`。要点：
- D1 三级检测概率接口：`λ^prim → Λ_a^action → p_B^sys(Π_A)`
- D2 p̲_B^sys 认证有限 certified cells Ω_c
- D9 Reverse VCG 私人成本含资本占用 `b_i = k_i + κ_A B_A,i T_A`
- D13 卖方保证金预锁 `B_S^pre` + 资本成本积分
- D16 SW_base/SW_full/SAW 会计口径冻结
- D18 证据资格门 EvidenceEligibilityGate

## 目录结构
```
valor/       # 机制实现 + 实验代码（Python 包）
docs/        # 项目文档（ARCHIVE_SPEC / VERSION_CONTROL_SPEC / DESIGN_DECISIONS）
configs/     # 实验配置（JSON，参数显式无默认值）
data/        # 数据集（raw/prepared 不入库）
scripts/     # 一键复现脚本
raw/         # 实验原始结果（gitignore）
reports/     # 实验报告（figures 不入库）
```

## 复现
```bash
python -m valor.report --config configs/lab-default.json   # 或
bash scripts/run-valor.sh
```

## 文档索引
- `docs/ARCHIVE_SPEC.md` — 目录归档规范
- `docs/VERSION_CONTROL_SPEC.md` — 版本控制规范
- `docs/DESIGN_DECISIONS.md` — 设计决策 D1–D20
- `docs/mechanism-frozen-v2.md` — 冻结版机制文档（D20 回写）
