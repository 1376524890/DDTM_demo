"""完整场景矩阵 C0-C8（任务书 §42）。

C0 NORMAL_TRADE / C1 NO_TRADE / C2 SELLER_BREACH_AUDIT / C3 BUYER_BREACH /
C4 NO_QUORUM / C5 AUDIT_DISCLOSURE_BUDGET_INFEASIBLE / C6 DELIVERY_ENV_ATTEST_FAIL /
C7 ILLEGAL_TRAINING_DENIED / C8 合法训练。
"""

from __future__ import annotations

import numpy as np
import pytest

from valor.engine import CapstoneScenario, run_capstone
from valor.engine.acceptance import (
    scenario_c0_normal,
    scenario_c1_no_trade,
    scenario_c2_seller_breach,
    scenario_c3_buyer_misuse,
)


def test_c0_normal_trade(tmp_path):
    res = run_capstone(scenario_c0_normal(), run_dir=str(tmp_path / "c0"))
    assert res.terminal_state == "TRADE"
    assert res.decision == "TRADE"


def test_c1_no_trade(tmp_path):
    res = run_capstone(scenario_c1_no_trade(), run_dir=str(tmp_path / "c1"))
    assert res.terminal_state == "NO_TRADE"


def test_c2_seller_breach_audit(tmp_path):
    """审计阶段真实 corruption → BREACH_EVIDENCE → SELLER_BREACH。"""
    from valor.experiments.adapters import TamperingSellerProvider

    def seller_open_fn(challenge, seller_svc):
        return TamperingSellerProvider(seller_svc).process_challenge(challenge)

    res = run_capstone(scenario_c2_seller_breach(), run_dir=str(tmp_path / "c2"),
                       seller_open_fn=seller_open_fn)
    assert res.terminal_state == "SELLER_BREACH"


def test_c3_buyer_breach(tmp_path):
    """成交后真实 misuse → evidence → BUYER_BREACH。"""
    res = run_capstone(scenario_c3_buyer_misuse(), run_dir=str(tmp_path / "c3"))
    assert res.terminal_state == "BUYER_BREACH"


def test_c5_disclosure_budget_infeasible(tmp_path):
    """披露预算不足以执行任何 action → 不超预算地拒绝。"""
    sc = scenario_c0_normal()
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 8, "max_fraction": 0.01, "max_bytes": 8 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 8
    sc.rights["audit_reveal_max_fraction"] = 0.01
    sc.rights["audit_reveal_max_bytes"] = 8 * 784
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c5"))
    res = orch.run()
    audit = orch._stages["audit"].output
    # 预算不足 → 不超预算地拒绝，精确 ACTION_INFEASIBLE_DISCLOSURE → NO_TRADE
    assert audit.get("unique_disclosure", 0) <= 8
    assert audit.get("audit_policy_status") == "ACTION_INFEASIBLE_DISCLOSURE"
    assert res.terminal_state == "NO_TRADE"
    assert "pricing" not in orch._stages
    assert "delivery" not in orch._stages


def test_c4_no_quorum(tmp_path):
    """审计节点离线过多 → 无一致 quorum → 审计不产生 CERTIFIED 结果。"""
    sc = scenario_c0_normal()
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 200, "max_fraction": 0.3, "max_bytes": 200 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 200
    sc.rights["audit_reveal_max_fraction"] = 0.3
    sc.rights["audit_reveal_max_bytes"] = 200 * 784
    from fastapi.testclient import TestClient
    from valor.engine.orchestrator import TransactionOrchestrator
    from valor.experiments.adapters import OfflineAuditorTransport
    from valor.privacy_audit import CommitChallengeVerifier, create_privacy_app

    clients = {}
    public_keys = {}
    for i in range(10):
        node_id = f"node-{i}"
        verifier = CommitChallengeVerifier(node_id)
        clients[node_id] = TestClient(create_privacy_app(verifier))
        public_keys[node_id] = verifier.signing_key.public_key_hex

    class _NodeClient:
        def __init__(self, tc):
            self._tc = tc
        def submit_task(self, task):
            r = self._tc.post("/privacy/tasks", json=task.to_plain())
            r.raise_for_status()
            return r.json()

    def _base(nid):
        return _NodeClient(clients[str(nid)])

    factory = OfflineAuditorTransport(_base, [f"node-{i}" for i in range(6)])
    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c4"), node_client_factory=factory,
                                   public_keys=public_keys)
    res = orch.run()
    audit = orch._stages["audit"].output
    # 无 quorum → 不产生 CERTIFIED action trace，精确 NO_QUORUM → NO_TRADE
    assert len(audit.get("audit_trace_events", [])) >= 1
    assert not any(e.get("status") == "CERTIFIED" for e in audit.get("audit_trace_events", []))
    assert audit.get("audit_policy_status") == "NO_QUORUM"
    assert res.terminal_state == "NO_TRADE"
    assert "pricing" not in orch._stages
    assert "delivery" not in orch._stages


