"""PrivacyAuditClient —— 隐私审计 HTTP 客户端（PPA-4）。"""

from __future__ import annotations

import httpx

from .task import PrivacyAuditTask


class PrivacyAuditClient:
    """与隐私审计节点交互（只传 task，不传全量数据）。"""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout

    def health(self) -> dict:
        r = httpx.get(f"{self.base_url}/health", timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def submit_task(self, task: PrivacyAuditTask) -> dict:
        r = httpx.post(
            f"{self.base_url}/privacy/tasks",
            json=task.to_plain(), timeout=self._timeout,
        )
        r.raise_for_status()
        return r.json()

    def auditor_has_no_full_data(self) -> bool:
        r = httpx.get(f"{self.base_url}/privacy/auditor_has_no_full_data",
                      timeout=self._timeout)
        r.raise_for_status()
        return not r.json()["has_full_data"]


__all__ = ["PrivacyAuditClient"]
