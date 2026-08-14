# VALOR 版本控制规范（VERSION_CONTROL_SPEC）

> 唯一 normative source：`VALOR_可实施原型系统_完整数学代码闭环与开发规范.md`。
> 本文件定义分支策略、提交规范、阶段门禁与发布要求。

## 1. 分支策略

- 主开发分支：`VALOR-v1`（空孤儿分支初始化，按规范从零实现）。
- 每个实现 Phase（规范 §70 Phase 0–8）在 `VALOR-v1` 上按顺序提交。
- 禁止把其他分支的旧实现（DDTM 历史代码）合入本分支。
- 规范文档本身作为唯一设计依据，随仓库版本冻结（D20 回写机制）。

## 2. 提交规范（Conventional Commits + 中文说明）

格式：`<type>(<scope>): <subject>`，`subject` 用中文，正文用中文。

| type | 用途 |
|---|---|
| `feat` | 新增功能/模块 |
| `fix` | 修复缺陷 |
| `test` | 新增/修改测试 |
| `docs` | 文档（ARCHIVE/VERSION/DESIGN/README） |
| `build`/`chore` | 构建、依赖、目录归档 |
| `refactor` | 重构，不改行为 |

示例：
```
feat(core): 新增 canonical JSON 与哈希链基础工具
test(params): 空业务配置 fail-closed 单测
docs: 建立目录归档与版本控制规范
```

## 3. 阶段门禁（Phase Gate，对齐规范 §69 工程 Gate）

每个 Phase 只有对应 Gate 通过、且测试全绿后，才能合并进入下一 Phase：

- **Gate A（参数溯源）**：核心算法无业务默认值；RequiredParameter 全可解析；unit checker 通过；config hash 可复现。
- Phase 0 验收：空业务配置不能运行 transaction；所有核心 dataclass 可序列化、canonicalize、hash。

## 4. 提交粒度

- 一个 Phase 拆分为多个逻辑 commit（core → params → asset → rights → configs → tests），每个 commit 可独立运行测试。
- 目录/归档变更（docs、.gitignore、pyproject）作为独立 commit。
- 禁止 `--no-verify` 绕过测试；提交前运行 `pytest`。

## 5. 发布 / 回写

- 阶段完成时在 `docs/DESIGN_DECISIONS.md` 记录设计决策与规范对照（D 编号续接）。
- 任何对规范实现方式的取舍，必须记录决策及其规范依据，禁止静默偏离。
