"""质量层核心模型（规范 §14 / §15 / §54.2）。

QualityPrimitive 是单一已有算法或确定性检查。每个可用 primitive 必须注册为
QualityAlgorithmSpec；进入分布式层前须有 QualityReproductionCertificate（Gate B）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.enums import MigrationClass, QualityImplementationKind
from valor.core.hashing import content_hash

# 复现等价规则类型（§15.1–15.3）
DETERMINISTIC = "deterministic"
FLOATING = "floating"
STOCHASTIC = "stochastic"
GROUND_TRUTH = "ground_truth"


@dataclass(frozen=True)
class QualityAlgorithmSpec:
    """质量算法规格（§14 / §54.2）。"""

    algorithm_id: str
    family: str  # structural | duplicate | confident_learning | shift | mmd | metadata
    implementation_kind: QualityImplementationKind
    source_title: str
    source_version: str  # 论文/包版本
    code_hash: str
    runtime_image_hash: str
    input_schema_hash: str
    output_schema_hash: str
    required_parameters: tuple[str, ...]
    determinism_spec: str  # DETERMINISTIC | FLOATING | STOCHASTIC
    migration_class: MigrationClass
    equivalence_rule: str = DETERMINISTIC
    distributed_enabled: bool = False  # Gate B 通过前必须为 False（§14）

    def spec_hash(self) -> str:
        """算法规格哈希（§16 节点承诺用）。"""
        return content_hash(self.to_plain())

    def to_plain(self) -> dict:
        return {
            "algorithm_id": self.algorithm_id,
            "family": self.family,
            "implementation_kind": self.implementation_kind.value,
            "source_title": self.source_title,
            "source_version": self.source_version,
            "code_hash": self.code_hash,
            "runtime_image_hash": self.runtime_image_hash,
            "input_schema_hash": self.input_schema_hash,
            "output_schema_hash": self.output_schema_hash,
            "required_parameters": list(self.required_parameters),
            "determinism_spec": self.determinism_spec,
            "migration_class": self.migration_class.value,
            "equivalence_rule": self.equivalence_rule,
            "distributed_enabled": self.distributed_enabled,
        }


@dataclass(frozen=True)
class PrimitiveOutput:
    """单节点 primitive 输出（§7 λ_p^prim 的结果载体）。"""

    algorithm_id: str
    metrics: dict[str, Any]  # 可解释统计量（非任意加权总分）
    detail: dict[str, Any] = field(default_factory=dict)

    def output_hash(self) -> str:
        """canonical 输出哈希（§15.1 确定性 primitive 完全一致用）。

        仅对 metrics+detail 取哈希（不含 algorithm_id），使 reference 与
        native 在同一算法内可直接比较输出等价。
        """
        return content_hash({"metrics": self.metrics, "detail": self.detail})

    def to_plain(self) -> dict:
        return {
            "algorithm_id": self.algorithm_id,
            "metrics": self.metrics,
            "detail": self.detail,
            "output_hash": self.output_hash(),
        }


@dataclass(frozen=True)
class ReproductionComparison:
    """复现比较结果（metric_comparison / statistical_equivalence_result）。"""

    passed: bool
    metric: str
    reference_value: float
    native_value: float
    tolerance: float | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_plain(self) -> dict:
        return {
            "passed": self.passed,
            "metric": self.metric,
            "reference_value": self.reference_value,
            "native_value": self.native_value,
            "tolerance": self.tolerance,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class QualityReproductionCertificate:
    """Reference Reproduction Gate 证书（§15 / §47）。"""

    certificate_id: str
    algorithm_id: str
    reference_impl_hash: str
    native_impl_hash: str
    reference_dataset_hashes: tuple[str, ...]
    injection_spec_hashes: tuple[str, ...]
    parameter_manifest_hash: str
    metric_comparison: tuple[ReproductionComparison, ...]
    runtime_comparison: dict[str, Any]
    statistical_equivalence_result: dict[str, Any]
    created_at: str
    passed: bool

    def to_plain(self) -> dict:
        return {
            "certificate_id": self.certificate_id,
            "algorithm_id": self.algorithm_id,
            "reference_impl_hash": self.reference_impl_hash,
            "native_impl_hash": self.native_impl_hash,
            "reference_dataset_hashes": list(self.reference_dataset_hashes),
            "injection_spec_hashes": list(self.injection_spec_hashes),
            "parameter_manifest_hash": self.parameter_manifest_hash,
            "metric_comparison": [c.to_plain() for c in self.metric_comparison],
            "runtime_comparison": self.runtime_comparison,
            "statistical_equivalence_result": self.statistical_equivalence_result,
            "created_at": self.created_at,
            "passed": self.passed,
        }
