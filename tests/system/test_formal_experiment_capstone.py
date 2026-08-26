"""Round 6 Phase 6: real FORMAL_EXPERIMENT capstone with all frozen components.

Constructs R_cal/R_cert/R_eval role manifests, process-isolated auditor cluster,
distributed R_cal, LikelihoodCatalog, ActionProfileCatalog, AuditPolicy,
independent full-policy R_cert, valuation calibration, and runs
TransactionOrchestrator(execution_mode=FORMAL_EXPERIMENT) through the mainline.
"""

from __future__ import annotations

import numpy as np
import pytest

from valor.audit.action_catalog import ActionProfileCatalog
from valor.audit.action_profile import build_action_profile
from valor.audit.likelihood_catalog import LikelihoodCatalog
from valor.audit.market_quote import AuditMarketSnapshot
from valor.audit.policy import AuditPolicy
from valor.core.enums import ExecutionMode
from valor.core.hashing import content_hash
from valor.engine.calibration import FrozenArtifact
from valor.engine.distributed_calibration_runner import DistributedAuditCalibrationRunner
from valor.engine.distributed_policy_certifier import DistributedPolicyCertifier
from valor.engine import CapstoneScenario, TransactionOrchestrator
from valor.engine.manifest import RunManifest
from valor.experiments.registry import DataRoleManifest, DataRoleRegistry
from valor.privacy_audit import ClaimType, CommittedDatasetStore
from valor.privacy_audit.process_isolated import AuditRuntimeDescriptor, ProcessHttpAuditorCluster


def _role(role_id, n, seed, start):
    return DataRoleManifest(
        role_id=role_id, dataset_id="mnist", dataset_version="v1",
        sample_ids=tuple(range(start, start + n)), split_seed=seed,
        split_algorithm_hash=content_hash({"split": "four-way-v1"}),
        source_dataset_hash=content_hash({"dataset": "mnist"}),
        trainer_scope_hash=content_hash({"trainer": "mnist-mlp"}),
        task_family_hash=content_hash({"task": "digit-classification"}),
    )


def _scenario():
    sc = CapstoneScenario(scenario_id="formal-capstone", seller_id="s", buyer_id="b")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.buyer_task["deployment_scale"] = 3000
    sc.audit["challenge_sizes"] = [16]
    sc.audit["privacy_budget"] = {
        "max_unique_rows": 100, "max_fraction": 0.9, "max_bytes": 100 * 784,
    }
    sc.rights["audit_reveal_max_rows"] = 100
    sc.rights["audit_reveal_max_fraction"] = 0.9
    sc.rights["audit_reveal_max_bytes"] = 100 * 784
    sc.audit["low_suitability_world"] = {
        "method": "buyer_task_utility",
        "threshold": 0.5,
        "row_utilities": [0.1] * 30 + [0.9] * 70,
        "ground_truth_ref": "rcal-L-buyer-task-utility",
    }
    sc.audit["breach_world"] = {
        "family": "POST_COMMIT_DATA_TAMPER",
        "tamper_fraction": 0.2,
        "ground_truth_ref": "rcal-B-post-commit-data-tamper",
    }
    # Economic params: make the capstone trade viable deterministically.
    sc.buyer["w_b_rem"] = 1000.0
    sc.seller["pi_s0"] = 0.0
    sc.exposure["rev_future_with"] = 0.0
    sc.exposure["rev_future_without"] = 0.0
    sc.seller["c_marg"] = 0.0
    sc.seller["c_r_s_pay"] = 0.0
    sc.seller["r_s_post"] = 0.0
    sc.buyer["r_b_post"] = 0.0
    sc.audit["market"]["bids"] = {f"node-{i}": 0.0 for i in range(10)}
    sc.bond.update({
        "g_dev": 0.0, "eps_s": 0.0, "p_e_bond": 1.0, "p_e_f": 0.0,
        "lambda_s": 1.0, "f_s": 0.0, "kappa_s": 0.0, "t_pre": 0.0, "t_post": 0.0,
    })
    return sc


def _policy(sc, profile_hashes, lik_hashes):
    return AuditPolicy(
        policy_version="v1",
        action_profile_hashes=tuple(sorted(profile_hashes)),
        likelihood_artifact_hashes=tuple(sorted(lik_hashes)),
        selection_algorithm_version="voi-v1",
        prior_family_version="dirichlet-v1",
        loss_matrix_hash="loss-v1",
        stop_rule="VOI_LE_0",
        mandatory_base_audit_policy="BASE_LISTING_ONCE",
        disclosure_policy="rows-fraction-bytes",
        market_quote_policy="FROZEN_SNAPSHOT",
        payer_policy="SELLER",
        evidence_verification_policy="ED25519_REQUIRED",
        quorum_policy="QUORUM_BY_RESULT",
        replacement_policy="OFFLINE_REPLACEMENT",
        certificate_requirements="R_CERT_INDEPENDENT",
    )


