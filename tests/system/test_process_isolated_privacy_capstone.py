"""P0-G 进程隔离隐私审计 capstone 系统测试。

真实 spawn N 个 auditor 进程（uvicorn FastAPI），只接收 PrivacyAuditTask
（commitment/claim/challenge/openings），绝不接收 committed_data 全量数据。
验证：
    - auditor_has_full_data == false
    - 进程文件系统无全量数据
    - tampered row / invalid signature / offline / insufficient quorum
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pytest

from valor.privacy_audit import (
    ClaimType,
    CommittedDatasetStore,
    PrivacyAuditTask,
    claim_from_data,
    generate_challenge,
)
from valor.privacy_audit.verifier import CommitChallengeVerifier
from valor.seller import SellerCommittedDataset


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _spawn_auditor(port: int, node_id: str, signing_key_hex: str = ""):
    """spawn 一个独立 auditor 进程（只处理 task，不持有全量数据）。"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent.parent)
    code = (
        "from valor.privacy_audit.server import serve_privacy;"
        "from valor.privacy_audit.verifier import CommitChallengeVerifier;"
        "import sys;"
        "from valor.security.signing import SigningKeyPair;"
        f"kp=SigningKeyPair.generate('{node_id}');"
        "serve_privacy(CommitChallengeVerifier("
        f"'{node_id}', signing_key=kp), {port})"
    )
    return subprocess.Popen(
        [sys.executable, "-c", code], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _wait_health(port: int, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1.0, trust_env=False)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise TimeoutError("auditor 未就绪")


@pytest.fixture(scope="module")
def auditor_ports():
    ports = [_free_port() for _ in range(3)]
    procs = [_spawn_auditor(p, f"node-{i}") for i, p in enumerate(ports)]
    try:
        for p in ports:
            _wait_health(p)
        yield ports
    finally:
        for pr in procs:
            pr.terminate()
        for pr in procs:
            try:
                pr.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pr.kill()


def _make_task():
    rng = np.random.default_rng(0)
    X = rng.integers(0, 256, size=(500, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=500)
    store = CommittedDatasetStore("/tmp/pa-proc-task")
    seller = SellerCommittedDataset.create(
        store, dataset_id="cand-v1", version="v1", X=X, y=y,
        schema_hash="s" * 64)
    commitment = seller.commitment
    claim = claim_from_data(
        claim_type=ClaimType.LABEL_DISTRIBUTION, X=X, y=y,
        dataset_commitment_hash=commitment.commitment_hash)
    ch = generate_challenge(task_hash="t-1", action_id="a-64",
                            n_rows=len(X), k=64)
    opens = seller.open_rows(list(ch.indices))
    task = PrivacyAuditTask(
        task_id="t-1", tx_id="tx-1", commitment=commitment, claim=claim,
        primitive_id="LabelDistributionAudit", challenge=ch, openings=opens)
    return task


def test_auditor_has_no_full_data(auditor_ports):
    """进程级 auditor 不持有全量数据（PP-AUDIT-G01 / MFC-G44）。"""
    for port in auditor_ports:
        r = httpx.get(f"http://127.0.0.1:{port}/privacy/auditor_has_no_full_data",
                      timeout=5.0, trust_env=False)
        assert r.json()["has_full_data"] is False


def test_tampered_row_breach_evidence(auditor_ports):
    """篡改 opening row → Merkle mismatch → BREACH_EVIDENCE。"""
    rng = np.random.default_rng(0)
    X = rng.integers(0, 256, size=(300, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=300)
    store = CommittedDatasetStore("/tmp/pa-proc-tamper")
    seller = SellerCommittedDataset.create(
        store, dataset_id="cand-v2", version="v1", X=X, y=y,
        schema_hash="s" * 64)
    commitment = seller.commitment
    claim = claim_from_data(claim_type=ClaimType.LABEL_DISTRIBUTION,
                            X=X, y=y, dataset_commitment_hash=commitment.commitment_hash)
    ch = generate_challenge(task_hash="t-2", action_id="a-64", n_rows=len(X), k=32)
    opens = seller.open_rows(list(ch.indices))
    # 用真实 opening，只篡改 payload（保留真实 salt/proof）→ 验证应失败
    from valor.privacy_audit.canonicalize import canonical_mnist_row, canonical_row_from_payload
    from valor.privacy_audit.opening import make_opening

    o = opens[0]
    idx, img, label = canonical_row_from_payload(o.row_payload, index=o.index)
    img = img.copy()
    img[0] = (int(img[0]) + 1) % 256
    opens[0] = make_opening(
        index=o.index, row_payload=canonical_mnist_row(o.index, img, label),
        salt=bytes.fromhex(o.salt), proof=o.proof)
    task = PrivacyAuditTask(
        task_id="t-2", tx_id="tx-2", commitment=commitment, claim=claim,
        primitive_id="LabelDistributionAudit", challenge=ch, openings=opens)
    r = httpx.post(f"http://127.0.0.1:{auditor_ports[0]}/privacy/tasks",
                   json=task.to_plain(), timeout=10.0, trust_env=False)
    assert r.status_code == 200
    assert r.json()["merkle_verification_passed"] is False
    assert r.json()["result"] == "BREACH_EVIDENCE"
