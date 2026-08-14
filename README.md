# VALOR：权利感知、质量可验证与用途可审计的数据交易原型系统

> **Value-Aware Liability and Optimal Risk Allocation for Data Transactions**

以冻结版规范 **《VALOR_可实施原型系统_完整数学代码闭环与开发规范.md》** 为唯一设计依据，从零实现。本仓库不参考任何 DDTM 历史代码。

## 主链（规范 §1/§77）
```
Entitlement → QualityReference → DistributedQualityAudit → V̲_{D,R}^{gross}
→ Π_A^* → p̲_B^{sys} → B_S^* → (P_τ^{min},P_τ^{max}) → P_τ^* → UsageControl → S_T → Θ_{t+1}
```

## 当前进度
- **Phase 0 已完成**：`pyproject.toml`、`valor/core`、`valor/params`、`valor/asset`、`valor/rights`、`configs/schemas`、`tests/unit/test_parameter_fail_closed.py`。
- 验收：空业务配置无法运行 transaction；核心 dataclass 可序列化 / canonicalize / hash。
- 后续 Phase 1–8 见规范 §70。

## 目录结构
```
pyproject.toml        # 包元数据 + 依赖（规范 §72）
valor/                # 机制实现 + 实验代码（Python 包）
configs/              # 配置（JSON + JSON Schema；参数显式无默认值）
configs/schemas/      # 配置 JSON Schema
docs/                 # ARCHIVE_SPEC / VERSION_CONTROL_SPEC / DESIGN_DECISIONS
tests/                # 单元测试（unit/）
scripts/              # 一键复现脚本（后续 Phase）
data/                 # 数据集（raw/prepared 不入库）
raw/                  # 实验原始结果（gitignore）
reports/              # 实验报告（figures 不入库）
```

## 使用
```bash
# 安装
python -m pip install -e ".[dev]"

# CLI（规范 §71）
python -m valor --version
python -m valor transaction run --config configs/example.transaction.json

# Phase 0 验收 Gate（检查单 T：输出机器可读 JSON，8 大硬 Gate）
python -m valor gate phase0 --config tests/fixtures/phase0_valid.json

# 业务默认值静态扫描（检查单 H）
python scripts/check_business_defaults.py --root valor

# 测试（unit + property）
python -m pytest
```

## 文档
- `docs/ARCHIVE_SPEC.md` — 目录归档规范
- `docs/VERSION_CONTROL_SPEC.md` — 版本控制规范（提交/门禁）
- `docs/DESIGN_DECISIONS.md` — 设计决策（D100 起）
- `VALOR_可实施原型系统_完整数学代码闭环与开发规范.md` — 唯一规范文档
