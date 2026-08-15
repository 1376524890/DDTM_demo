"""AggregateClaim —— 卖方对数据集聚合统计的声明（方案 §7）。

语义：seller claims this statistic（不是 cryptographic proof）。
MNIST 第一版只支持：
    ROW_COUNT / LABEL_DISTRIBUTION / PIXEL_MEAN / PIXEL_VARIANCE /
    ZERO_FRACTION / VALUE_RANGE / DUPLICATE_RATE
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np

from valor.core.hashing import content_hash

from .models import ClaimType


@dataclass(frozen=True)
class AggregateClaim:
    claim_id: str
    claim_type: ClaimType
    value: Any
    algorithm_spec_hash: str
    parameter_manifest_hash: str
    dataset_commitment_hash: str
    created_at: str
    claim_hash: str

    def to_plain(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type.value,
            "value": self.value,
            "algorithm_spec_hash": self.algorithm_spec_hash,
            "parameter_manifest_hash": self.parameter_manifest_hash,
            "dataset_commitment_hash": self.dataset_commitment_hash,
            "created_at": self.created_at,
            "claim_hash": self.claim_hash,
        }

    @classmethod
    def from_plain(cls, d: dict) -> "AggregateClaim":
        return cls(
            claim_id=d["claim_id"], claim_type=ClaimType(d["claim_type"]),
            value=d["value"], algorithm_spec_hash=d["algorithm_spec_hash"],
            parameter_manifest_hash=d["parameter_manifest_hash"],
            dataset_commitment_hash=d["dataset_commitment_hash"],
            created_at=d["created_at"], claim_hash=d["claim_hash"],
        )


def _compute_hash(claim_type, value, alg, param, commit_hash, created_at) -> str:
    return content_hash({
        "claim_type": claim_type.value, "value": value,
        "algorithm_spec_hash": alg, "parameter_manifest_hash": param,
        "dataset_commitment_hash": commit_hash, "created_at": created_at,
    })


def make_claim(
    *,
    claim_type: ClaimType,
    value: Any,
    dataset_commitment_hash: str,
    algorithm_spec_hash: str = "",
    parameter_manifest_hash: str = "",
    claim_id: str = "",
) -> AggregateClaim:
    """构造声明（自动 hash）。"""
    created_at = datetime.now(timezone.utc).isoformat()
    if not claim_id:
        claim_id = f"claim-{content_hash({'t': claim_type.value, 'v': value})[:12]}"
    claim_hash = _compute_hash(claim_type, value, algorithm_spec_hash,
                               parameter_manifest_hash, dataset_commitment_hash,
                               created_at)
    return AggregateClaim(
        claim_id=claim_id, claim_type=claim_type, value=value,
        algorithm_spec_hash=algorithm_spec_hash,
        parameter_manifest_hash=parameter_manifest_hash,
        dataset_commitment_hash=dataset_commitment_hash,
        created_at=created_at, claim_hash=claim_hash,
    )


# ---------------------------------------------------------------------------
# 从数据生成声明（卖方在明文上计算）
# ---------------------------------------------------------------------------
def claim_from_data(
    *, claim_type: ClaimType, X: np.ndarray, y: np.ndarray,
    dataset_commitment_hash: str, algorithm_spec_hash: str = "",
) -> AggregateClaim:
    """在明文数据上计算声明值。"""
    if claim_type == ClaimType.ROW_COUNT:
        value = int(len(X))
    elif claim_type == ClaimType.LABEL_DISTRIBUTION:
        counts, _ = np.histogram(y, bins=10, range=(0, 10))
        value = {str(c): float(counts[c]) for c in range(10)}
    elif claim_type == ClaimType.PIXEL_MEAN:
        value = float(np.mean(X))
    elif claim_type == ClaimType.PIXEL_VARIANCE:
        value = float(np.var(X))
    elif claim_type == ClaimType.ZERO_FRACTION:
        value = float(np.mean(X == 0))
    elif claim_type == ClaimType.VALUE_RANGE:
        value = [float(np.min(X)), float(np.max(X))]
    elif claim_type == ClaimType.DUPLICATE_RATE:
        value = float(_exact_dup_rate(X))
    else:
        raise ValueError(f"未知 claim_type: {claim_type}")
    return make_claim(
        claim_type=claim_type, value=value,
        dataset_commitment_hash=dataset_commitment_hash,
        algorithm_spec_hash=algorithm_spec_hash,
    )


def _exact_dup_rate(X: np.ndarray) -> float:
    if len(X) == 0:
        return 0.0
    from valor.core.hashing import content_hash

    seen = set()
    dup = 0
    for i in range(len(X)):
        h = content_hash(X[i].tobytes())
        if h in seen:
            dup += 1
        else:
            seen.add(h)
    return dup / len(X)


__all__ = ["AggregateClaim", "make_claim", "claim_from_data"]
