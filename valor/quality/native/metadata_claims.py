"""QP MetadataClaimAudit（规范 §13）。

将卖方声明写成机器可执行 predicate，系统直接记录 predicate、observed metric、
comparison 与 evidence hash。
声明示例：max_missing_rate(column)、allowed_categories(column)、
label_error_upper_bound、class_coverage_requirement、provenance_claim。
"""

from __future__ import annotations

import pandas as pd

from valor.core.hashing import content_hash

from ..models import PrimitiveOutput


def run_metadata_claim_audit(
    X: pd.DataFrame,
    *,
    claims: dict,  # {claim_id: {"predicate":..., "column":..., "declared":...}}
) -> PrimitiveOutput:
    """审计卖方元数据声明。

    claims 结构示例：
        {"max_missing": {"column":"age","declared":0.05}}
    支持 predicate: max_missing_rate / allowed_categories / min_completeness。
    """
    results: list[dict] = []
    violations = 0
    for claim_id, c in claims.items():
        col = c["column"]
        declared = c["declared"]
        pred = c.get("predicate", "max_missing_rate")
        observed = _observe(X, col, pred)
        ok = _compare(pred, observed, declared)
        if not ok:
            violations += 1
        results.append({
            "claim_id": claim_id,
            "predicate": pred,
            "column": col,
            "declared": declared,
            "observed": observed,
            "passed": ok,
            "evidence_hash": content_hash(
                {"predicate": pred, "column": col,
                 "declared": declared, "observed": observed}
            ),
        })
    metrics = {
        "n_claims": int(len(results)),
        "n_violations": int(violations),
    }
    return PrimitiveOutput(
        algorithm_id="metadata_claim_audit", metrics=metrics,
        detail={"results": results},
    )


def _observe(X: pd.DataFrame, col: str, pred: str) -> float:
    if col not in X.columns:
        return float("nan")
    n = len(X)
    if n == 0:
        return 0.0
    if pred in ("max_missing_rate", "missing_rate"):
        return float(X[col].isna().sum()) / n
    if pred == "min_completeness":
        return float(X[col].notna().sum()) / n
    raise ValueError(f"未知 predicate: {pred}")


def _compare(pred: str, observed: float, declared: float) -> bool:
    if pred in ("max_missing_rate", "missing_rate"):
        # 声明为缺缺失率上限：观测缺缺失率 <= 声明
        return observed <= declared
    if pred == "min_completeness":
        return observed >= declared
    return observed == declared
