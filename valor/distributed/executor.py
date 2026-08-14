"""节点执行器：在隔离环境运行质量 primitive 并签名证据（规范 §16）。

节点收到 TaskEnvelope + 数据访问句柄，运行对应 primitive，生成 execution_hash
= H(输出 ∥ 数据承诺 ∥ 算法spec)，产出 AuditEvidence。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import pandas as pd

from valor.core.hashing import stable_hash

from .node_state import AuditorNode
from .task_models import AuditEvidence, TaskEnvelope

# primitive 执行器：接收数据 → 返回 {metrics, result} 的 dict
PrimitiveRunner = Callable[[pd.DataFrame], dict]


class NodeExecutor:
    """在单个节点内执行审计任务。"""

    def __init__(self, node: AuditorNode, runner: PrimitiveRunner,
                 decision_fn: Callable[[dict], str]) -> None:
        self.node = node
        self.runner = runner
        self.decision_fn = decision_fn

    def execute(self, task: TaskEnvelope, data: pd.DataFrame) -> AuditEvidence:
        """执行任务，校验承诺，产出并返回证据。"""
        # 校验节点数据承诺与任务一致（§16 H(D_node)=H(D)_τ）
        from valor.core.hashing import content_hash

        data_commit = content_hash(data.to_dict("list"))
        if data_commit != task.data_commitment:
            from valor.core.errors import CommitBindingError

            raise CommitBindingError(
                f"[节点 {self.node.node_id}] 数据承诺与任务不一致"
            )
        out = self.runner(data)
        result = self.decision_fn(out)
        execution_hash = stable_hash(
            out, task.data_commitment, task.algorithm_spec_hash
        )
        return AuditEvidence(
            node_id=self.node.node_id,
            task=task,
            result=result,
            raw_metrics=out,
            execution_hash=execution_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
