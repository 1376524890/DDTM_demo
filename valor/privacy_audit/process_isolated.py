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
from dataclasses import dataclass, field

import httpx


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@dataclass(frozen=True)
class AuditRuntimeDescriptor:
    """Frozen descriptor for the audit execution runtime (Round 5 §4).

    FORMAL_EXPERIMENT must be PROCESS_HTTP + process-isolated + node-local Ed25519.
    """

    transport_mode: str  # TEST_FIXTURE | PROCESS_HTTP | PRODUCTION
    process_isolated: bool
    node_pids: dict[str, int] = field(default_factory=dict)
    node_public_keys: dict[str, str] = field(default_factory=dict)
    node_key_fingerprints: dict[str, str] = field(default_factory=dict)
    task_schema_hash: str = ""
    server_code_hash: str = ""
    environment_hash: str = ""

    def to_plain(self) -> dict:
        return {
            "transport_mode": self.transport_mode,
            "process_isolated": self.process_isolated,
            "node_pids": dict(self.node_pids),
            "node_public_keys": dict(self.node_public_keys),
            "node_key_fingerprints": dict(self.node_key_fingerprints),
            "task_schema_hash": self.task_schema_hash,
            "server_code_hash": self.server_code_hash,
            "environment_hash": self.environment_hash,
        }

    @classmethod
    def from_cluster(cls, cluster: "ProcessHttpAuditorCluster") -> "AuditRuntimeDescriptor":
        pool = cluster._pool
        from valor.core.hashing import content_hash

        return cls(
            transport_mode="PROCESS_HTTP",
            process_isolated=True,
            node_pids={nid: p.pid for nid, p in pool.procs.items()},
            node_public_keys=dict(cluster._registry._public_keys),
            node_key_fingerprints=dict(cluster._registry._fingerprints),
            task_schema_hash=content_hash({"schema": "PrivacyAuditTask-v1"}),
            server_code_hash=content_hash({"module": "valor.privacy_audit.server", "version": "v1"}),
            environment_hash=content_hash({
                "python": sys.version.split()[0],
                "cwd": str(Path(__file__).resolve().parent.parent.parent),
            }),
        )


def wait_health(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0, trust_env=False)
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

    def health(self) -> dict:
        r = httpx.get(f"{self.base}/health", timeout=5.0, trust_env=False)
        r.raise_for_status()
        return r.json()

    def public_key(self) -> str:
        return self.health().get("public_key", "")

    def key_fingerprint(self) -> str:
        return self.health().get("key_fingerprint", "")

    def submit_task(self, task):
        r = httpx.post(f"{self.base}/privacy/tasks", json=task.to_plain(),
                       timeout=10.0, trust_env=False)
        r.raise_for_status()
        return r.json()


class AuditorIdentityRegistry:
    """Scheduler-side registry of auditor public identities.

    Stores node_id -> public_key / key_fingerprint. The private key is created
    and held inside the auditor subprocess and never exposed to the scheduler.
    """

    def __init__(self) -> None:
        self._public_keys: dict[str, str] = {}
        self._fingerprints: dict[str, str] = {}

    def register(self, node_id: str, *, public_key: str, key_fingerprint: str) -> None:
        self._public_keys[node_id] = public_key
        self._fingerprints[node_id] = key_fingerprint

    def register_client(self, node_id: str, client: ProcessAuditorClient) -> None:
        self.register(node_id, public_key=client.public_key(),
                      key_fingerprint=client.key_fingerprint())

    def public_key(self, node_id: str) -> str:
        if node_id not in self._public_keys:
            raise KeyError(f"AUDITOR_IDENTITY_MISSING: {node_id}")
        return self._public_keys[node_id]

    def key_fingerprint(self, node_id: str) -> str:
        if node_id not in self._fingerprints:
            raise KeyError(f"AUDITOR_IDENTITY_MISSING: {node_id}")
        return self._fingerprints[node_id]

    def public_keys(self) -> dict[str, str]:
        return dict(self._public_keys)

    def to_plain(self) -> dict:
        return {
            "public_keys": dict(self._public_keys),
            "key_fingerprints": dict(self._fingerprints),
        }


class ProcessHttpAuditorCluster:
    """Formal process-isolated auditor cluster used by FORMAL_EXPERIMENT/PRODUCTION.

    Each auditor is a real subprocess (independent PID) exposing FastAPI/HTTP.
    The scheduler only sends PrivacyAuditTask (commitment + claim + challenge +
    openings + action metadata); never seller_store or full X/y. Each auditor
    creates its Ed25519 key locally and returns signed evidence.
    """

    def __init__(self, n: int, *, node_prefix: str = "node-") -> None:
        self._pool = ProcessAuditorPool(n=n, node_prefix=node_prefix)
        self._registry = AuditorIdentityRegistry()
        for nid, client in self._pool._clients.items():
            self._registry.register_client(nid, client)

    @property
    def registry(self) -> AuditorIdentityRegistry:
        return self._registry

    def client_factory(self) -> Callable[[str], ProcessAuditorClient]:
        return self._pool.client_factory()

    def close(self) -> None:
        self._pool.close()

    def __enter__(self) -> "ProcessHttpAuditorCluster":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


__all__ = [
    "free_port", "wait_health", "spawn_auditor_process",
    "ProcessAuditorPool", "ProcessAuditorClient",
    "AuditorIdentityRegistry", "ProcessHttpAuditorCluster",
]
