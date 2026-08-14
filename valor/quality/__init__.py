"""质量验证层（规范 §7–§15 / Phase 1）。

QualityPrimitive → QualityAction → AuditPolicy（§7 三层禁止混用）。

Phase 1 交付：
- models:      QualityAlgorithmSpec / PrimitiveOutput / QualityReproductionCertificate（§14/§15）
- catalog:     质量算法目录（distributed_enabled 由 Gate B 控制）
- equivalence: 确定性/浮点/随机 3 类等价规则（§15.1–15.3）
- reproduction: Reference Reproduction Gate Q0（§15/§47）
- native/:     NativeConfidentLearning / structural / duplicates / ks_shift / categorical_shift / mmd / metadata_claims
- reference/:  deequ_adapter / cleanlab_adapter / scipy_stats_adapter
"""

from .models import (
    PrimitiveOutput,
    QualityAlgorithmSpec,
    QualityReproductionCertificate,
)
from .catalog import QualityAlgorithmCatalog
from .reproduction import reproduce_algorithm, run_reproduction_gate

__all__ = [
    "PrimitiveOutput",
    "QualityAlgorithmSpec",
    "QualityReproductionCertificate",
    "QualityAlgorithmCatalog",
    "reproduce_algorithm",
    "run_reproduction_gate",
]
