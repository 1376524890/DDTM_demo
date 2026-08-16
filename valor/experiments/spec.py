"""Experiment Framework V2 核心对象：ExperimentSpec / WorldSpec / TrialSpec / TrialResult。

原则：一个 trial 先生成「世界」（WorldSpec），method 只能改变策略，不能改变世界。
TrialSpec 不可变；trial_id = H(experimentID, worldHash, methodID, configHash)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash, sha256_hex


def _h(obj: Any) -> str:
    return content_hash(obj)


# ---------------------------------------------------------------------------
# WorldSpec：同一 underlying world（method 不允许修改）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WorldSpec:
    world_id: str
    seed: int  # master seed
    dataset_manifest_hash: str
    split_hash: str
    ground_truth_state: str  # G / L / B
    corruption_family: str | None = None
    corruption_severity: float | None = None
    auditor_pool_state: dict = field(default_factory=dict)
    auditor_costs: dict = field(default_factory=dict)
    offline_state: dict = field(default_factory=dict)
    adversarial_nodes: tuple[str, ...] = ()
    buyer_context_hash: str = ""
    world_hash: str = ""

    def to_plain(self) -> dict:
        return {
            "world_id": self.world_id,
            "seed": self.seed,
            "dataset_manifest_hash": self.dataset_manifest_hash,
            "split_hash": self.split_hash,
            "ground_truth_state": self.ground_truth_state,
            "corruption_family": self.corruption_family,
            "corruption_severity": self.corruption_severity,
            "auditor_pool_state": self.auditor_pool_state,
            "auditor_costs": self.auditor_costs,
            "offline_state": self.offline_state,
            "adversarial_nodes": list(self.adversarial_nodes),
            "buyer_context_hash": self.buyer_context_hash,
            "world_hash": self.world_hash,
        }


def make_world(*, world_id: str, seed: int, **kw) -> WorldSpec:
    """构造 WorldSpec 并计算 world_hash（确定性）。"""
    base = {k: v for k, v in kw.items() if k != "world_hash"}
    wh = _h({"world_id": world_id, "seed": seed, **base})
    return WorldSpec(world_id=world_id, seed=seed, world_hash=wh, **kw)


# ---------------------------------------------------------------------------
# ExperimentSpec：整个实验
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    rq: str
    methods: tuple[str, ...]
    seeds: tuple[int, ...]
    factors: dict = field(default_factory=dict)
    metrics: tuple[str, ...] = ()
    calibration_artifact_hash: str = ""
    certificate_hash: str = ""
    paired: bool = True
    git_commit: str = ""
    execution_mode: str = ""  # 必须显式冻结（FULL_DATA/COMMIT_CHALLENGE/...）
    spec_hash: str = ""

    def to_plain(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "rq": self.rq,
            "methods": list(self.methods),
            "seeds": list(self.seeds),
            "factors": self.factors,
            "metrics": list(self.metrics),
            "calibration_artifact_hash": self.calibration_artifact_hash,
            "certificate_hash": self.certificate_hash,
            "paired": self.paired,
            "git_commit": self.git_commit,
            "execution_mode": self.execution_mode,
            "spec_hash": self.spec_hash,
        }


def make_experiment_spec(
    *, experiment_id: str, rq: str, methods: tuple[str, ...], seeds: tuple[int, ...],
    factors: dict | None = None, metrics: tuple[str, ...] = (),
    calibration_artifact_hash: str = "", certificate_hash: str = "",
    paired: bool = True, git_commit: str = "", execution_mode: str = "",
) -> ExperimentSpec:
    """构造 ExperimentSpec 并计算 spec_hash。"""
    body = {
        "experiment_id": experiment_id, "rq": rq,
        "methods": list(methods), "seeds": list(seeds),
        "factors": factors or {}, "metrics": list(metrics),
        "calibration_artifact_hash": calibration_artifact_hash,
        "certificate_hash": certificate_hash, "paired": paired,
        "git_commit": git_commit, "execution_mode": execution_mode,
    }
    spec_hash = _h(body)
    return ExperimentSpec(**body, spec_hash=spec_hash)


# ---------------------------------------------------------------------------
# TrialSpec
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TrialSpec:
    experiment_id: str
    world: WorldSpec
    method_id: str
    method_config_hash: str
    trial_id: str

    @classmethod
    def build(
        cls, *, experiment_id: str, world: WorldSpec, method_id: str,
        method_config: dict,
    ) -> "TrialSpec":
        mch = _h(method_config)
        trial_id = sha256_hex(_h({
            "experiment_id": experiment_id, "world_hash": world.world_hash,
            "method_id": method_id, "method_config_hash": mch,
        }).encode())
        return cls(experiment_id=experiment_id, world=world, method_id=method_id,
                   method_config_hash=mch, trial_id=trial_id)

    def to_plain(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "world": self.world.to_plain(),
            "method_id": self.method_id,
            "method_config_hash": self.method_config_hash,
            "trial_id": self.trial_id,
        }


# ---------------------------------------------------------------------------
# TrialResult
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TrialResult:
    trial_id: str
    world_id: str
    method_id: str
    success: bool
    metrics: dict = field(default_factory=dict)
    terminal_state: str = ""
    run_manifest_hash: str = ""
    trace_hash: str = ""
    artifact_root_hash: str = ""
    runtime_ms: float = 0.0
    error: str | None = None

    def to_plain(self) -> dict:
        return {
            "trial_id": self.trial_id,
            "world_id": self.world_id,
            "method_id": self.method_id,
            "success": self.success,
            "metrics": self.metrics,
            "terminal_state": self.terminal_state,
            "run_manifest_hash": self.run_manifest_hash,
            "trace_hash": self.trace_hash,
            "artifact_root_hash": self.artifact_root_hash,
            "runtime_ms": self.runtime_ms,
            "error": self.error,
        }


__all__ = [
    "WorldSpec", "make_world", "ExperimentSpec", "make_experiment_spec",
    "TrialSpec", "TrialResult",
]
