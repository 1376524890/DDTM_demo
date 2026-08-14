"""原生 Python 质量 primitive 复现（规范 §9–§13）。

每个函数返回 PrimitiveOutput；参数来自 ResolvedParameter（fail-closed）。
"""

from .structural import run_structural
from .duplicates import run_exact_duplicates
from .confident_learning import run_confident_learning
from .ks_shift import run_ks_shift
from .categorical_shift import run_categorical_shift
from .mmd import run_mmd
from .metadata_claims import run_metadata_claim_audit

__all__ = [
    "run_structural",
    "run_exact_duplicates",
    "run_confident_learning",
    "run_ks_shift",
    "run_categorical_shift",
    "run_mmd",
    "run_metadata_claim_audit",
]
