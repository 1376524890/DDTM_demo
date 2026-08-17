"""隐私审计接入完整 capstone：COMMIT_CHALLENGE 作为审计执行层。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine import CapstoneScenario, TransactionOrchestrator
from valor.privacy_audit import (
    ClaimType,
    CommitChallengeVerifier,
    create_privacy_app,
)
from valor.privacy_audit.executor_adapter import make_privacy_audit_executor
from fastapi.testclient import TestClient


def _client_factory(n=10):
    clients = {f"node-{i}": TestClient(
        create_privacy_app(CommitChallengeVerifier(f"node-{i}")))
        for i in range(n)}

    class _A:
        def __init__(self, tc): self._tc = tc
        def submit_task(self, task):
            r = self._tc.post("/privacy/tasks", json=task.to_plain())
            r.raise_for_status()
            return r.json()

    return lambda nid: _A(clients[str(nid)])


def test_capstone_with_privacy_audit(tmp_path):
    """完整交易用 COMMIT_CHALLENGE 审计执行层跑通，披露受限。"""
    sc = CapstoneScenario(scenario_id="pa-cap", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    # 隐私预算（P0-H：AuditDisclosureBudget，显式 rows/fraction/bytes）
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 200, "max_fraction": 0.3, "max_bytes": 200 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 200
    sc.rights["audit_reveal_max_fraction"] = 0.3
    sc.rights["audit_reveal_max_bytes"] = 200 * 784

    pa_executor = make_privacy_audit_executor(
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[32, 64], n_nodes=10, f=2,
        seller_store=__import__("valor.privacy_audit.commitment",
                                fromlist=["CommittedDatasetStore"])
        .CommittedDatasetStore(str(tmp_path / "seller_private")),
        node_client_factory=_client_factory(),
    )
    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "runs"),
                                   audit_executor=pa_executor)
    res = orch.run()
    audit = orch._stages["audit"].output
    assert audit["execution_mode"] == "COMMIT_CHALLENGE"
    assert audit["unique_disclosure"] <= 200  # 披露受限
    # 审计 action 的 VCG 进 MC_A^pay
    for a in audit["audit_trace_events"]:
        assert a["mc_a_pay"] > 0
    # 后验已更新
    assert audit["posterior"] is not None


def test_privacy_audit_disclosure_fraction(tmp_path):
    """披露比例记录在审计 stage。"""
    sc = CapstoneScenario(scenario_id="pa-cap2", seller_id="s", buyer_id="b")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 100, "max_fraction": 0.2, "max_bytes": 100 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 100
    sc.rights["audit_reveal_max_fraction"] = 0.2
    sc.rights["audit_reveal_max_bytes"] = 100 * 784

    pa_executor = make_privacy_audit_executor(
        claim_type=ClaimType.LABEL_DISTRIBUTION,
        challenge_sizes=[32], n_nodes=10, f=2,
        seller_store=__import__("valor.privacy_audit.commitment",
                                fromlist=["CommittedDatasetStore"])
        .CommittedDatasetStore(str(tmp_path / "seller_private2")),
        node_client_factory=_client_factory(),
    )
    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "runs2"),
                                   audit_executor=pa_executor)
    res = orch.run()
    audit = orch._stages["audit"].output
    assert 0.0 <= audit["disclosure_fraction"] <= 1.0