def _market_provider(sc):
    mkt = sc.audit["market"]
    snap = AuditMarketSnapshot(
        snapshot_id=mkt.get("snapshot_id", "formal-market"),
        family=mkt.get("family", "quality"),
        qualified_nodes=[str(x) for x in mkt["qualified_nodes"]],
        bids={str(k): float(v) for k, v in mkt["bids"].items()},
        min_stake=float(mkt.get("min_stake", 0.0)),
        source_kind="MARKET_DISCOVERED",
        source_ref="formal-market-provider",
        version=mkt.get("version", "1"),
    )

    class _Provider:
        def snapshot(self):
            return snap

    return _Provider()


def test_formal_experiment_capstone(tmp_path):
    rng = np.random.default_rng(11)
    X = rng.integers(0, 256, size=(300, 784), dtype=np.uint8)
    y = rng.integers(0, 10, size=300)
    sc = _scenario()

    cal_manifest = _role("R_cal", 100, 11, 0)
    cert_manifest = _role("R_cert", 100, 21, 100)
    eval_manifest = _role("R_eval", 100, 31, 200)
    role_registry = DataRoleRegistry()
    role_registry.register_role_manifest(cal_manifest)
    role_registry.register_role_manifest(cert_manifest)
    role_registry.register_role_manifest(eval_manifest)
    role_registry.freeze()

    cluster = ProcessHttpAuditorCluster(n=10)
    try:
        runtime = AuditRuntimeDescriptor.from_cluster(cluster)
        factory = cluster.client_factory()
        public_keys = cluster.registry.public_keys()

        rcal = DistributedAuditCalibrationRunner(
            scenario=sc, X=X, y=y, role_manifest=cal_manifest,
            claim_type=ClaimType.LABEL_DISTRIBUTION,
            challenge_sizes=[16], n_runs=1, f=2,
            seller_store=CommittedDatasetStore(str(tmp_path / "rcal")),
            node_client_factory=factory, public_keys=public_keys,
            execution_mode=ExecutionMode.FORMAL_EXPERIMENT,
            audit_runtime=runtime,
        )
        rcal_events = rcal.run()
        lik_arts = rcal.freeze_likelihood()
        profile_hashes = sorted(lik_arts.keys())
        lik_hashes = [art.artifact_hash for art in lik_arts.values()]

        lik_catalog = LikelihoodCatalog()
        for art in lik_arts.values():
            lik_catalog.register(art)
        profile_catalog = ActionProfileCatalog()
        for k in [16]:
            profile = build_action_profile(
                scenario_audit=sc.audit,
                claim_type=ClaimType.LABEL_DISTRIBUTION.value,
                k=k, f=2,
                execution_version_hash=str(sc.audit.get("execution_version_hash", "cc-audit-v1")),
            )
            profile_catalog.register(profile)

        policy = _policy(sc, profile_hashes, lik_hashes)
        certifier = DistributedPolicyCertifier(
            policy=policy, scenario=sc, X=X, y=y, role_manifest=cert_manifest,
            likelihood_artifacts=lik_arts,
            claim_type=ClaimType.LABEL_DISTRIBUTION, challenge_sizes=[16],
            n_runs=1, f=2, seller_store=CommittedDatasetStore(str(tmp_path / "rcert")),
            node_client_factory=factory, public_keys=public_keys,
            execution_mode=ExecutionMode.FORMAL_EXPERIMENT,
            audit_runtime=runtime,
            role_registry=role_registry,
            market_provider=_market_provider(sc),
        )
        cert_art = certifier.run(
            r_cal_sample_ids=list(cal_manifest.sample_ids),
            r_cal_event_ids=[e.event_id for e in rcal_events],
        )

        val = FrozenArtifact(kind="valuation_calibration", data={
            "alpha_v": 0.05, "n_samples": 4, "residual_quantile": 0.0,
            "coverage": 1.0, "residuals": [0.0, 0.0, 0.0, 0.0],
            "dataset_hash": "d", "trainer_hash": "t", "buyer_context_family": "f", "seed": 0,
        })

        orch = TransactionOrchestrator(
            sc, run_dir=str(tmp_path / "runs"),
            execution_mode=ExecutionMode.FORMAL_EXPERIMENT,
            role_registry=role_registry,
            market_provider=_market_provider(sc),
            likelihood_catalog=lik_catalog,
            audit_policy=policy,
            policy_certificate=cert_art,
            valuation_calibration=val,
        )
        res = orch.run()
        assert res.terminal_state == "TRADE"
        audit = orch._stages["audit"].output
        assert audit["audit_policy_status"] == "CERTIFIED"
        assert audit["audit_policy_hash"] == policy.policy_hash
        # no TEST_FIXTURE source / scenario fallback in FORMAL path
        assert audit["execution_mode"] == "COMMIT_CHALLENGE"
        assert orch._stages["data_voi"].output["valuation_calibration_hash"] == val.artifact_hash
        assert orch._stages["audit"].output["audit_policy_hash"] == policy.policy_hash
        manifest_plain = __import__("json").loads(
            (orch.artifacts.root / "manifest.json").read_text(encoding="utf-8"))
        manifest = RunManifest.from_plain(manifest_plain)
        assert manifest.audit_policy_hash == policy.policy_hash
        assert manifest.certificate_hash == cert_art.r_cert_hash
        assert manifest.valuation_calibration_hash == val.artifact_hash
    finally:
        cluster.close()