def test_c6_delivery_fail(tmp_path):
    """交付替换 → H(D) mismatch → SELLER_BREACH，Rights 不 ACTIVE。"""
    sc = scenario_c0_normal()
    sc.buyer["w_b_rem"] = 1000.0
    sc.seller["pi_s0"] = 0.0
    sc.exposure["rev_future_without"] = 0.0
    sc.exposure["rev_future_with"] = 0.0
    sc.seller["c_marg"] = 0.0
    sc.seller["c_r_s_pay"] = 0.0
    sc.seller["r_s_post"] = 0.0
    sc.buyer["r_b_post"] = 0.0
    sc.audit["market"]["bids"] = {f"node-{i}": 0.0 for i in range(10)}
    sc.bond.update({
        "g_dev": 0.0, "eps_s": 0.0, "p_e_bond": 1.0, "p_e_f": 0.0,
        "lambda_s": 1.0, "f_s": 0.0, "kappa_s": 0.0, "t_pre": 0.0, "t_post": 0.0,
    })
    from valor.engine.orchestrator import TransactionOrchestrator
    from valor.experiments.adapters import MismatchedDeliveryProvider

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c6"),
                                   delivery_provider=MismatchedDeliveryProvider())
    res = orch.run()
    assert res.terminal_state == "SELLER_BREACH"
    delivery = orch._stages["delivery"].output
    assert delivery.get("verified") is False
    # 终态非 TRADE → usage/training 不启用
    assert orch._stages["usage"].output.get("enabled") is False
    assert orch._stages["training"].output.get("enabled") is False


def test_c13_prelock_insufficient_funds(tmp_path):
    """卖方资金不足以预锁 → 不进入审计，直接 NO_TRADE。"""
    sc = scenario_c0_normal()
    sc.seller["funds"] = 0.0
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c13"))
    res = orch.run()
    assert res.terminal_state == "NO_TRADE"
    prelock = orch._stages["prelock"].output
    assert prelock.get("locked") is False
    # fail-closed downstream absent
    assert "audit" not in orch._stages or orch._stages["audit"].output.get("audit_trace_events", []) == []
    audit = orch._stages.get("audit")
    assert audit is None or len(audit.output.get("audit_trace_events", [])) == 0
    assert audit is None or audit.output.get("audit_pay_s", 0) == 0.0
    assert audit is None or audit.output.get("audit_pay_b", 0) == 0.0
    assert "pricing" not in orch._stages
    assert "delivery" not in orch._stages


def test_c14_buyer_usage_bond_slash(tmp_path):
    """BUYER_BREACH 时 usage bond 在 Phase II 被罚没给 seller。"""
    sc = scenario_c3_buyer_misuse()
    sc.buyer["w_b_rem"] = 1000.0
    sc.seller["pi_s0"] = 0.0
    sc.exposure["rev_future_without"] = 0.0
    sc.exposure["rev_future_with"] = 0.0
    sc.seller["c_marg"] = 0.0
    sc.seller["c_r_s_pay"] = 0.0
    sc.seller["r_s_post"] = 0.0
    sc.buyer["r_b_post"] = 0.0
    sc.audit["market"]["bids"] = {f"node-{i}": 0.0 for i in range(10)}
    sc.bond.update({
        "g_dev": 0.0, "eps_s": 0.0, "p_e_bond": 1.0, "p_e_f": 0.0,
        "lambda_s": 1.0, "f_s": 0.0, "kappa_s": 0.0, "t_pre": 0.0, "t_post": 0.0,
    })
    sc.usage["usage_bond"] = {
        "p_misuse_lower_sys": 0.9, "g_misuse": 10.0, "eps_b": 0.0,
        "p_e_ubond": 1.0, "p_e_uf": 0.0, "lambda_b": 1.0, "f_b": 0.0,
    }
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c14"))
    res = orch.run()
    assert res.terminal_state == "BUYER_BREACH"
    settlement = orch._stages["settlement"].output
    money = [e for e in settlement.get("money_events", [])]
    assert any(e["from_account"] == "B_B^use" and e["to_account"] == "seller"
               for e in money)
    # expected slash amount: buyer usage bond full amount (lambda_b * B_B_use)
    ub = sc.usage.get("usage_bond", {})
    b_b_use = settlement.get("b_b_use", 0.0) or orch._stages.get("pricing", type("S", (), {"output": {}})()).output.get("b_b_use", 0.0)
    expected = float(ub.get("lambda_b", 1.0)) * float(b_b_use or 0.0)
    if expected > 0:
        slash_events = [e for e in money if e["from_account"] == "B_B^use" and e["to_account"] == "seller"]
        assert slash_events and abs(sum(float(e["amount"]) for e in slash_events) - expected) < 1e-6
    else:
        # if bond amount is zero, at least one B_B^use -> seller transfer must exist
        assert any(e["from_account"] == "B_B^use" and e["to_account"] == "seller" for e in money)


