"""独立 auditor 节点服务（规范 §17）。

每个节点是独立 OS 进程/容器，通过 HTTP 传输任务和证据。至少暴露：
    GET  /health
    POST /audit/tasks
    GET  /audit/tasks/{task_id}
    GET  /audit/evidence/{evidence_id}
    POST /challenge/{evidence_id}

节点读取只读共享对象存储中的 committed dataset，执行 primitive 并签名证据。
"""

from __future__ import annotations

import os
import pickle
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException

from .executor import NodeExecutor
from .task_models import AuditEvidence, TaskEnvelope


def create_app(executor: NodeExecutor, committed_data: pd.DataFrame) -> FastAPI:
    """构造 FastAPI 应用。"""
    app = FastAPI(title=f"VALOR auditor node {executor.node.node_id}")
    _evidence_store: dict[str, AuditEvidence] = {}

    @app.get("/health")
    def health() -> dict:
        return {"node_id": str(executor.node.node_id), "status": "ok"}

    @app.post("/audit/tasks")
    def submit_task(payload: dict) -> dict:
        task = _task_from_payload(payload)
        evidence = executor.execute(task, committed_data)
        _evidence_store[evidence.evidence_id] = evidence
        return {"evidence_id": evidence.evidence_id, "result": evidence.result}

    @app.get("/audit/tasks/{task_id}")
    def get_task(task_id: str) -> dict:
        for ev in _evidence_store.values():
            if ev.task.task_id == task_id:
                return ev.task.to_plain()
        raise HTTPException(status_code=404, detail="task not found")

    @app.get("/audit/evidence/{evidence_id}")
    def get_evidence(evidence_id: str) -> dict:
        ev = _evidence_store.get(evidence_id)
        if ev is None:
            raise HTTPException(status_code=404, detail="evidence not found")
        return ev.to_plain()

    @app.post("/challenge/{evidence_id}")
    def challenge(evidence_id: str) -> dict:
        """强验证：重新执行并比对 execution_hash（§19）。"""
        ev = _evidence_store.get(evidence_id)
        if ev is None:
            raise HTTPException(status_code=404, detail="evidence not found")
        rerun = executor.execute(ev.task, committed_data)
        honest = rerun.execution_hash == ev.execution_hash
        return {"evidence_id": evidence_id, "challenge_passed": honest,
                "result": rerun.result}
    return app


def _task_from_payload(payload: dict) -> TaskEnvelope:
    from valor.core.ids import TransactionID

    return TaskEnvelope(
        tx_id=TransactionID(payload["tx_id"]),
        data_commitment=payload["data_commitment"],
        rights_commitment=payload.get("rights_commitment", ""),
        algorithm_spec_hash=payload["algorithm_spec_hash"],
        param_manifest_hash=payload.get("param_manifest_hash", ""),
        execution_spec_hash=payload.get("execution_spec_hash", ""),
        deadline=payload.get("deadline", ""),
    )


def serve(executor: NodeExecutor, committed_data: pd.DataFrame, port: int) -> None:
    """启动节点服务（独立进程入口）。"""
    import uvicorn

    app = create_app(executor, committed_data)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
