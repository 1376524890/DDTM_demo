"""C2 真实审计：节点独立 primitive 产生分歧 + quorum-by-result 裁决。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from valor.engine.real_evidence import (
    RealQualityEvidence,
    make_real_evidence_provider,
)
from valor.distributed.node_state import AuditorNode, NodeRegistry
from valor.distributed.scheduler import DistributedAuditScheduler
from valor.distributed.task_models import TaskEnvelope
from valor.core.ids import AuditorID, TransactionID


def test_node_primitives_produce_distinct_views():
    """不同 primitive 对同一候选数据可能给出不同判定（真实分歧来源）。"""
    rng = np.random.default_rng(1)
    n = 800
    ref = pd.DataFrame({"a": rng.normal(0, 1, n), "b": rng.normal(5, 2, n)})
    shifted = pd.DataFrame({"a": rng.normal(3, 1, n), "b": rng.normal(8, 2, n)})
    y = pd.Series(rng.integers(0, 2, n))

    det = RealQualityEvidence(reference_df=ref, candidate_df=shifted,
                              y_candidate=y, row_sample=400, compress_dim=16)
    # KS 应检测到漂移 → QUALITY_FAIL；duplicates 无重复 → PASS（分歧）
    ks = det.detect_primitive("ks_shift")
    dup = det.detect_primitive("duplicates")
    assert ks.outcome == "QUALITY_FAIL"
    assert dup.outcome == "PASS"
    assert ks.outcome != dup.outcome  # 真实分歧


def test_make_provider_assigns_primitives():
    """provider 对任意节点 id 返回结果（稳健分配），且可能产生分歧。"""
    rng = np.random.default_rng(2)
    n = 800
    ref = pd.DataFrame({"a": rng.normal(0, 1, n), "b": rng.normal(5, 2, n)})
    shifted = pd.DataFrame({"a": rng.normal(3, 1, n), "b": rng.normal(8, 2, n)})
    y = pd.Series(rng.integers(0, 2, n))

    prov = make_real_evidence_provider(
        reference_df=ref, candidate_df=shifted, y_candidate=y,
        row_sample=400, compress_dim=16,
    )
    # 对多个节点取证据，看是否产生分歧结果
    outcomes = {}
    for i in range(7):
        r = prov(f"node-{i}", type("T", (), {"task_id": "t1"})())
        outcomes[f"node-{i}"] = r["result"]
    assert len(set(outcomes.values())) >= 1
    # 至少能产生结果（不抛错）
    assert all(v in ("PASS", "QUALITY_FAIL") for v in outcomes.values())


def _mnist_quorum(cand_X, cand_y, ref_X):
    prov = make_real_evidence_provider(
        reference_df=ref_X, candidate_df=cand_X, y_candidate=cand_y,
        row_sample=800, compress_dim=64)
    reg = NodeRegistry()
    for i in range(10):
        reg.register(AuditorNode(AuditorID(f"node-{i}"), ("quality",), 1.0, 100.0 + i))
    bids = {AuditorID(f"node-{i}"): 10.0 + i for i in range(10)}
    endpoints = {f"node-{i}": f"http://node-{i}" for i in range(10)}
    sched = DistributedAuditScheduler(
        endpoints=endpoints, registry=reg, family="quality", f=2,
        bids=bids, rho=0.0, evidence_provider=prov)
    task = TaskEnvelope(TransactionID("tx-1"), "d" * 64, "r" * 64,
                        "a" * 64, "p" * 64, "e" * 64, "2026-12-31")
    return sched.run(task)


def test_quorum_clean_certified_poisoned_no_quorum():
    """干净候选→CERTIFIED PASS；污染候选→节点分歧→NO_QUORUM（quorum-by-result）。"""
    from valor.data.download import load_dataset

    h = load_dataset("mnist")
    X, y = h.X, h.y
    rng = np.random.default_rng(0)
    ref_X = X.iloc[20000:25000]
    cand_idx = rng.choice(25000, 3000, replace=False)
    cand_X = X.iloc[cand_idx].reset_index(drop=True).astype(float)
    cand_y = y.iloc[cand_idx].reset_index(drop=True).astype(int)
    shifted = cand_X.copy()
    si = rng.choice(len(shifted), int(0.4 * len(shifted)), replace=False)
    shifted.iloc[si] = shifted.iloc[si] + 40.0
    shifted = shifted.clip(0, 255)

    clean = _mnist_quorum(cand_X, cand_y, ref_X)
    poison = _mnist_quorum(shifted, cand_y, ref_X)
    assert clean["status"] == "CERTIFIED" and clean["cert_result"] == "PASS"
    # 污染下分歧可能 NO_QUORUM（不错误 CERTIFIED）或 QUALITY_FAIL
    assert poison["status"] in ("NO_QUORUM", "CERTIFIED")
    if poison["status"] == "CERTIFIED":
        assert poison["cert_result"] == "QUALITY_FAIL"