def test_c9_invalid_signature(tmp_path):
    """全部节点签名无效 → 无有效 evidence → 审计不产生 CERTIFIED 结果。"""
    sc = scenario_c0_normal()
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 200, "max_fraction": 0.3, "max_bytes": 200 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 200
    sc.rights["audit_reveal_max_fraction"] = 0.3
    sc.rights["audit_reveal_max_bytes"] = 200 * 784
    from fastapi.testclient import TestClient
    from valor.engine.orchestrator import TransactionOrchestrator
    from valor.experiments.adapters import InvalidSignatureAuditorTransport
    from valor.privacy_audit import CommitChallengeVerifier, create_privacy_app

    clients = {}
    public_keys = {}
    for i in range(10):
        node_id = f"node-{i}"
        verifier = CommitChallengeVerifier(node_id)
        clients[node_id] = TestClient(create_privacy_app(verifier))
        public_keys[node_id] = verifier.signing_key.public_key_hex

    class _NodeClient:
        def __init__(self, tc):
            self._tc = tc
        def submit_task(self, task):
            r = self._tc.post("/privacy/tasks", json=task.to_plain())
            r.raise_for_status()
            return r.json()

    def _base(nid):
        return _NodeClient(clients[str(nid)])

    factory = InvalidSignatureAuditorTransport(_base, [f"node-{i}" for i in range(10)])
    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c9"), node_client_factory=factory,
                                   public_keys=public_keys)
    res = orch.run()
    audit = orch._stages["audit"].output
    assert len(audit.get("audit_trace_events", [])) >= 1
    assert all(e.get("status") == "INVALID_EVIDENCE" for e in audit.get("audit_trace_events", []))
    assert audit.get("audit_policy_status") == "INVALID_EVIDENCE"
    assert res.terminal_state == "NO_TRADE"
    assert "pricing" not in orch._stages
    assert "delivery" not in orch._stages


def test_c7_illegal_training_denied(tmp_path):
    """非法训练（未授权 actor）→ 无 key release / 无 training。"""
    sc = scenario_c0_normal()
    sc.usage["training_requests"] = [
        {"actor": "buyer_org_B", "purpose": "digit-classification",
         "requested_output": "MODEL_ARTIFACT", "environment": "approved_compute",
         },
    ]
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c7"))
    res = orch.run()
    assert res.terminal_state == "TRADE"
    tr = orch._stages["training"].output
    assert tr.get("enabled") is True
    out = tr["results"][0]["outcome"]
    assert out["decision"] == "DENY"
    assert out["key_released"] is False
    assert out["training_started"] is False


def test_c8_legal_training_runs(tmp_path):
    """合法训练真实运行并生成 metrics。"""
    sc = scenario_c0_normal()
    sc.usage["training_requests"] = [
        {"actor": "buyer_org_A", "purpose": "digit-classification",
         "requested_output": "MODEL_ARTIFACT", "environment": "approved_compute",
         },
    ]
    from valor.engine.orchestrator import TransactionOrchestrator

    orch = TransactionOrchestrator(sc, run_dir=str(tmp_path / "c8"))
    res = orch.run()
    assert res.terminal_state == "TRADE"
    tr = orch._stages["training"].output
    assert tr.get("enabled") is True
    out = tr["results"][0]["outcome"]
    assert out["decision"] == "ALLOW"
    assert out["training_started"] is True
    assert out["model_created"] is True
    assert out.get("worker_pid") is not None
    assert out.get("model_artifact_hash")
    assert "accuracy" in out["metrics"]


