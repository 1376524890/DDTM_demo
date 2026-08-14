"""Data-VOI 估值层（规范 §26–§28 / Phase 4）。

- oracle:          精确重训练 Oracle（真实 marginal task utility）
- economic_mapping: 用 cost-sensitive payoff 矩阵把效用映射为货币 [CU]
- exposure:        竞争外部性 L_b^comp（§26）
- calibration:     价值校准 → V̲_{D,R}^gross 保守下界（§28）
- 估值器：loo/data_shapley/data_banzhaf/forward_influence/data_oob/knn_shapley
"""

from .oracle import OracleRetraining, exact_retraining_utility
from .economic_mapping import PayoffMatrix, utility_from_predictions, gross_value
from .exposure import competition_externality
from .calibration import value_lower_bound_quantile, ValueCalibrator

__all__ = [
    "OracleRetraining",
    "exact_retraining_utility",
    "PayoffMatrix",
    "utility_from_predictions",
    "gross_value",
    "competition_externality",
    "value_lower_bound_quantile",
    "ValueCalibrator",
]
