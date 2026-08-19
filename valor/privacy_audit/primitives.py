"""隐私审计抽样统计 primitive（PPA-3）。

只输入 openings（已解码的行），不接触全量数据。第一版 5 个：
    P1 RangeClaimAudit      像素∈[0,255]、label∈[0,9]
    P2 LabelDistributionAudit  抽样直方图 vs 声称直方图（multinomial GOF）
    P3 PixelMomentAudit     声称 mean/var 是否落入抽样 CI
    P4 MissingOrMalformedAudit  MNIST 行格式/标签合法性
    P5 DuplicateSampleAudit  challenge 行间重复 fingerprint（sampled evidence）

决策返回 PrimitiveResult：PASS / CLAIM_NOT_SUPPORTED / BREACH_EVIDENCE / INCONCLUSIVE。
Merkle opening 失败 → BREACH_EVIDENCE（由 executor 处理，不在本层）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .canonicalize import canonical_row_from_payload
from .models import ClaimType, DecisionRule, PrimitiveResult
from .opening import RowOpening


@dataclass(frozen=True)
class PrimitiveOutput:
    result: PrimitiveResult
    test_statistic: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    metrics: dict[str, Any] = None  # type: ignore

    def to_plain(self) -> dict:
        return {
            "result": self.result.value,
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "effect_size": self.effect_size,
            "metrics": self.metrics or {},
        }


def decode_openings(opening_list: list[RowOpening]) -> list[dict]:
    """解码 openings 为 {index, image(784,uint8), label}。"""
    rows = []
    for o in opening_list:
        idx, img, label = canonical_row_from_payload(o.row_payload, index=o.index)
        rows.append({"index": idx, "image": img, "label": int(label)})
    return rows


# ---- P1: RangeClaimAudit ----
def range_audit(rows: list[dict], *, expected_min: int = 0, expected_max: int = 255,
                n_classes: int = 10) -> PrimitiveOutput:
    violations = []
    for r in rows:
        img = r["image"]
        if img.min() < expected_min or img.max() > expected_max:
            violations.append({"index": r["index"], "kind": "pixel_range"})
        if not (0 <= r["label"] < n_classes):
            violations.append({"index": r["index"], "kind": "label_range"})
    if violations:
        return PrimitiveOutput(
            result=PrimitiveResult.CLAIM_NOT_SUPPORTED,
            metrics={"violations": violations[:20], "n_violations": len(violations)})
    return PrimitiveOutput(
        result=PrimitiveResult.PASS,
        metrics={"n_checked": len(rows), "n_violations": 0})


# ---- P2: LabelDistributionAudit ----
def label_distribution_audit(rows: list[dict], claim_value: dict,
                             *, n_classes: int = 10, alpha: float = 0.05) -> PrimitiveOutput:
    """抽样直方图 vs 声称分布，multinomial goodness-of-fit（chi-square）。"""
    from scipy.stats import chi2_contingency

    k = len(rows)
    if k == 0:
        return PrimitiveOutput(result=PrimitiveResult.INCONCLUSIVE, metrics={"k": 0})
    observed = np.zeros(n_classes, dtype=float)
    for r in rows:
        observed[r["label"]] += 1
    # 声称概率
    total_claim = sum(claim_value.values())
    if total_claim <= 0:
        return PrimitiveOutput(result=PrimitiveResult.CLAIM_NOT_SUPPORTED,
                               metrics={"reason": "claim 分布和为零"})
    expected = np.zeros(n_classes)
    for c in range(n_classes):
        expected[c] = k * float(claim_value.get(str(c), 0)) / total_claim
    # 仅对期望>0 的类做检验；期望过小（<5）合并到 INCONCLUSIVE
    mask = expected >= 5
    if mask.sum() < 2:
        return PrimitiveOutput(result=PrimitiveResult.INCONCLUSIVE,
                               metrics={"k": k, "reason": "期望计数过小"})
    obs = observed[mask]
    exp = expected[mask]
    # chi-square statistic（手动，避免 contingency table 语义错误）
    chi2 = float(np.sum((obs - exp) ** 2 / exp))
    dof = max(1, int(mask.sum()) - 1)
    from scipy.stats import chi2 as chi2_dist

    p_value = float(1.0 - chi2_dist.cdf(chi2, dof))
    if p_value < alpha:
        return PrimitiveOutput(
            result=PrimitiveResult.CLAIM_NOT_SUPPORTED,
            test_statistic=chi2, p_value=p_value, metrics={
                "k": k, "observed": observed.tolist(), "expected": expected.tolist()})
    return PrimitiveOutput(
        result=PrimitiveResult.PASS, test_statistic=chi2, p_value=p_value,
        metrics={"k": k})


# ---- P3: PixelMomentAudit ----
def pixel_moment_audit(rows: list[dict], claim_value: float, *, moment: str = "mean",
                       alpha: float = 0.05) -> PrimitiveOutput:
    """声称均值/方差是否落入抽样估计的置信区间。"""
    from scipy.stats import norm

    vals = np.concatenate([r["image"].astype(float) for r in rows])
    if len(vals) < 2:
        return PrimitiveOutput(result=PrimitiveResult.INCONCLUSIVE,
                               metrics={"n_pixels": len(vals)})
    if moment == "mean":
        m = float(vals.mean())
        se = float(vals.std(ddof=1)) / np.sqrt(len(vals))
    elif moment == "variance":
        m = float(vals.var(ddof=1))
        # 方差标准误近似（正态）
        se = float(np.sqrt(2.0 / (len(vals) - 1)) * m)
    else:
        raise ValueError(f"未知 moment: {moment}")
    z = norm.ppf(1 - alpha / 2)
    lo, hi = m - z * se, m + z * se
    in_ci = lo <= claim_value <= hi
    if in_ci:
        return PrimitiveOutput(
            result=PrimitiveResult.PASS, test_statistic=m,
            metrics={"claimed": claim_value, "ci": [lo, hi], "moment": moment})
    return PrimitiveOutput(
        result=PrimitiveResult.CLAIM_NOT_SUPPORTED, test_statistic=m,
        metrics={"claimed": claim_value, "ci": [lo, hi], "moment": moment})


# ---- P4: MissingOrMalformedAudit ----
def malformed_audit(rows: list[dict], *, n_features: int = 784) -> PrimitiveOutput:
    """MNIST 行格式/标签合法性（解码本身已校验尺寸；此处额外查 NaN/异常）。"""
    malformed = []
    for r in rows:
        img = r["image"]
        if img.shape[0] != n_features:
            malformed.append({"index": r["index"], "kind": "shape"})
        if not np.isfinite(img).all():
            malformed.append({"index": r["index"], "kind": "non_finite"})
    if malformed:
        return PrimitiveOutput(
            result=PrimitiveResult.CLAIM_NOT_SUPPORTED,
            metrics={"malformed": malformed[:20], "n": len(malformed)})
    return PrimitiveOutput(result=PrimitiveResult.PASS,
                           metrics={"n_checked": len(rows)})


# ---- P5: DuplicateSampleAudit ----
def duplicate_sample_audit(rows: list[dict]) -> PrimitiveOutput:
    """challenge 行间重复 fingerprint（只提供 sampled evidence，不声称全量重复率）。"""
    from valor.core.hashing import content_hash

    seen = set()
    dup = []
    for r in rows:
        h = content_hash(r["image"].tobytes())
        if h in seen:
            dup.append(r["index"])
        else:
            seen.add(h)
    rate = len(dup) / len(rows) if rows else 0.0
    return PrimitiveOutput(
        result=PrimitiveResult.PASS,
        metrics={"sampled_duplicate_rate": rate, "n_sampled": len(rows),
                 "duplicate_indices": dup})


PRIMITIVES = {
    "RangeClaimAudit": range_audit,
    "LabelDistributionAudit": label_distribution_audit,
    "PixelMomentAudit": pixel_moment_audit,
    "MissingOrMalformedAudit": malformed_audit,
    "DuplicateSampleAudit": duplicate_sample_audit,
}

# claim_type -> 支持的 primitive
CLAIM_TO_PRIMITIVE = {
    ClaimType.VALUE_RANGE: "RangeClaimAudit",
    ClaimType.LABEL_DISTRIBUTION: "LabelDistributionAudit",
    ClaimType.PIXEL_MEAN: "PixelMomentAudit",
    ClaimType.PIXEL_VARIANCE: "PixelMomentAudit",
    ClaimType.ROW_COUNT: "MissingOrMalformedAudit",
    ClaimType.DUPLICATE_RATE: "DuplicateSampleAudit",
}


def run_primitive(primitive_id: str, openings: list[RowOpening], claim) -> PrimitiveOutput:
    """按 primitive_id 运行；claim 为 AggregateClaim 或 None。"""
    rows = decode_openings(openings)
    if primitive_id == "RangeClaimAudit":
        return range_audit(rows)
    if primitive_id == "LabelDistributionAudit":
        return label_distribution_audit(rows, claim.value if claim else {})
    if primitive_id == "PixelMomentAudit":
        moment = "mean" if claim and claim.claim_type == ClaimType.PIXEL_MEAN else "variance"
        return pixel_moment_audit(rows, claim.value if claim else 0.0, moment=moment)
    if primitive_id == "MissingOrMalformedAudit":
        return malformed_audit(rows)
    if primitive_id == "DuplicateSampleAudit":
        return duplicate_sample_audit(rows)
    raise ValueError(f"未知 primitive: {primitive_id}")


__all__ = [
    "PrimitiveOutput", "decode_openings", "run_primitive",
    "range_audit", "label_distribution_audit", "pixel_moment_audit",
    "malformed_audit", "duplicate_sample_audit", "PRIMITIVES",
]
