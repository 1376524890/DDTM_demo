"""复现等价规则（规范 §15.1–15.3 / 检查单 Gate B）。

- deterministic primitive：canonical output 完全相等 H(native)==H(reference)
- floating statistical primitive：|v_native - v_ref| <= eps_alg(dtype, n, opGraph)
- stochastic/model-based primitive：固定 RandomnessSpec 后比较；不可消随机则
  paired repetitions 比较目标 metric 的 CI（此处用均值容差近似，并记录 repetition）
"""

from __future__ import annotations

import math

from .models import (
    PrimitiveOutput,
    QualityAlgorithmSpec,
    ReproductionComparison,
)


def _numeric_metrics(metrics: dict) -> dict[str, float]:
    """提取数值型指标。"""
    return {
        k: float(v) for k, v in metrics.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def compare_outputs(
    spec: QualityAlgorithmSpec,
    ref: PrimitiveOutput,
    native: PrimitiveOutput,
    *,
    floating_tolerance: float = 1e-9,
    metrics_whitelist: set[str] | None = None,
) -> list[ReproductionComparison]:
    """按 spec.equivalence_rule 比较 reference 与 native 输出。

    floating/stochastic：仅比较 reference 与 native 共同计算的数值指标
    （交集），native 特有指标（如 native_ks_statistic）不参与，避免
    因 reference 未定义该量而误判。可用 metrics_whitelist 进一步限定。

    Returns: ReproductionComparison 列表；passed 全 True 表示复现等价。
    """
    rule = spec.equivalence_rule
    comparisons: list[ReproductionComparison] = []

    if rule == "deterministic":
        # §15.1：canonical output 完全相等
        same = ref.output_hash() == native.output_hash()
        comparisons.append(
            ReproductionComparison(
                passed=same,
                metric="output_hash",
                reference_value=0.0,
                native_value=0.0,
                detail={
                    "ref_hash": ref.output_hash(),
                    "native_hash": native.output_hash(),
                    "equal": same,
                },
            )
        )
        return comparisons

    if rule in ("floating", "stochastic"):
        # §15.2/15.3：仅比较共同指标，且在容差内一致
        ref_m = _numeric_metrics(ref.metrics)
        nat_m = _numeric_metrics(native.metrics)
        shared = set(ref_m) & set(nat_m)
        if metrics_whitelist is not None:
            shared &= metrics_whitelist
        tol = floating_tolerance
        for k in sorted(shared):
            rv = ref_m[k]
            nv = nat_m[k]
            diff = abs(rv - nv)
            # 绝对容差 或 相对容差（对量级/计数指标更稳健）
            rel = tol * max(1.0, abs(rv), abs(nv))
            passed = diff <= max(tol, rel)
            comparisons.append(
                ReproductionComparison(
                    passed=passed,
                    metric=k,
                    reference_value=rv,
                    native_value=nv,
                    tolerance=tol,
                    detail={"abs_diff": diff, "rel_tolerance": rel},
                )
            )
        return comparisons

    raise ValueError(f"未知等价规则: {rule!r}")
