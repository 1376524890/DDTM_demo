"""分布式审计 HTTP 客户端（规范 §17）。

向独立节点服务派发任务、收集证据、发起 challenge。
"""

from __future__ import annotations

from typing import Any

import httpx

from .task_models import TaskEnvelope


class AuditClient:
    """与 auditor 节点交互的 HTTP 客户端。"""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    def health(self) -> dict:
        r = httpx.get(f"{self.base_url}/health", timeout=self._timeout, trust_env=False)
        r.raise_for_status()
        return r.json()

    def submit_task(self, task: TaskEnvelope) -> dict:
        r = httpx.post(
            f"{self.base_url}/audit/tasks",
            json=task.to_plain(),
            timeout=self._timeout,
            trust_env=False,
        )
        r.raise_for_status()
        return r.json()

    def get_evidence(self, evidence_id: str) -> dict:
        r = httpx.get(
            f"{self.base_url}/audit/evidence/{evidence_id}",
            timeout=self._timeout,
            trust_env=False,
        )
        r.raise_for_status()
        return r.json()

    def challenge(self, evidence_id: str) -> dict:
        r = httpx.post(
            f"{self.base_url}/challenge/{evidence_id}",
            timeout=self._timeout,
            trust_env=False,
        )
        r.raise_for_status()
        return r.json()
