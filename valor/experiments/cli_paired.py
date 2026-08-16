"""paired 实验 CLI：走 Experiment Framework V2（spec/registry/pairing/runner/analysis）。

method 只能改变策略，不能改变 world（paired）；每个 trial 经 TransactionOrchestrator。
"""

from __future__ import annotations

import json

from .artifacts import ArtifactStore
from .pairing import build_paired_plan
from .runner import ExperimentRunner
from .seeds import SeedHierarchy
from .spec import make_experiment_spec, make_world


def run_paired_cli(cfg: dict, exp: dict) -> int:
    from .analysis import AnalysisRunner
    from .rq2_audit_voi import capstone_trial_executor

    methods = tuple(exp.get("methods", ("valor", "no_audit")))
    seeds = tuple(exp.get("seeds", (1, 2)))
    out_dir = exp.get("out_dir", "raw/experiments")
    experiment_id = exp.get("experiment_id", "CLI-RQ2")

    spec = make_experiment_spec(
        experiment_id=experiment_id, rq=exp.get("rq", "RQ2"),
        methods=methods, seeds=seeds, execution_mode="COMMIT_CHALLENGE",
        metrics=("clearing_price", "n_audit_steps", "audit_pay",
                 "disclosure_fraction"),
    )

    def world_factory(seed, world_id):
        sh = SeedHierarchy(seed)
        return make_world(
            world_id=world_id, seed=seed,
            dataset_manifest_hash=sh.split,
            split_hash=sh.split,
            ground_truth_state="G", buyer_context_hash="b" * 64,
        )

    def manifest_builder(trial):
        from .artifacts import build_manifest

        return build_manifest(
            experiment_id=experiment_id, trial_id=trial.trial_id,
            method_id=trial.method_id, world_id=trial.world.world_id,
            git_commit="", config_hash="", dataset_hash=trial.world.dataset_manifest_hash,
            split_hash=trial.world.split_hash, execution_mode="COMMIT_CHALLENGE",
            seed=trial.world.seed,
        )

    plan = build_paired_plan(experiment=spec, world_factory=world_factory,
                             method_configs={})
    store = ArtifactStore(out_dir)
    runner = ExperimentRunner(plan=plan, store=store,
                              executor=capstone_trial_executor,
                              manifest_builder=manifest_builder)
    summary = runner.run()
    print("=== RunSummary ===")
    print(json.dumps(summary.to_plain(), indent=2))

    ar = AnalysisRunner(store, out_dir + "-analysis")
    for metric in ("clearing_price", "n_audit_steps", "audit_pay"):
        try:
            res = ar.analyze_pair([t.trial_id for t in plan.trials()],
                                  metric=metric, proposed="valor",
                                  baseline="no_audit")
            print(json.dumps({metric: {
                "n_worlds": res["n_worlds"],
                "mean_paired_diff": res["mean_paired_diff"],
                "test": res["test"],
            }}, indent=2))
        except Exception as e:  # noqa: BLE001
            print(f"  {metric}: 分析跳过（{e}）")
    return 0


__all__ = ["run_paired_cli"]