def test_c10_action_profile_likelihood_mismatch_fails_closed(tmp_path):
    """C10: action profile without certified likelihood must never execute."""
    import numpy as np

    from valor.audit.policy import AuditPolicy
    from valor.core.enums import ExecutionMode
    from valor.core.hashing import content_hash
    from valor.engine.distributed_calibration_runner import DistributedAuditCalibrationRunner
    from valor.engine.distributed_policy_certifier import DistributedPolicyCertifier
    from valor.engine.experiment_world import build_experiment_world
    from valor.experiments.registry import DataRoleManifest
    from valor.privacy_audit import ClaimType, CommittedDatasetStore
    from tests.privacy_audit.test_distributed_policy_certifier import (
        _client_factory, _role, _scenario, _policy,
    )

    rng = np.random.default_rng(123)
    X = rng.integers(0, 256, size=(200, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=200)
    sc = _scenario()
    sc.audit["low_suitability_world"]["row_utilities"] = [0.1] * 30 + [0.9] * 70
    factory, public_keys = _client_factory()
    rcal = DistributedAuditCalibrationRunner(
        scenario=sc, X=X, y=y, role_manifest=_role("R_cal", 100, 11),
        claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[16], n_runs=1,
        f=2, seller_store=CommittedDatasetStore(str(tmp_path / "rcal")),
        node_client_factory=factory, public_keys=public_keys,
        execution_mode=ExecutionMode.TEST_FIXTURE,
    )
    rcal.run()
    lik_arts = rcal.freeze_likelihood()
    # policy references a profile hash that has no likelihood artifact
    bad_profile = content_hash({"action": "phantom", "k": 99})
    bad_lik = content_hash({"lik": "phantom"})
    with pytest.raises(ValueError, match="ACTION_NOT_CERTIFIED|CERTIFICATION_POLICY_BINDING_MISMATCH"):
        DistributedPolicyCertifier(
            policy=_policy(sc, [bad_profile], [bad_lik]),
            scenario=sc, X=X, y=y,
            role_manifest=_role("R_cert", 100, 21, start=100),
            likelihood_artifacts=lik_arts,
            claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[16],
            n_runs=1, f=2,
            seller_store=CommittedDatasetStore(str(tmp_path / "rcert")),
            node_client_factory=factory, public_keys=public_keys,
            execution_mode=ExecutionMode.TEST_FIXTURE,
        ).run()


def test_c11_rcal_rcert_overlap_fails_closed(tmp_path):
    """C11: overlapping R_cal/R_cert sample ids must fail with DATA_ROLE_OVERLAP."""
    from valor.core.enums import ExecutionMode
    from valor.engine.distributed_policy_certifier import DistributedPolicyCertifier
    from valor.privacy_audit import ClaimType, CommittedDatasetStore
    from tests.privacy_audit.test_distributed_policy_certifier import (
        _client_factory, _role, _scenario, _policy,
    )

    rng = np.random.default_rng(124)
    X = rng.integers(0, 256, size=(100, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=100)
    sc = _scenario()
    factory, public_keys = _client_factory()
    with pytest.raises(ValueError, match="DATA_ROLE_OVERLAP"):
        DistributedPolicyCertifier(
            policy=_policy(sc), scenario=sc, X=X, y=y,
            role_manifest=_role("R_cert", 20, 31),  # overlaps with r_cal ids 0..2
            likelihood_artifacts={},
            claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[16],
            n_runs=1, f=2,
            seller_store=CommittedDatasetStore(str(tmp_path / "x")),
            node_client_factory=factory, public_keys=public_keys,
            execution_mode=ExecutionMode.TEST_FIXTURE,
        ).run(r_cal_sample_ids=[0, 1, 2])


def test_c12_final_eval_early_access_forbidden(tmp_path):
    """C12: pre-terminal FinalEval access must record DENY and raise."""
    import numpy as np
    import pandas as pd

    from valor.feedback.final_eval_access_ledger import (
        FinalEvaluationAccessLedger, FinalEvaluationHandle, TerminalDecisionArtifact,
    )

    X = pd.DataFrame({"a": np.arange(10.0)})
    y = pd.Series(np.arange(10))
    ledger = FinalEvaluationAccessLedger()
    handle = FinalEvaluationHandle(X=X, y=y, indices=[2, 4], ledger=ledger)
    with pytest.raises(ValueError, match="FINAL_EVALUATION_ACCESS_FORBIDDEN"):
        handle.resolve(stage="DATA_VOI", caller="orch",
                       terminal_artifact=TerminalDecisionArtifact(terminal="TRADE", stage="DATA_VOI"))
    assert any(r.reason == "FINAL_EVALUATION_ACCESS_FORBIDDEN" for r in ledger.records)
