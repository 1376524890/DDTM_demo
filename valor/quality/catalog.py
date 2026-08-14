"""质量算法目录（规范 §14）。

每个可用 primitive 注册为 QualityAlgorithmSpec。distributed_enabled 在
Reference Reproduction Gate 通过前必须为 False（§14）。
"""

from __future__ import annotations

from .models import QualityAlgorithmSpec
from . import models as _models


def _source_hash(module_name: str) -> str:
    """对模块源码计算 code_hash（规范 §14 code_hash）。"""
    import importlib

    mod = importlib.import_module(module_name)
    from valor.core.hashing import sha256_hex

    return sha256_hex(
        open(mod.__file__, "rb").read()
    ) if mod.__file__ else "no-source"


def default_catalog() -> "QualityAlgorithmCatalog":
    """构建 Phase 1 默认质量算法目录（§14 注册表）。"""
    cat = QualityAlgorithmCatalog()
    from valor.core.enums import MigrationClass, QualityImplementationKind

    NATIVE = QualityImplementationKind.NATIVE
    REFERENCE = QualityImplementationKind.REFERENCE
    cat.register(QualityAlgorithmSpec(
        algorithm_id="structural",
        family="structural",
        implementation_kind=NATIVE,
        source_title="Deequ semantics (Schelter et al. 2018)",
        source_version="deequ-semantics",
        code_hash=_source_hash("valor.quality.native.structural"),
        runtime_image_hash="python-3.14",
        input_schema_hash="tabular",
        output_schema_hash="structural-metrics",
        required_parameters=(),
        determinism_spec="deterministic",
        migration_class=MigrationClass.MERGEABLE_EXACT,
        equivalence_rule=_models.DETERMINISTIC,
    ))
    cat.register(QualityAlgorithmSpec(
        algorithm_id="exact_duplicates",
        family="duplicate",
        implementation_kind=NATIVE,
        source_title="Canonical row hash duplicate detection",
        source_version="1.0",
        code_hash=_source_hash("valor.quality.native.duplicates"),
        runtime_image_hash="python-3.14",
        input_schema_hash="tabular",
        output_schema_hash="duplicate-metrics",
        required_parameters=(),
        determinism_spec="deterministic",
        migration_class=MigrationClass.MERGEABLE_EXACT,
        equivalence_rule=_models.DETERMINISTIC,
    ))
    cat.register(QualityAlgorithmSpec(
        algorithm_id="confident_learning",
        family="confident_learning",
        implementation_kind=NATIVE,
        source_title="Confident Learning (Northcutt et al. 2021)",
        source_version="paper-mean-threshold",
        code_hash=_source_hash("valor.quality.native.confident_learning"),
        runtime_image_hash="python-3.14",
        input_schema_hash="tabular+oof-probs",
        output_schema_hash="cl-metrics",
        required_parameters=("threshold_method",),
        determinism_spec="stochastic",
        migration_class=MigrationClass.MODEL_BASED_REPLICATED,
        equivalence_rule=_models.FLOATING,
    ))
    cat.register(QualityAlgorithmSpec(
        algorithm_id="ks_shift",
        family="shift",
        implementation_kind=NATIVE,
        source_title="Two-sample Kolmogorov-Smirnov",
        source_version="1.0",
        code_hash=_source_hash("valor.quality.native.ks_shift"),
        runtime_image_hash="python-3.14",
        input_schema_hash="tabular-continuous",
        output_schema_hash="ks-metrics",
        required_parameters=("column", "alpha_shift"),
        determinism_spec="floating",
        migration_class=MigrationClass.GLOBAL_STATISTIC,
        equivalence_rule=_models.FLOATING,
    ))
    cat.register(QualityAlgorithmSpec(
        algorithm_id="categorical_shift",
        family="shift",
        implementation_kind=NATIVE,
        source_title="Categorical distribution shift (chi-square)",
        source_version="1.0",
        code_hash=_source_hash("valor.quality.native.categorical_shift"),
        runtime_image_hash="python-3.14",
        input_schema_hash="tabular-categorical",
        output_schema_hash="categorical-metrics",
        required_parameters=("column", "alpha_shift"),
        determinism_spec="floating",
        migration_class=MigrationClass.GLOBAL_STATISTIC,
        equivalence_rule=_models.FLOATING,
    ))
    cat.register(QualityAlgorithmSpec(
        algorithm_id="mmd",
        family="mmd",
        implementation_kind=NATIVE,
        source_title="Unbiased Maximum Mean Discrepancy",
        source_version="1.0",
        code_hash=_source_hash("valor.quality.native.mmd"),
        runtime_image_hash="python-3.14",
        input_schema_hash="tabular-multivariate",
        output_schema_hash="mmd-metrics",
        required_parameters=("target_pvalue_resolution",),
        determinism_spec="floating",
        migration_class=MigrationClass.GLOBAL_STATISTIC,
        equivalence_rule=_models.FLOATING,
    ))
    cat.register(QualityAlgorithmSpec(
        algorithm_id="metadata_claim_audit",
        family="metadata",
        implementation_kind=NATIVE,
        source_title="MetadataClaimAudit (declared predicate)",
        source_version="1.0",
        code_hash=_source_hash("valor.quality.native.metadata_claims"),
        runtime_image_hash="python-3.14",
        input_schema_hash="tabular+claims",
        output_schema_hash="claim-metrics",
        required_parameters=("claims",),
        determinism_spec="deterministic",
        migration_class=MigrationClass.MERGEABLE_EXACT,
        equivalence_rule=_models.DETERMINISTIC,
    ))
    return cat


class QualityAlgorithmCatalog:
    """质量算法注册目录。"""

    def __init__(self) -> None:
        self._specs: dict[str, QualityAlgorithmSpec] = {}

    def register(self, spec: QualityAlgorithmSpec) -> None:
        self._specs[spec.algorithm_id] = spec

    def get(self, algorithm_id: str) -> QualityAlgorithmSpec:
        return self._specs[algorithm_id]

    def set_distributed_enabled(self, algorithm_id: str, enabled: bool) -> None:
        """Gate B 通过后置 distributed_enabled=True（§14）。"""
        s = self._specs[algorithm_id]
        self._specs[algorithm_id] = QualityAlgorithmSpec(
            algorithm_id=s.algorithm_id,
            family=s.family,
            implementation_kind=s.implementation_kind,
            source_title=s.source_title,
            source_version=s.source_version,
            code_hash=s.code_hash,
            runtime_image_hash=s.runtime_image_hash,
            input_schema_hash=s.input_schema_hash,
            output_schema_hash=s.output_schema_hash,
            required_parameters=s.required_parameters,
            determinism_spec=s.determinism_spec,
            migration_class=s.migration_class,
            equivalence_rule=s.equivalence_rule,
            distributed_enabled=enabled,
        )

    def list_ids(self) -> list[str]:
        return sorted(self._specs)

    def distributed_ids(self) -> list[str]:
        return [
            aid for aid, s in self._specs.items() if s.distributed_enabled
        ]

    def to_plain(self) -> dict:
        return {
            aid: s.to_plain() for aid, s in self._specs.items()
        }
