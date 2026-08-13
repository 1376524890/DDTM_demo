"""VALOR-v1：双层信息价值数据交易闭环机制实现与实验代码包。

以冻结版机制文档为唯一设计依据（D20），不参考任何 DDTM 历史代码。
设计决策见 docs/DESIGN_DECISIONS.md（D1-D20）。

包结构（对齐机制文档 §31 + 评审修订）：
- calibration/   三级似然 + 认证（D1/D2/D19）
- valuation/     Data-VOI（RQ1）
- audit/         Audit-VOI（RQ2）
- market/        反向审计市场（RQ3）
- security/      节点安全（BFT/challenge/slashing/liveness）
- contract/      合同与结算（RQ4-6）
- feedback/      贝叶斯反馈闭环（含证据资格门 D18）
- evaluation/    实验评估（oracle/utilities/welfare/metrics/statistics）
- data/          数据管线
"""

__version__ = "0.1.0"
