"""ExperimentWorld construction for R_cal/R_cert (Round 5 §3).

Ground truth worlds:
  G: seller honest, committed data authentic, claim truthful, suitable.
  L: seller honest, committed data authentic, claim truthful, but buyer-specific
     task suitability is below threshold (no tampering; ground truth ref marks L).
  B: seller breach using a real breach mechanism family from the frozen design.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from valor.core.hashing import content_hash
from valor.privacy_audit import ClaimType, CommittedDatasetStore
from valor.seller import SellerCommittedDataset


@dataclass(frozen=True)
class ExperimentWorld:
    seller: Any
    y_committed: np.ndarray
    state: str
    ground_truth_ref: str
    breach_family: str
    suitability_metric: float | None = None
    suitability_threshold: float | None = None
    construction_hash: str = ""


@dataclass(frozen=True)
class LowSuitabilityWorldBuilderResult:
    X_L: np.ndarray
    y_L: np.ndarray
    suitability_metric: float
    suitability_threshold: float
    truthful_claim: dict
    construction_hash: str


class LowSuitabilityWorldBuilder:
    """Build a materially different L world (buyer-specific low suitability).

    Seller stays honest: the committed dataset is authentic, the claim is the
    truthful aggregate claim of that dataset, and no tampering is applied.
    The L dataset is a strict subset selected by buyer-task suitability below
    the threshold, so suitability(L) < threshold <= suitability(G).
    """

    def __init__(self, *, method: str, threshold: float,
                 row_utilities: np.ndarray, buyer_task: dict,
                 trainer_family_hash: str, claim_type: str,
                 task_family_hash: str) -> None:
        self.method = method
        self.threshold = float(threshold)
        self.row_utilities = np.asarray(row_utilities, dtype=float)
        self.buyer_task = buyer_task
        self.trainer_family_hash = trainer_family_hash
        self.claim_type = claim_type
        self.task_family_hash = task_family_hash

    def suitability(self, indices: np.ndarray | None = None) -> float:
        if indices is None or len(indices) == 0:
            return float(np.mean(self.row_utilities))
        return float(np.mean(self.row_utilities[indices]))

    def build(self, X: np.ndarray, y: np.ndarray) -> LowSuitabilityWorldBuilderResult:
        if self.method != "buyer_task_utility":
            raise ValueError(f"unsupported low_suitability_world method: {self.method}")
        X = np.asarray(X, dtype=np.uint8)
        y = np.asarray(y, dtype=np.int64)
        if len(self.row_utilities) != len(X):
            raise ValueError(
                "low_suitability_world.row_utilities length must match the "
                "candidate dataset size")
        suitability_G = self.suitability()
        if suitability_G < self.threshold:
            raise ValueError(
                f"G world suitability {suitability_G} must be >= threshold "
                f"{self.threshold}")
        idx = np.where(self.row_utilities < self.threshold)[0]
        if len(idx) == 0:
            raise ValueError("L world has no rows below suitability threshold")
        X_L = X[idx]
        y_L = y[idx]
        suitability_L = self.suitability(idx)
        if suitability_L >= self.threshold:
            raise ValueError(
                f"L world suitability {suitability_L} must be < threshold "
                f"{self.threshold}")
        truthful_claim = {
            "claim_type": self.claim_type,
            "suitability_metric": "buyer_task_utility",
            "suitability": suitability_L,
            "threshold": self.threshold,
            "n_rows": int(len(y_L)),
            "buyer_task_id": self.buyer_task.get("task_id"),
        }
        construction_hash = content_hash({
            "method": self.method,
            "threshold": self.threshold,
            "suitability_G": suitability_G,
            "suitability_L": suitability_L,
            "n_rows_G": int(len(y)),
            "n_rows_L": int(len(y_L)),
            "trainer_family_hash": self.trainer_family_hash,
            "task_family_hash": self.task_family_hash,
            "truthful_claim": truthful_claim,
        })
        return LowSuitabilityWorldBuilderResult(
            X_L=X_L, y_L=y_L,
            suitability_metric=suitability_L,
            suitability_threshold=self.threshold,
            truthful_claim=truthful_claim,
            construction_hash=construction_hash,
        )


def build_experiment_world(
    *,
    scenario: Any,
    store: CommittedDatasetStore,
    X: np.ndarray,
    y: np.ndarray,
    role_id: str,
    state: str,
    k: int,
    run: int,
) -> ExperimentWorld:
    """Build one immutable G/L/B world with real commitment + optional breach."""
    X = np.asarray(X, dtype=np.uint8)
    y = np.asarray(y, dtype=np.int64)
    yy = y.copy()
    breach_family = ""
    ground_truth_ref = ""

    suitability_metric = None
    suitability_threshold = None
    construction_hash = ""
    if state == "L":
        low = scenario.audit.get("low_suitability_world")
        if low is None:
            raise ValueError(
                "L world requires scenario.audit.low_suitability_world "
                "(buyer-specific suitability < threshold); random label flip "
                "is not an acceptable L world")
        builder = LowSuitabilityWorldBuilder(
            method=low.get("method", "buyer_task_utility"),
            threshold=float(low.get("threshold", 0.0)),
            row_utilities=low.get("row_utilities", []),
            buyer_task=scenario.buyer_task,
            trainer_family_hash=content_hash(scenario.trainer),
            task_family_hash=content_hash(scenario.buyer_task),
            claim_type="LABEL_DISTRIBUTION",
        )
        low_result = builder.build(X, y)
        X = low_result.X_L
        yy = low_result.y_L.copy()
        suitability_metric = low_result.suitability_metric
        suitability_threshold = low_result.suitability_threshold
        construction_hash = low_result.construction_hash
        ground_truth_ref = low.get("ground_truth_ref", "rcal-L-buyer-task-utility")
    elif state == "B":
        breach = scenario.audit.get("breach_world")
        if breach is None:
            raise ValueError(
                "B world requires scenario.audit.breach_world with a real "
                "breach mechanism (CLAIM_FALSE/POST_COMMIT_DATA_TAMPER/...)")
        family = breach.get("family")
        if family == "POST_COMMIT_DATA_TAMPER":
            breach_family = "POST_COMMIT_DATA_TAMPER"
        elif family == "CLAIM_FALSE":
            breach_family = "CLAIM_FALSE"
        elif family == "OPENING_TAMPER":
            breach_family = "OPENING_TAMPER"
        elif family == "VERSION_MISMATCH":
            raise NotImplementedError("VERSION_MISMATCH breach world not yet implemented")
        else:
            raise ValueError(f"unsupported breach family: {family}")
        ground_truth_ref = breach.get("ground_truth_ref", "rcal-B-post-commit-data-tamper")
    else:
        ground_truth_ref = "seller_honest_authentic_suitable"
        low = scenario.audit.get("low_suitability_world")
        if low is not None and low.get("method") == "buyer_task_utility":
            utility = np.asarray(low.get("row_utilities", []), dtype=float)
            if len(utility) == len(yy):
                suitability_metric = float(np.mean(utility))
                suitability_threshold = float(low.get("threshold", 0.0))
                construction_hash = content_hash({
                    "state": "G",
                    "suitability": suitability_metric,
                    "threshold": suitability_threshold,
                })

    dataset_id = f"{role_id}-{state}-{k}-{run}"
    seller = SellerCommittedDataset.create(
        store, dataset_id=dataset_id, version="v1",
        X=X, y=yy, schema_hash=content_hash({"schema": "MNIST-784"})[:64],
    )
    if state == "B" and breach_family == "POST_COMMIT_DATA_TAMPER":
        breach = scenario.audit.get("breach_world")
        rng = np.random.default_rng(run)
        n = len(yy)
        tamper_count = int(breach.get("tamper_fraction", 0.2) * n)
        idx = rng.choice(n, size=max(1, tamper_count), replace=False)
        for i in idx:
            old = int(yy[i])
            store.tamper_row(
                seller.dataset_id, int(i),
                new_y=rng.choice([c for c in range(10) if c != old]))
    return ExperimentWorld(
        seller=seller, y_committed=yy, state=state,
        ground_truth_ref=ground_truth_ref, breach_family=breach_family,
        suitability_metric=suitability_metric,
        suitability_threshold=suitability_threshold,
        construction_hash=construction_hash,
    )


__all__ = [
    "ExperimentWorld", "LowSuitabilityWorldBuilder",
    "LowSuitabilityWorldBuilderResult", "build_experiment_world",
]
