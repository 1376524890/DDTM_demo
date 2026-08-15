"""分布式质量审计层（规范 §16–§20 / Phase 2）。

- task_models:  TaskEnvelope T_a / AuditEvidence E_i / 节点承诺（§16）
- node_state:   auditor 节点状态（stake/availability/reliability）
- executor:     节点执行质量 primitive 并签名证据
- node_server:  FastAPI 独立节点服务（§17 HTTP 端点）
- client:       HTTP 客户端（派发任务/收集证据）
- scheduler:    委员会调度、离线重指派、证书形成
"""

from .task_models import AuditEvidence, TaskEnvelope
from .node_state import AuditorNode, NodeRegistry
from .client import AuditClient

# DistributedAuditScheduler 惰性导出（PEP 562）：避免循环导入
# （scheduler → market.reverse_vcg → market.committee_allocation → node_state）
_LAZY = {
    "DistributedAuditScheduler": (".scheduler", "DistributedAuditScheduler"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        mod, attr = _LAZY[name]
        obj = getattr(importlib.import_module(mod, __name__), attr)
        globals()[name] = obj
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AuditEvidence",
    "TaskEnvelope",
    "AuditorNode",
    "NodeRegistry",
    "AuditClient",
    "DistributedAuditScheduler",
]
