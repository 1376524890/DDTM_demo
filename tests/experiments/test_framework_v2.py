"""Experiment Framework V2 验收测试：EF-G01..EF-G15。"""

from __future__ import annotations

import numpy as np
import pytest

from valor.experiments import (
    AnalysisRunner,
    ArtifactReproducibilityViolation,
    ArtifactStore,
    DataRoleRegistry,
    DataSplitIsolationError,
    ExperimentRunner,
    PairedPlan,
    RetryPolicy,
    SeedHierarchy,
    TrialSpec,
    artifact_root_hash,
    build_manifest,
    build_paired_plan,
    make_experiment_spec,
    make_world,
    validate_role_isolation,
)


# ---------------------------------------------------------------------------
# 测试 world_factory + 简单 executor
# ---------------------------------------------------------------------------
def _world_factory(seed, world_id):
    return make_world(
        world_id=world_id, seed=seed,
        dataset_manifest_hash=f"d{seed:016x}",
        split_hash=f"s{seed:016x}",
        ground_truth_state="B",
        corruption_family="label_flip",
        corruption_severity=0.05,
        buyer_context_hash="b" * 64,
    )


def _executor(method_id, config, world):
    """简单 executor：metric 依赖 method + world seed（确定性）。"""
    base = world.seed % 10
    if method_id == "no_audit":
        val = base + 1.0
    elif method_id == "valor":
        val = base + 5.0
    else:
        val = base + config.get("k", 1) / 100.0
    return {
        "metrics": {"detection": val, "cost": 100 - val},
        "terminal_state": "TRADE",
        "run_manifest_hash": "m" * 64,
        "trace_hash": "t" * 64,
        "artifact_root_hash": "a" * 64,
    }


def _manifest_builder(trial):
    return build_manifest(
        experiment_id="EXP-1", trial_id=trial.trial_id,
        method_id=trial.method_id, world_id=trial.world.world_id,
        git_commit="c" * 40, config_hash="cfg" * 16,
        dataset_hash=trial.world.dataset_manifest_hash,
        split_hash=trial.world.split_hash,
        calibration_artifact_hash="cal" * 32,
        certificate_hash="cert" * 32,
        execution_mode="COMMIT_CHALLENGE", seed=trial.world.seed,
    )


# ---- EF-G02: deterministic seed derivation ----
def test_ef_g02_seed_derivation():
    h1 = SeedHierarchy(42)
    h2 = SeedHierarchy(42)
    assert h1.dataset == h2.dataset
    assert h1.corruption == h2.corruption
    # 不同 namespace 不同 seed
    assert h1.dataset != h1.corruption
    # 不同 master 不同 seed
    assert h1.dataset != SeedHierarchy(43).dataset


# ---- EF-G01 + EF-G06: same world paired + deterministic trial_id ----
def test_ef_g01_g06_paired_and_trial_id():
    exp = make_experiment_spec(
        experiment_id="EXP-1", rq="RQ2", methods=("no_audit", "fixed_64", "valor"),
        seeds=(1, 2, 3), execution_mode="COMMIT_CHALLENGE",
        calibration_artifact_hash="cal" * 32, certificate_hash="cert" * 32)
    plan = build_paired_plan(
        experiment=exp, world_factory=_world_factory,
        method_configs={"fixed_64": {"k": 64}})
    # EF-G01: paired（每 world 所有 method 共享 world_hash）
    assert plan.methods_share_world() is True
    trials = plan.trials()
    assert len(trials) == 3 * 3  # 3 seeds × 3 methods
    # EF-G06: deterministic trial_id
    t1 = trials[0]
    t1b = TrialSpec.build(experiment_id="EXP-1", world=t1.world,
                          method_id="no_audit", method_config={})
    assert t1.trial_id == t1b.trial_id


# ---- EF-G03: R_cal/R_cert/R_eval disjoint ----
def test_ef_g03_role_isolation():
    reg = DataRoleRegistry()
    reg.assign_world("w1", "calibration")
    reg.assign_world("w2", "certification")
    reg.assign_world("w3", "evaluation")
    reg.assign_seed(1, "calibration")
    reg.assign_seed(2, "certification")
    reg.assign_seed(3, "evaluation")
    assert reg.validate_isolation() is True
    # 交叉 → 抛错
    with pytest.raises(DataSplitIsolationError):
        reg.assign_world("w1", "evaluation")
    assert validate_role_isolation(["w1"], ["w2"], ["w3"],
                                   [1], [2], [3]) is True
    assert validate_role_isolation(["w1"], ["w1"], ["w3"],
                                   [1], [2], [3]) is False


