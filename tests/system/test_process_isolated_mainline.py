"""P0-G: COMMIT_CHALLENGE privacy audit in transaction mainline via subprocess auditors."""

from __future__ import annotations

from valor.engine import CapstoneScenario, TransactionOrchestrator
from valor.privacy_audit import ClaimType, make_privacy_audit_executor
from valor.privacy_audit.process_isolated import ProcessHttpAuditorCluster


def test_process_isolated_privacy_audit_in_mainline(tmp_path):
    sc = CapstoneScenario(scenario_id="proc-main", seller_id="seller-1",
                          buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 100, "max_fraction": 0.2, "max_bytes": 100 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 100
    sc.rights["audit_reveal_max_fraction"] = 0.2
    sc.rights["audit_reveal_max_bytes"] = 100 * 784

    cluster = ProcessHttpAuditorCluster(n=10)
    try:
        executor = make_privacy_audit_executor(
            claim_type=ClaimType.LABEL_DISTRIBUTION,
            challenge_sizes=[32], n_nodes=10, f=2,
            node_client_factory=cluster.client_factory(),
            auditor_identity_registry=cluster.registry,
        )
        orch = TransactionOrchestrator(
            sc, run_dir=str(tmp_path / "runs"), audit_executor=executor)
        res = orch.run()
        audit = orch._stages["audit"].output
        assert audit["execution_mode"] == "COMMIT_CHALLENGE"
        assert 0 <= audit["unique_disclosure"] <= 100
        assert res.terminal_state in ("TRADE", "NO_TRADE")
    finally:
        cluster.close()
