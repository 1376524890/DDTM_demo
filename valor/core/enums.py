"""VALOR 核心枚举类型。

对齐规范：
- §5.1 参数来源类型 ParamSource
- §8 交易状态 X∈{G,L,B}
- §43 终态 S_T 与持续 RightsState
- §14 质量实现类型 / 分布式迁移类
- §36 交付模式
"""

from __future__ import annotations

from enum import Enum


class ConfigMode(str, Enum):
    """配置/参数使用模式（检查单 B2）。

    决定 TEST_FIXTURE 来源是否被允许：
    - TEST：测试模式，允许 TEST_FIXTURE
    - EXPERIMENT / PRODUCTION：禁止 TEST_FIXTURE（规范 §5.3）
    """

    TEST = "TEST"
    EXPERIMENT = "EXPERIMENT"
    PRODUCTION = "PRODUCTION"


class ExecutionMode(str, Enum):
    """Formal execution mode for paper closure (Round 4, §21).

    TEST_FIXTURE may use in-process TestClient transports and fixture parameters.
    FORMAL_EXPERIMENT / PRODUCTION must use process-isolated HTTP auditor clusters,
    frozen market snapshots, node-local signing keys, and no scenario fallbacks.
    """

    TEST_FIXTURE = "TEST_FIXTURE"
    FORMAL_EXPERIMENT = "FORMAL_EXPERIMENT"
    PRODUCTION = "PRODUCTION"


class ParamSource(str, Enum):
    """ResolvedParameter 的允许来源类型（规范 §5.1）。

    任何核心参数必须来自下列之一；TEST_FIXTURE 仅允许用于测试 fixture，
    不得进入 experiment/production schema（规范 §5.3，检查单 B2 冻结）。
    """

    OBSERVED_DATA = "OBSERVED_DATA"  # 由观测数据得到
    CALIBRATED = "CALIBRATED"  # 由校准数据得到
    CONTRACT_INPUT = "CONTRACT_INPUT"  # 合同/配置显式输入
    MARKET_DISCOVERED = "MARKET_DISCOVERED"  # 市场发现（如节点 bid）
    OPTIMIZER_OUTPUT = "OPTIMIZER_OUTPUT"  # 优化器输出（如 m,q,rho）
    THREAT_SCENARIO = "THREAT_SCENARIO"  # 威胁场景 / 可验证上界
    STANDARD_CONSTANT = "STANDARD_CONSTANT"  # 标准常量（SHA-256、machine epsilon）
    TEST_FIXTURE = "TEST_FIXTURE"  # 测试夹具专用，禁止进入实验/生产


class TradeState(str, Enum):
    """三状态先验（规范 §8）：G=技术适配、L=诚实但适配不足、B=卖方违约。"""

    GOOD = "G"
    LOW_SUITABILITY = "L"
    BREACH = "B"


class TerminalState(str, Enum):
    """交易终态（规范 §43）。"""

    TRADE = "TRADE"
    NO_TRADE = "NO_TRADE"
    SELLER_BREACH = "SELLER_BREACH"
    BUYER_BREACH = "BUYER_BREACH"


class RightsState(str, Enum):
    """持续权利状态（规范 §43/§63）。TRADE 不表示权利生命周期结束。"""

    PROPOSED = "PROPOSED"
    RESERVED = "RESERVED"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CONSUMED = "CONSUMED"
    DELETION_PENDING = "DELETION_PENDING"
    DELETED_ATTESTED = "DELETED_ATTESTED"


class DeliveryMode(str, Enum):
    """三种交付模式（规范 §36）。"""

    DOWNLOAD_TRACEABLE = "DOWNLOAD_TRACEABLE"
    API_GATEWAY = "API_GATEWAY"
    COMPUTE_ONLY = "COMPUTE_ONLY"


class QualityImplementationKind(str, Enum):
    """质量 primitive 实现类型（规范 §14）。"""

    REFERENCE = "REFERENCE"  # 引用/锁定版本实现
    NATIVE = "NATIVE"  # 原生 Python 复现


class MigrationClass(str, Enum):
    """分布式迁移类（规范 §14）。"""

    MERGEABLE_EXACT = "MERGEABLE_EXACT"  # 计数类可用代数状态精确聚合
    GLOBAL_STATISTIC = "GLOBAL_STATISTIC"  # KS/MMD 需要全局统计
    MODEL_BASED_REPLICATED = "MODEL_BASED_REPLICATED"  # CL 等独立完整执行
    SECURE_EXECUTION_ONLY = "SECURE_EXECUTION_ONLY"  # 只能受控环境执行


class AuditDecision(str, Enum):
    """审计阶段决策（规范 §24）。"""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    TERMINATE = "TERMINATE"


class AuditOutcome(str, Enum):
    """分布式动作结果 Y（规范 §21.2）。"""

    PASS = "PASS"
    QUALITY_FAIL = "QUALITY_FAIL"
    BREACH_EVIDENCE = "BREACH_EVIDENCE"
