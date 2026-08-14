"""VALOR：权利感知、质量可验证与用途可审计的数据交易原型系统。

以冻结版规范《VALOR_可实施原型系统_完整数学代码闭环与开发规范.md》为唯一设计依据。
本包从零实现，不参考任何 DDTM 历史代码。

主链（规范 §1/§77）：
    Entitlement
    → QualityReference
    → DistributedQualityAudit
    → V̲_{D,R}^{gross}
    → Π_A^*
    → p̲_B^{sys}
    → B_S^*
    → (P_τ^{min},P_τ^{max})
    → P_τ^*
    → UsageControl
    → S_T
    → Θ_{t+1}

包结构（规范 §53）：
- core/       枚举、货币、哈希、canonical JSON、错误、ID（Phase 0）
- params/     ResolvedParameter 参数溯源 + fail-closed 解析（Phase 0）
- asset/      数据资产 / 版本 / 承诺 / 资格 / 合规（Phase 0）
- rights/     权利束 / ODRL / 注册表 / 兼容 / 支配 / 机会成本（Phase 0）
- quality/    质量 primitive（reference/native/calibration）+ 复现 Gate
- distributed/ 分布式审计节点（独立进程/容器 + HTTP）
- market/     反向 VCG / 委员会分配 / 支付
- security/   BFT / liveness / challenge / slashing / certification
- audit/      Bayes 风险 / Audit-VOI / 动作目录 / 策略
- valuation/  Data-VOI / 估值器 / 校准
- liability/  卖方保证金 / pre-lock / 买方 usage bond / 资本成本
- pricing/    买卖双方价格边界 / 结算 / rights menu
- execution/  delivery / api_gateway / compute_only / secure_valuation
- usage/      PDP/PEP/PIP/PXP / receipt / fingerprint / misuse
- lineage/    Data Flow Graph / hash chain / OpenLineage 映射
- contract/   账户 / escrow / 状态机 / 结算
- feedback/   证据资格门 / 贝叶斯反馈
- evaluation/ 指标 / 效用 / 福利 / oracle / 实验
- simulation/ 参与方 / 网络 / 交易 / 场景
- cli.py      CLI 契约（规范 §71）
"""

__version__ = "0.2.0"
