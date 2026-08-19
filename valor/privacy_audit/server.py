"""PrivacyNodeServer —— 隐私审计节点服务（PPA-4）。

关键：**不接收 committed_data**。节点只接收 PrivacyAuditTask（commitment/claim/
challenge/openings），在内存中验证 k 行 openings，产出 PrivacyAuditEvidence。

这从架构上保证 auditor 文件系统/内存中不存在全量数据集。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .evidence import PrivacyAuditEvidence
from .task import PrivacyAuditTask
from .verifier import AuditExecutionContext, CommitChallengeVerifier


def create_privacy_app(verifier: CommitChallengeVerifier) -> FastAPI:
    """构造隐私审计节点 FastAPI 应用（无 committed_data 参数）。"""
    app = FastAPI(title=f"VALOR privacy auditor {verifier.node_id}")
    _evidence: dict[str, dict] = {}

    @app.get("/health")
    def health() -> dict:
        pk = ""
        fp = ""
        if verifier.signing_key is not None:
            pk = verifier.signing_key.public_key_hex
            fp = verifier.signing_key.key_fingerprint
        return {
            "node_id": verifier.node_id,
            "status": "ok",
            "mode": "COMMIT_CHALLENGE",
            "public_key": pk,
            "key_fingerprint": fp,
            "private_key_in_child": verifier.signing_key is not None,
        }

    @app.post("/privacy/tasks")
    def submit_privacy_task(payload: dict) -> dict:
        task = PrivacyAuditTask.from_plain(payload)
        ctx = AuditExecutionContext(
            commitment=task.commitment, claim=task.claim,
            challenge=task.challenge, openings=task.openings,
        )
        ev: PrivacyAuditEvidence = verifier.execute(
            task_binding_hash=task.task_binding_hash,
            primitive_id=task.primitive_id, ctx=ctx)
        _evidence[ev.evidence_id] = ev.to_plain()
        return ev.to_plain()

    @app.get("/privacy/evidence/{evidence_id}")
    def get_evidence(evidence_id: str) -> dict:
        if evidence_id not in _evidence:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="evidence not found")
        return _evidence[evidence_id]

    @app.get("/privacy/auditor_has_no_full_data")
    def auditor_has_no_full_data() -> dict:
        """验收：auditor 节点不持有全量数据（PP-AUDIT-G01）。"""
        return {"node_id": verifier.node_id, "has_full_data": False}

    return app


def serve_privacy(verifier: CommitChallengeVerifier, port: int) -> None:
    import uvicorn

    app = create_privacy_app(verifier)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


__all__ = ["create_privacy_app", "serve_privacy"]