# ---- EF-G04 + EF-G07 + EF-G14: immutable, resume, failed retained ----
def test_ef_g04_g07_g14_run_resume(tmp_path):
    exp = make_experiment_spec(
        experiment_id="EXP-R", rq="RQ2", methods=("valor", "no_audit"),
        seeds=(1, 2), execution_mode="COMMIT_CHALLENGE",
        calibration_artifact_hash="cal" * 32, certificate_hash="cert" * 32)
    plan = build_paired_plan(experiment=exp, world_factory=_world_factory,
                             method_configs={})
    store = ArtifactStore(str(tmp_path / "ef-store"))

    runner = ExperimentRunner(plan=plan, store=store, executor=_executor,
                              manifest_builder=_manifest_builder)
    s1 = runner.run()
    assert s1.executed == 4 and s1.skipped == 0
    # EF-G04: immutable
    tid = plan.trials()[0].trial_id
    assert store.is_immutable(tid) is True

    # EF-G07: resume → 全部 skip（不重算）
    s2 = runner.run(resume=True)
    assert s2.skipped == 4 and s2.executed == 0

    # EF-G15: rerun hash 一致 → skip（不抛）
    # EF-G05: immutable hash 不一致 → REPRODUCIBILITY_VIOLATION
    res = store.read_result(tid)
    res["metrics"]["detection"] = 999.0  # 篡改
    with pytest.raises(ArtifactReproducibilityViolation):
        store.write_trial(tid, result=res, manifest=store.read_manifest(tid))


# ---- EF-G14: failed trials retained ----
def test_ef_g14_failed_retained(tmp_path):
    exp = make_experiment_spec(
        experiment_id="EXP-F", rq="RQ2", methods=("valor",),
        seeds=(1,), execution_mode="COMMIT_CHALLENGE")
    plan = build_paired_plan(experiment=exp, world_factory=_world_factory,
                             method_configs={})
    store = ArtifactStore(str(tmp_path / "ef-fail"))

    def bad_executor(*a, **k):
        raise RuntimeError("boom")

    runner = ExperimentRunner(plan=plan, store=store, executor=bad_executor,
                              manifest_builder=_manifest_builder,
                              retry_policy=RetryPolicy(max_retries=1))
    s = runner.run()
    assert s.failed == 1
    assert len(s.failed_trials) == 1
    # failed trial 显式保留
    res = store.read_result(s.failed_trials[0])
    assert res["success"] is False and res["error"] == "boom"


# ---- EF-G08: manifest binds ----
def test_ef_g08_manifest_binds():
    m = build_manifest(
        experiment_id="E", trial_id="t", method_id="valor", world_id="w1",
        git_commit="c" * 40, config_hash="cfg" * 16,
        dataset_hash="d" * 64, split_hash="s" * 64,
        calibration_artifact_hash="cal" * 32, certificate_hash="cert" * 32,
        execution_mode="COMMIT_CHALLENGE", seed=7)
    assert m["execution_mode"] == "COMMIT_CHALLENGE"
    assert m["calibration_artifact_hash"] == "cal" * 32
    assert m["git_commit"] == "c" * 40


# ---- EF-G09..G13: analysis ----
def test_ef_g09_g13_analysis(tmp_path):
    exp = make_experiment_spec(
        experiment_id="EXP-A", rq="RQ2", methods=("no_audit", "valor"),
        seeds=tuple(range(10)), execution_mode="COMMIT_CHALLENGE")
    plan = build_paired_plan(experiment=exp, world_factory=_world_factory,
                             method_configs={})
    store = ArtifactStore(str(tmp_path / "ef-ana"))
    ExperimentRunner(plan=plan, store=store, executor=_executor,
                     manifest_builder=_manifest_builder).run()
    trial_ids = [t.trial_id for t in plan.trials()]
    ar = AnalysisRunner(store, str(tmp_path / "ef-ana-out"))
    result = ar.analyze_pair(trial_ids, metric="detection",
                             proposed="valor", baseline="no_audit")
    # EF-G09: paired metrics（n_worlds = seeds）
    assert result["n_worlds"] == 10
    # EF-G10: bootstrap 95% CI
    assert result["diff_ci_95"][0] is not None
    # EF-G11: paired significance
    assert result["test"]["method"] in ("paired_t", "wilcoxon")
    # EF-G12: effect size
    assert result["effect_size"]["cohens_dz"] is not None
    assert result["effect_size"]["rank_biserial"] is not None
    # EF-G13: Holm
    results = ar.holm_adjust([result])
    assert results[0]["holm_adjusted_p"] is not None
    # write csvs
    ar.write_csvs(results)
    assert (ar.out_dir / "significance.csv").exists()


# ---- EF-G15: artifact_root_hash deterministic ----
def test_ef_g15_artifact_root_hash(tmp_path):
    import json

    store = ArtifactStore(str(tmp_path / "ef-hash"))
    h1 = artifact_root_hash(str(tmp_path / "ef-hash"))
    h2 = artifact_root_hash(str(tmp_path / "ef-hash"))
    assert h1 == h2
