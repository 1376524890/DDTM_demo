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

    if state == "L":
        low = scenario.audit.get("low_suitability_world")
        if low is None:
            raise ValueError(
                "L world requires scenario.audit.low_suitability_world "
                "(buyer-specific suitability < threshold); random label flip "
                "is not an acceptable L world")
        method = low.get("method")
        if method == "buyer_task_utility":
            threshold = float(low.get("threshold", 0.0))
            utility = np.asarray(low.get("row_utilities", []), dtype=float)
            if len(utility) != len(yy):
                raise ValueError("low_suitability_world.row_utilities length mismatch")
            idx = np.where(utility < threshold)[0]
            if len(idx) == 0:
                raise ValueError("L world has no rows below suitability threshold")
            ground_truth_ref = low.get("ground_truth_ref", "rcal-L-buyer-task-utility")
        else:
            raise ValueError(f"unsupported low_suitability_world method: {method}")
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
    )


__all__ = ["ExperimentWorld", "build_experiment_world"]
