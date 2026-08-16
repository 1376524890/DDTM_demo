"""VALOR Experiment Framework V2 —— 论文实验运行基础设施。

原则：
- 一个 trial 先生成「世界」（WorldSpec），method 只改变策略，不改变世界（paired）。
- seed hierarchy：S_x = H(S_master ∥ namespace_x)。
- R_cal / R_cert / R_eval 三集合隔离。
- immutable raw artifact（hash 一致 skip / 不一致 REPRODUCIBILITY_VIOLATION）。
- resume 支持（completed skip / failed retry / missing execute）。
- 统一统计：bootstrap CI + paired t/Wilcoxon + Cohen's dz/rank-biserial + Holm。
"""

from __future__ import annotations

from .seeds import SeedHierarchy, derive_seed
from .spec import (
    ExperimentSpec,
    TrialResult,
    TrialSpec,
    WorldSpec,
    make_experiment_spec,
    make_world,
)
from .registry import (
    DataRoleRegistry,
    DataSplitIsolationError,
    validate_role_isolation,
)
from .pairing import PairedPlan, build_paired_plan
from .artifacts import (
    ArtifactStore,
    ArtifactReproducibilityViolation,
    REPRODUCIBILITY_VIOLATION,
    artifact_root_hash,
    build_manifest,
)
from .runner import ExperimentRunner, RetryPolicy, RunSummary
from .analysis import AnalysisRunner, PairedAnalysis
from .reconciliation import ReconciliationCase, level1_reconciliation

__all__ = [
    "SeedHierarchy", "derive_seed",
    "ExperimentSpec", "TrialResult", "TrialSpec", "WorldSpec",
    "make_experiment_spec", "make_world",
    "DataRoleRegistry", "DataSplitIsolationError", "validate_role_isolation",
    "PairedPlan", "build_paired_plan",
    "ArtifactStore", "ArtifactReproducibilityViolation",
    "REPRODUCIBILITY_VIOLATION", "artifact_root_hash", "build_manifest",
    "ExperimentRunner", "RetryPolicy", "RunSummary",
    "AnalysisRunner", "PairedAnalysis",
    "ReconciliationCase", "level1_reconciliation",
]
