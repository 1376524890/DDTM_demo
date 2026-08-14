"""真实 HTTP 分布式质量审计测试（规范 §17/§20）。

拉起 7 个独立节点进程（f=2 → m=7, q=5），通过 HTTP 派发一次 committed
dataset 上的 structural 审计任务，验证 Reverse VCG 分配、BFT 证书与结果聚合。
"""

from __future__ import annotations

import pytest

from valor.core.hashing import content_hash
from valor.core.ids import AuditorID, TransactionID
from valor.data.download import load_dataset
from valor.data.preprocess import preprocess
from valor.data.split_roles import split_roles_four_way
from valor.data.transaction_batches import make_candidate_batches
from valor.distributed.node_state import AuditorNode, NodeRegistry
from valor.distributed.scheduler import DistributedAuditScheduler
from valor.distributed.spawn import spawn_nodes, teardown
from valor.distributed.task_models import TaskEnvelope


@pytest.fixture(scope="module")
def committed():
    handle = load_dataset("breast_cancer")
    X = preprocess(handle.X, fill_strategy="none")
    split = split_roles_four_way(
        X, handle.y, seed=0, base_train_frac=0.5,
        seller_pool_frac=0.3, valuation_validation_frac=0.1,
    )
    batch = make_candidate_batches(
        X, handle.y, seller_pool_idx=split.seller_pool_idx,
        n_batches=1, rows_per_batch=50, seed=0,
    )[0]
    return batch.X


def test_real_http_distributed_audit(committed):
    # 用 10 个节点（f=2 → m=7, q=5），删除任一 winner 后仍有替补委员会
    node_ids = [f"node-{i}" for i in range(10)]
    ports = list(range(8700, 8710))
    procs, data_path = spawn_nodes(
        committed_data=committed, node_ids=node_ids, ports=ports,
        env_overrides={"NODE_CAPABILITY": "structural"},
    )
    try:
        registry = NodeRegistry()
        endpoints = {}
        bids = {}
        for i, (nid, port) in enumerate(zip(node_ids, ports)):
            node = AuditorNode(
                node_id=AuditorID(nid), capability=("structural",),
                availability=1.0, stake=100.0 + i,
            )
            registry.register(node)
            endpoints[nid] = f"http://127.0.0.1:{port}"
            bids[AuditorID(nid)] = 10.0 + i

        task = TaskEnvelope(
            tx_id=TransactionID("tx-dist-http"),
            data_commitment=content_hash(committed.to_dict("list")),
            rights_commitment="c" * 64,
            algorithm_spec_hash=content_hash({"alg": "structural"}),
            param_manifest_hash=content_hash({}),
            execution_spec_hash=content_hash({"env": "py-3.14"}),
            deadline="2026-12-31",
        )
        scheduler = DistributedAuditScheduler(
            endpoints=endpoints, registry=registry, family="structural",
            f=2, bids=bids, eta_b=0.0, eta_o=0.0, seed=1,
        )
        result = scheduler.run(task)
        assert result["status"] == "CERTIFIED"
        assert result["m"] == 7 and result["q"] == 5
        assert result["cert_result"] in ("PASS", "QUALITY_FAIL")
        assert len(result["payments"]) == 7  # 委员会成员数 m
        assert result["p_safe"] == pytest.approx(1.0)
        assert result["p_live"] == pytest.approx(1.0)
    finally:
        teardown(procs)
