"""ExperimentRunner + Resume（EF-G07/G14）。

对 paired plan 运行全部 trials，支持：
    - completed trial → skip（immutable hash 一致）
    - failed trial → retry policy（默认有限次重试）
    - missing trial → execute
    - failed trials 显式保留（不静默丢弃）
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .artifacts import ArtifactStore
from .pairing import PairedPlan
from .spec import TrialResult, TrialSpec

# trial 执行器契约：method_id + method_config + world -> TrialResult
TrialExecutor = Callable[[str, dict, object], dict]


class RetryPolicy:
    """失败重试策略。"""

    def __init__(self, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    def should_retry(self, attempt: int) -> bool:
        return attempt < self.max_retries


@dataclass
class RunSummary:
    planned: int = 0
    executed: int = 0
    skipped: int = 0
    failed: int = 0
    failed_trials: list[str] = field(default_factory=list)

    def to_plain(self) -> dict:
        return {
            "planned": self.planned, "executed": self.executed,
            "skipped": self.skipped, "failed": self.failed,
            "failed_trials": self.failed_trials,
        }


class ExperimentRunner:
    """运行 paired plan，支持 resume。"""

    def __init__(
        self,
        *,
        plan: PairedPlan,
        store: ArtifactStore,
        executor: TrialExecutor,
        manifest_builder: Callable[[TrialSpec], dict],
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.plan = plan
        self.store = store
        self.executor = executor
        self.manifest_builder = manifest_builder
        self.retry_policy = retry_policy or RetryPolicy()

    def run(self, *, resume: bool = True) -> RunSummary:
        trials = self.plan.trials()
        summary = RunSummary(planned=len(trials))
        for trial in trials:
            outcome = self._run_one(trial, resume=resume)
            if outcome == "executed":
                summary.executed += 1
            elif outcome == "skipped":
                summary.skipped += 1
            elif outcome == "failed":
                summary.failed += 1
                summary.failed_trials.append(trial.trial_id)
        return summary

    def _run_one(self, trial: TrialSpec, *, resume: bool) -> str:
        # completed & immutable → skip
        if resume and self.store.is_immutable(trial.trial_id):
            return "skipped"
        attempt = 0
        last_err = None
        while True:
            try:
                t0 = time.perf_counter()
                metrics = self.executor(
                    trial.method_id, self.plan.method_configs.get(trial.method_id, {}),
                    trial.world)
                runtime_ms = (time.perf_counter() - t0) * 1000.0
                result = {
                    "trial_id": trial.trial_id,
                    "world_id": trial.world.world_id,
                    "method_id": trial.method_id,
                    "success": True,
                    "metrics": metrics.get("metrics", {}),
                    "terminal_state": metrics.get("terminal_state", ""),
                    "run_manifest_hash": metrics.get("run_manifest_hash", ""),
                    "trace_hash": metrics.get("trace_hash", ""),
                    "artifact_root_hash": metrics.get("artifact_root_hash", ""),
                    "runtime_ms": runtime_ms,
                    "error": None,
                }
                manifest = self.manifest_builder(trial)
                self.store.write_trial(trial.trial_id, result=result,
                                       manifest=manifest)
                return "executed"
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                attempt += 1
                if not self.retry_policy.should_retry(attempt):
                    # failed trial 显式保留（不静默丢弃）
                    self._record_failure(trial, last_err)
                    return "failed"

    def _record_failure(self, trial: TrialSpec, err: str) -> None:
        result = {
            "trial_id": trial.trial_id, "world_id": trial.world.world_id,
            "method_id": trial.method_id, "success": False, "metrics": {},
            "terminal_state": "", "run_manifest_hash": "", "trace_hash": "",
            "artifact_root_hash": "", "runtime_ms": 0.0, "error": err,
        }
        manifest = self.manifest_builder(trial)
        try:
            self.store.write_trial(trial.trial_id, result=result, manifest=manifest)
        except Exception:  # noqa: BLE001  失败记录本身失败则忽略（已保留 error）
            pass


__all__ = ["ExperimentRunner", "RetryPolicy", "RunSummary", "TrialExecutor"]
