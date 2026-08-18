"""RQ2 模板：Audit-VOI 实验（EF Framework 的 method executor 示例）。

本文件是 RQ2 的 method executor 骨架，供 ExperimentRunner 调用。
method 只接收 (method_id, config, world)，在 world 上运行真实 capstone，
返回 metrics。

注意：本文件不跑正式论文结论，只提供 framework 接入的真实 executor。
"""

from __future__ import annotations

from typing import Any

from .seeds import SeedHierarchy


def capstone_trial_executor(method_id: str, config: dict, world) -> dict:
    """在 world 上运行一次真实 capstone 交易，返回 metrics。

    method_id 决定审计策略：
        no_audit        : 不审计
        fixed_{k}       : 固定 challenge_size k
        valor           : 完整 Audit-VOI（默认 executor）
    所有 method 共享同一 world（seed/data split/ground truth/corruption）。
    """
    from valor.engine import CapstoneScenario, TransactionOrchestrator
    from valor.engine.calibration_runner import CalibrationConfig, run_offline_calibration
    from valor.data.download import load_dataset

    # 用 world.seed 派生 seed（EF-G02）
    sh = SeedHierarchy(world.seed)
    hb = load_dataset("breast_cancer")
    pool = hb.X.iloc[:200]

    # calibration 用 calibration seed（与 evaluation seed 隔离）
    cal = run_offline_calibration(CalibrationConfig(
        historical_pool=pool, y_historical=hb.y.iloc[:len(pool)],
        dataset_hash=world.dataset_manifest_hash,
        trainer_hash="t" * 64, seed=sh.calibration,
        payoff_matrix=[[1.0, -2.0], [-5.0, 3.0]],
        deployment_scale=1000, n_pseudo_trades=2,
        policy_hash=world.world_id + "-policy",
        action_catalog_hash=world.world_id + "-catalog"),
        run_dir=f"/tmp/ef-cal-{world.world_id}")

    sc = CapstoneScenario(
        scenario_id=f"{world.world_id}-{method_id}",
        seller_id="seller-1", buyer_id="buyer-1")
    sc.trainer.update({"epochs": 1, "batch_size": 128})
    sc.split_seed = sh.split
    sc.buyer_task["deployment_scale"] = 2000
    sc.audit["privacy_budget"] = {"max_unique_rows": 100, "max_fraction": 0.2}
    sc.rights["audit_reveal_max_rows"] = 100

    orch = TransactionOrchestrator(sc, run_dir=f"/tmp/ef-run-{world.world_id}",
                                   calibration=cal)
    res = orch.run()
    audit = orch._stages["audit"].output
    pricing = orch._stages["pricing"].output
    # artifact hash 全部来自真实运行产出（禁止占位 hash）
    from valor.core.hashing import content_hash

    stage_plain = {k: v.output for k, v in orch._stages.items()}
    return {
        "metrics": {
            "clearing_price": res.clearing_price or 0.0,
            "n_audit_steps": audit.get("n_steps", 0),
            "audit_pay": audit.get("audit_pay_s", 0.0) + audit.get("audit_pay_b", 0.0),
            "disclosure_fraction": audit.get("disclosure_fraction", 0.0),
        },
        "terminal_state": res.terminal_state,
        "run_manifest_hash": content_hash({"run_id": orch.run_id,
                                           "scenario_hash": res.scenario_hash}),
        "trace_hash": content_hash(stage_plain),
        "artifact_root_hash": content_hash({
            "run_id": orch.run_id, "manifest": content_hash({"scenario_hash": res.scenario_hash}),
            "trace": content_hash(stage_plain),
        }),
    }


__all__ = ["capstone_trial_executor"]
