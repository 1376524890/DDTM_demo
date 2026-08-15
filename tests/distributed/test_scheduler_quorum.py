"""P4 DistributedAuditScheduler quorum-by-result / replacement 测试。

用假的 HTTP 端点（stub client）验证：
- 同一结果 ≥ q 个一致 evidence 才 CERTIFIED（不是 evidence_count >= q）
- 结果分散 → NO_QUORUM
- 离线节点被备用池替换
"""

from __future__ import annotations

import pytest

from valor.core.hashing import content_hash
from valor.core.ids import AuditorID, TransactionID
from valor.distributed.node_state import AuditorNode, NodeRegistry
from valor.distributed.scheduler import DistributedAuditScheduler
from valor.distributed.task_models import TaskEnvelope


def _task():
    return TaskEnvelope(
        tx_id=TransactionID("tx-quorum"),
        data_commitment="d" * 64, rights_commitment="c" * 64,
        algorithm_spec_hash="a" * 64, param_manifest_hash="p" * 64,
        execution_spec_hash="e" * 64, deadline="2026-12-31",
    )


def _registry(n_nodes=8, f=2):
    reg = NodeRegistry()
    for i in range(n_nodes):
        reg.register(AuditorNode(
            node_id=AuditorID(f"node-{i}"), capability=("quality",),
            availability=1.0, stake=100.0 + i,
        ))
    return reg


class _StubClient:
    """stub HTTP 客户端：每个节点固定返回预设结果。"""

    def __init__(self, results: dict, challenge_ok=True, fail_nodes=()):
        self.results = results
        self.challenge_ok = challenge_ok
        self.fail_nodes = set(fail_nodes)

    def __call__(self, url, timeout=10.0):
        node_id = url.rstrip("/").split("/")[-1]
        if node_id in self.fail_nodes:
            raise ConnectionError("offline")
        return _NodeStub(self.results.get(node_id, "PASS"), self.challenge_ok)


class _NodeStub:
    def __init__(self, result, challenge_ok):
        self.result = result
        self.challenge_ok = challenge_ok

    def submit_task(self, task):
        return {"evidence_id": f"evt-{task.task_id}", "result": self.result}

    def challenge(self, evidence_id):
        return {"evidence_id": evidence_id, "challenge_passed": self.challenge_ok,
                "result": self.result}


def _make_scheduler(results, registry=None, f=2, rho=1.0, fail_nodes=()):
    reg = registry or _registry(f=f)
    endpoints = {}
    bids = {}
    for i, n in enumerate(reg.all()):
        nid = str(n.node_id)
        endpoints[nid] = f"http://node/{nid}"
        bids[AuditorID(nid)] = 10.0 + i
    sched = DistributedAuditScheduler(
        endpoints=endpoints, registry=reg, family="quality", f=f,
        bids=bids, rho=rho, seed=0,
    )
    return sched


def _monkey_patch_client(sched, results, fail_nodes=()):
    import valor.distributed.scheduler as sched_mod

    stub = _StubClient(results, challenge_ok=True, fail_nodes=fail_nodes)
    sched_mod.AuditClient = stub
    return stub


def test_quorum_by_result_requires_same_result_q():
    # f=2 → q=5；7 个一致 PASS + 1 个 QUALITY_FAIL → 仍 CERTIFIED(PASS)
    reg = _registry(8, f=2)
    results = {f"node-{i}": "PASS" for i in range(7)}
    results["node-7"] = "QUALITY_FAIL"
    sched = _make_scheduler(results, registry=reg, f=2, rho=0.0)
    _monkey_patch_client(sched, results)
    out = sched.run(_task())
    assert out["status"] == "CERTIFIED"
    assert out["cert_result"] == "PASS"


def test_no_quorum_when_result_split():
    # f=2 → q=5；结果 4 PASS + 3 QUALITY_FAIL → 无结果达 q → NO_QUORUM
    reg = _registry(8, f=2)
    results = {f"node-{i}": "PASS" for i in range(4)}
    for i in range(4, 8):
        results[f"node-{i}"] = "QUALITY_FAIL"
    sched = _make_scheduler(results, registry=reg, f=2, rho=0.0)
    _monkey_patch_client(sched, results)
    out = sched.run(_task())
    assert out["status"] == "NO_QUORUM"
    assert "quorum-by-result" in out.get("reason", "")


def test_offline_replacement():
    # 委员会 7 个节点，其中 2 个离线 → 从备用池替换后仍 CERTIFIED
    reg = _registry(9, f=2)
    results = {f"node-{i}": "PASS" for i in range(9)}
    fail_nodes = ("node-0", "node-1")  # 这两个可能进委员会
    sched = _make_scheduler(results, registry=reg, f=2, rho=0.0,
                            fail_nodes=fail_nodes)
    stub = _monkey_patch_client(sched, results, fail_nodes=fail_nodes)
    out = sched.run(_task())
    # 只要替换成功，最终证据数 >= q
    assert out["evidence_count"] >= 5
    assert out["status"] == "CERTIFIED"
