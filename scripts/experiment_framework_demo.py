"""Experiment Framework 真实演示（不跑论文结论）。

用真实 capstone executor 跑一个小 paired 实验（2 seeds × 2 methods），
验证 framework 端到端：world → paired trial → immutable artifacts → analysis。
"""

from __future__ import annotations

import json

from valor.experiments import (
    AnalysisRunner,
    ArtifactStore,
    ExperimentRunner,
    build_manifest,
    build_paired_plan,
    make_experiment_spec,
    make_world,
)
from valor.experiments.rq2_audit_voi import capstone_trial_executor


def world_factory(seed, world_id):
    return make_world(
        world_id=world_id, seed=seed,
        dataset_manifest_hash=f"d{seed:016x}",
        split_hash=f"s{seed:016x}",
        ground_truth_state="B", corruption_family="label_flip",
        corruption_severity=0.05, buyer_context_hash="b" * 64,
    )


def manifest_builder(trial):
    return build_manifest(
        experiment_id="DEMO-RQ2", trial_id=trial.trial_id,
        method_id=trial.method_id, world_id=trial.world.world_id,
        git_commit="c" * 40, config_hash="cfg" * 16,
        dataset_hash=trial.world.dataset_manifest_hash,
        split_hash=trial.world.split_hash,
        calibration_artifact_hash="cal" * 32,
        certificate_hash="cert" * 32,
        execution_mode="COMMIT_CHALLENGE", seed=trial.world.seed,
    )


def main():
    exp = make_experiment_spec(
        experiment_id="DEMO-RQ2", rq="RQ2",
        methods=("no_audit", "valor"), seeds=(1, 2),
        execution_mode="COMMIT_CHALLENGE",
        calibration_artifact_hash="cal" * 32, certificate_hash="cert" * 32,
        metrics=("clearing_price", "n_audit_steps", "audit_pay",
                 "disclosure_fraction"),
    )
    plan = build_paired_plan(experiment=exp, world_factory=world_factory,
                             method_configs={})
    store = ArtifactStore("/tmp/ef-demo")
    runner = ExperimentRunner(plan=plan, store=store,
                              executor=capstone_trial_executor,
                              manifest_builder=manifest_builder)
    summary = runner.run()
    print("=== RunSummary ===")
    print(json.dumps(summary.to_plain(), indent=2))

    trial_ids = [t.trial_id for t in plan.trials()]
    ar = AnalysisRunner(store, "/tmp/ef-demo-analysis")
    for metric in ("clearing_price", "n_audit_steps", "audit_pay"):
        try:
            res = ar.analyze_pair(trial_ids, metric=metric,
                                  proposed="valor", baseline="no_audit")
            print(f"=== {metric} ===")
            print(json.dumps({
                "n_worlds": res["n_worlds"],
                "mean_diff": res["mean_paired_diff"],
                "diff_ci_95": res["diff_ci_95"],
                "test": res["test"],
                "effect_size": res["effect_size"],
            }, indent=2))
        except Exception as e:  # noqa: BLE001
            print(f"  {metric}: 分析跳过（{e}）")
    ar.write_csvs([])
    print("analysis dir:", ar.out_dir)


if __name__ == "__main__":
    main()
