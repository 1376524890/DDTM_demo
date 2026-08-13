# VALOR-v1 版本控制规范

本文件定义 VALOR-v1 分支的 git 使用规范，确保可追溯、可复现、可回滚。

## 1. 分支策略

- **VALOR-v1**：主开发分支（当前），从空孤儿分支开始。
- **main / 其他分支**：历史研究存档，**与当前项目无关**，不向其合并、不从中引用代码。
- 功能/阶段开发直接在 VALOR-v1 上进行；若需并行，开 `feature/<phase>` 分支，合回 VALOR-v1。

## 2. 提交规范

### 提交信息格式
```
<type>(<scope>): <中文摘要>

<正文（可选）：说明改动动机与影响>
```

| type | 含义 |
|---|---|
| `feat` | 新功能/新阶段模块 |
| `fix` | 修复 bug |
| `refactor` | 重构（不改变行为） |
| `docs` | 文档（规范、冻结文档、报告） |
| `chore` | 构建/配置/依赖 |
| `test` | 测试 |
| `perf` | 性能优化 |

### 示例
```
feat(valuation): 实现 Data-VOI 的 LOO 与 Forward Influence 估值器 (RQ1)

- transaction_unit.py: candidate seller batch 定义与 point→batch 聚合
- economic_mapping.py: cost-sensitive payoff 经济映射 (D7)
- 覆盖 Phase 1 Gate：Oracle 可复现、Spearman/Kendall 可计算
```

## 3. 阶段提交策略（对应 Phase）

每个 Phase 完成并**通过其 Gate** 后，做一次原子提交。阶段间若 Gate 未过，不提交为"完成"，可先提交中间态但 message 明确标注 `WIP` 或 `[未过Gate]`。

```
Phase 0  →  feat(config): ... 骨架
Phase 1  →  feat(valuation): ... Data-VOI
Phase 1.5A → feat(calibration): primitive
Phase 1.5B → feat(calibration): action likelihood
Phase 2  →  feat(market): Algorithm 2
Phase 2.5 → feat(calibration): certification
Phase 3  →  feat(contract): Algorithm 3/4
Phase 4  →  feat(evaluation): 统计图表
```

## 4. 推送备份

- 每次阶段提交后 `git push origin VALOR-v1` 备份到远程。
- 推送前确认 `git status` 干净（或明确预期未跟踪文件，如机制文档）。
- 远程 `origin/VALOR-v1` 为唯一权威备份。

## 5. 复现与标记

- 每个可复现结果对应一个 commit；结果 JSON 内记录 `git_commit`。
- 里程碑用 tag：`v0.1.0`（Phase 0 完成）... `v1.0.0`（Phase 4 全部完成）。
- 冻结版机制文档（D20）用独立 tag 标记，如 `frozen-mechanism-v2`。

## 6. 禁止事项

- 不向 VALOR-v1 引入 main 分支的 DDTM 历史代码（G0/G1/ARUC/ZASA/JABO 等）。
- 不提交大文件/数据（见 ARCHIVE_SPEC §4）。
- 不提交含密钥的 `.env`。
- 不在未通过 Gate 时声称阶段完成。
