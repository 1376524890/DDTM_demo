"""精确重训练 Oracle（规范 §26 / Phase 4）。

真实 marginal task utility：
    ΔU_D^* = U(θ_{D_existing ∪ D}) - U(θ_{D_existing})
用严格验证集（ValuationValidation/FinalEvaluation）评估，避免 data leakage。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .economic_mapping import PayoffMatrix, utility_from_predictions


def _fit_predict(model, X_train, y_train, X_test):
    model.fit(X_train, y_train)
    return model.predict(X_test)


def exact_retraining_utility(
    *,
    X_base: pd.DataFrame,
    y_base: pd.Series,
    X_batch: pd.DataFrame,
    y_batch: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    payoff: PayoffMatrix,
    model_factory=None,
    seed: int = 0,
) -> tuple[float, float]:
    """返回 (U_base, U_base_plus)；ΔU = U_base_plus - U_base。"""
    from sklearn.linear_model import LogisticRegression

    model = model_factory() if model_factory else LogisticRegression(max_iter=1000)
    y_base_v = y_base.to_numpy().astype(int)
    y_val_v = y_val.to_numpy().astype(int)

    u_base = utility_from_predictions(
        y_val_v, _fit_predict(model, X_base.fillna(0), y_base_v, X_val.fillna(0)), payoff
    )
    # base + batch 联合训练
    X_all = pd.concat([X_base, X_batch], ignore_index=True)
    y_all = pd.concat([y_base, y_batch], ignore_index=True)
    model2 = model_factory() if model_factory else LogisticRegression(max_iter=1000)
    u_plus = utility_from_predictions(
        y_val_v, _fit_predict(model2, X_all.fillna(0), y_all.to_numpy().astype(int), X_val.fillna(0)), payoff
    )
    return u_base, u_plus


class OracleRetraining:
    """批次级精确重训练 Oracle（§26/§56 以 batch 为 player）。"""

    def __init__(self, payoff: PayoffMatrix, model_factory=None, seed: int = 0) -> None:
        self.payoff = payoff
        self.model_factory = model_factory
        self.seed = seed

    def marginal_value(self, X_base, y_base, X_batch, y_batch, X_val, y_val) -> float:
        u_base, u_plus = exact_retraining_utility(
            X_base=X_base, y_base=y_base, X_batch=X_batch, y_batch=y_batch,
            X_val=X_val, y_val=y_val, payoff=self.payoff,
            model_factory=self.model_factory, seed=self.seed,
        )
        return u_plus - u_base
