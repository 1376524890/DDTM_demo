"""实验 Oracle（规范 §45/§65）。

- realised_value_oracle：在 FinalEvaluation 上计算真实 realised utility（§45，
  ExperimentalOracleFeedback 与 ProductionObservableFeedback 严格区分）。
- no_trade_oracle：Y_oracle = 1[P_max^oracle >= P_min^oracle]（§65）。
"""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import LogisticRegression

from valor.valuation.economic_mapping import PayoffMatrix, utility_from_predictions


def realised_value_oracle(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_eval: pd.DataFrame,
    y_eval: pd.Series,
    payoff: PayoffMatrix,
) -> float:
    """FinalEvaluation 上的真实 realised utility V^real（§45/§65）。"""
    m = LogisticRegression(max_iter=800)
    m.fit(X_train.fillna(0), y_train.to_numpy().astype(int))
    pred = m.predict(X_eval.fillna(0))
    return utility_from_predictions(y_eval.to_numpy().astype(int), pred, payoff)


def no_trade_oracle(p_max: float, p_min: float) -> bool:
    """Y_oracle = 1[P_max^oracle ≥ P_min^oracle]（§65 NO_TRADE Oracle）。"""
    return p_max >= p_min
