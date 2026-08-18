"""Process-isolated privacy auditor pool (P0-G).

Each auditor is a real subprocess exposing FastAPI endpoints. The pool only
sends PrivacyAuditTask (commitment/claim/challenge/openings) and never the full
dataset. This is process isolation, not hardware confidential computing.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import httpx


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def wait_health(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise TimeoutError("privacy auditor not ready")


def spawn_auditor_process(node_id: str, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent.parent)
    code = (
        "from valor.privacy_audit.server import serve_privacy;"
        "from valor.privacy_audit.verifier import CommitChallengeVerifier;"
        "from valor.security.signing import SigningKeyPair;"
        f"kp=SigningKeyPair.generate('{node_id}');"
        "serve_privacy(CommitChallengeVerifier("
        f"'{node_id}', signing_key=kp), {port})"
    )
    return subprocess.Popen(
        [sys.executable, "-c", code], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


class ProcessAuditorPool:
    """Spawn and manage m >= 3f+1 auditor processes."""

    def __init__(self, n: int, *, node_prefix: str = "node-") -> None:
        self.n = n
        self.node_prefix = node_prefix
        self.procs: dict[str, subprocess.Popen] = {}
        self.ports: dict[str, int] = {}
        self._clients: dict[str, "ProcessAuditorClient"] = {}
        for i in range(n):
            nid = f"{node_prefix}{i}"
            port = free_port()
            proc = spawn_auditor_process(nid, port)
            self.procs[nid] = proc
            self.ports[nid] = port
            self._clients[nid] = ProcessAuditorClient(port, nid)
        for nid in self.procs:
            wait_health(self.ports[nid])

    def client_factory(self) -> Callable[[str], "ProcessAuditorClient"]:
        def factory(node_id: str) -> "ProcessAuditorClient":
            nid = str(node_id)
            if nid not in self._clients:
                raise KeyError(f"unknown auditor {nid}")
            return self._clients[nid]
        return factory

    def close(self) -> None:
        for proc in self.procs.values():
            proc.terminate()
        for proc in self.procs.values():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def __enter__(self) -> "ProcessAuditorPool":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class ProcessAuditorClient:
    def __init__(self, port: int, node_id: str) -> None:
        self.port = port
        self.node_id = node_id
        self.base = f"http://127.0.0.1:{port}"

    def submit_task(self, task):
        r = httpx.post(f"{self.base}/privacy/tasks", json=task.to_plain(),
                       timeout=10.0)
        r.raise_for_status()
        return r.json()


__all__ = [
    "free_port", "wait_health", "spawn_auditor_process",
    "ProcessAuditorPool", "ProcessAuditorClient",
]
