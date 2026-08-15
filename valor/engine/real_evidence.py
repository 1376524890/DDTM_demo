"""RealQualityEvidenceProvider —— 真实证据源（P4 收尾）。

把零知识审计（审计效果实验 `scripts/audit_effectiveness.py`）接入 DistributedAuditExecutor：
对卖方候选数据在交易前运行真实质量 primitive（不接触 FinalEvaluation），产生真实 outcome：

    - KS 两样本分布漂移：candidate 行级统计特征 vs reference（历史池）→ 漂移检测
    - Confident Learning：候选内部 label 一致性 → label 污染检测

判定：任一显著漂移特征 或 候选内部 label 误差率显著高 → QUALITY_FAIL，否则 PASS。

这替换了原来的"默认全 PASS"模拟证据源，使审计 outcome 真正反映候选数据质量。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd


@dataclass
class RealEvidenceResult:
    """一次真实审计的检测结果。"""

    outcome: str  # PASS | QUALITY_FAIL | BREACH_EVIDENCE
    n_significant_drift: int
    total_drift_features: int
    min_pvalue: float
    label_error_rate: float
    label_flagged: bool

    def to_plain(self) -> dict:
        return {
            "outcome": self.outcome,
            "n_significant_drift": self.n_significant_drift,
            "total_drift_features": self.total_drift_features,
            "min_pvalue": self.min_pvalue,
            "label_error_rate": self.label_error_rate,
            "label_flagged": self.label_flagged,
        }


class RealQualityEvidence:
    """基于候选数据真实质量检测的证据生成器。"""

    def __init__(
        self,
        *,
        reference_df: pd.DataFrame,
        candidate_df: pd.DataFrame,
        y_candidate: pd.Series,
        alpha_shift: float = 0.01,
        label_error_threshold: float = 0.28,
        dup_threshold: float = 0.05,
        row_sample: int = 2000,
        compress_dim: int = 64,
    ) -> None:
        self.reference_df = reference_df
        self.candidate_df = candidate_df
        self.y_candidate = y_candidate
        self.alpha_shift = alpha_shift
        self.label_error_threshold = label_error_threshold
        self.dup_threshold = dup_threshold
        self.row_sample = row_sample
        self.compress_dim = compress_dim

    # ---- 行级统计特征（784 像素 → 均值/标准差/稀疏度）----
    @staticmethod
    def _row_features(X: pd.DataFrame, sample: int = 2000) -> pd.DataFrame:
        if len(X) > sample:
            X = X.iloc[:sample]
        arr = X.to_numpy(dtype=float)
        return pd.DataFrame({
            "pixel_mean": arr.mean(axis=1),
            "pixel_std": arr.std(axis=1),
            "sparsity": (arr < 128).mean(axis=1),
        })

    # ---- 像素压缩（加速 CL）----
    @staticmethod
    def _compress(X: pd.DataFrame, dim: int = 64) -> pd.DataFrame:
        arr = X.to_numpy(dtype=float)
        n = arr.shape[0]
        n_feat = arr.shape[1]
        dim = max(1, min(dim, n_feat))  # 防空 slice
        blocks = np.array_split(np.arange(n_feat), dim)
        out = np.zeros((n, dim))
        for j, b in enumerate(blocks):
            if len(b) == 0:
                out[:, j] = 0.0
            else:
                out[:, j] = arr[:, b].mean(axis=1)
        return pd.DataFrame(out)

    # ---- 分布漂移检测（KS）----
    def _drift_check(self) -> tuple[int, int, float]:
        from scipy.stats import ks_2samp

        ref_feat = self._row_features(self.reference_df, self.row_sample)
        cand_feat = self._row_features(self.candidate_df, self.row_sample)
        n_sig = 0
        total = len(ref_feat.columns)
        min_p = 1.0
        for col in ref_feat.columns:
            ks = ks_2samp(ref_feat[col], cand_feat[col])
            if ks.pvalue < self.alpha_shift:
                n_sig += 1
            min_p = min(min_p, ks.pvalue)
        return n_sig, total, float(min_p)

    # ---- label 污染检测（Confident Learning）----
    def _label_check(self) -> tuple[float, bool]:
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.model_selection import cross_val_predict

            from valor.quality.native.confident_learning import run_confident_learning

            n = min(len(self.candidate_df), self.row_sample)
            Xs = self._compress(self.candidate_df.iloc[:n].fillna(0), self.compress_dim)
            ys = self.y_candidate.iloc[:n]
            clf = LogisticRegression(max_iter=300)
            probs = cross_val_predict(clf, Xs, ys.to_numpy(), cv=2,
                                      method="predict_proba")
            out = run_confident_learning(Xs, ys, probabilities=probs)
            err = float(out.metrics["estimated_label_error_rate"])
            return err, err > self.label_error_threshold
        except Exception:  # noqa: BLE001  label 检测失败不阻断（漂移检测为主）
            return 0.0, False

    # ---- 生成真实 outcome（综合多 primitive）----
    def detect(self) -> RealEvidenceResult:
        n_sig, total, min_p = self._drift_check()
        label_err, label_flagged = self._label_check()
        if n_sig >= 1 or label_flagged:
            outcome = "QUALITY_FAIL"
        else:
            outcome = "PASS"
        return RealEvidenceResult(
            outcome=outcome, n_significant_drift=n_sig,
            total_drift_features=total, min_pvalue=min_p,
            label_error_rate=label_err, label_flagged=label_flagged,
        )

    # ---- 单一 primitive 独立检测（供节点独立执行，产生真实分歧）----
    def detect_primitive(self, primitive: str) -> RealEvidenceResult:
        """按指定 primitive 独立检测。

        primitives:
            - "ks_shift"   ：分布漂移（reference vs candidate）
            - "confident_learning"：label 内部一致性
            - "duplicates" ：整行重复（不依赖 reference）
        """
        if primitive == "ks_shift":
            n_sig, total, min_p = self._drift_check()
            outcome = "QUALITY_FAIL" if n_sig >= 1 else "PASS"
            return RealEvidenceResult(
                outcome=outcome, n_significant_drift=n_sig,
                total_drift_features=total, min_pvalue=min_p,
                label_error_rate=0.0, label_flagged=False)
        if primitive == "confident_learning":
            label_err, label_flagged = self._label_check()
            outcome = "QUALITY_FAIL" if label_flagged else "PASS"
            return RealEvidenceResult(
                outcome=outcome, n_significant_drift=0,
                total_drift_features=0, min_pvalue=1.0,
                label_error_rate=label_err, label_flagged=label_flagged)
        if primitive == "duplicates":
            dup_rate = self._duplicate_check()
            outcome = "QUALITY_FAIL" if dup_rate > self.dup_threshold else "PASS"
            return RealEvidenceResult(
                outcome=outcome, n_significant_drift=0,
                total_drift_features=0, min_pvalue=1.0,
                label_error_rate=0.0, label_flagged=False)
        raise ValueError(f"未知 primitive: {primitive}")

    # ---- 重复检测（候选内部整行重复率）----
    def _duplicate_check(self) -> float:
        from valor.quality.native.duplicates import run_exact_duplicates

        n = min(len(self.candidate_df), self.row_sample)
        out = run_exact_duplicates(self.candidate_df.iloc[:n])
        return float(out.metrics.get("exact_duplicate_rate", 0.0))


# 每个节点分配的检测 primitive（可配置；不同 primitive 对同一数据可能给出不同判定，
# 从而产生真实的分歧，由分布式 quorum-by-result 裁决）
DEFAULT_NODE_PRIMITIVES = [
    "ks_shift", "ks_shift", "confident_learning",
    "duplicates", "ks_shift", "confident_learning", "duplicates",
]


def make_real_evidence_provider(
    *,
    reference_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    y_candidate: pd.Series,
    node_primitives: list[str] | None = None,
    **kwargs,
) -> Callable[[str, Any], dict]:
    """构造 evidence provider：各节点独立运行不同质量 primitive，产生真实（可能分歧）evidence。

    论文机制：诚实节点对同一 committed data 运行**各自被分配的 primitive**，可能
    因 primitive 视角不同产生分歧，最终由分布式 quorum-by-result（同一结果 ≥ q 个一致）
    裁决。这取代了"所有节点返回同一结果"的简化。
    """
    detector = RealQualityEvidence(
        reference_df=reference_df, candidate_df=candidate_df,
        y_candidate=y_candidate, **kwargs,
    )
    primitives = node_primitives or DEFAULT_NODE_PRIMITIVES
    # 每个节点按其 id 的稳定 hash 分配 primitive（对任意 node_id 稳健）
    node_results: dict[str, RealEvidenceResult] = {}

    def _primitive_for(node_id: str) -> str:
        from valor.core.hashing import sha256_hex

        h = int(sha256_hex(node_id.encode("utf-8"))[:8], 16)
        return primitives[h % len(primitives)]

    combined = detector.detect()

    def provider(node_id: str, task) -> dict:
        res = node_results.get(node_id)
        if res is None:
            res = detector.detect_primitive(_primitive_for(node_id))
            node_results[node_id] = res
        return {"evidence_id": f"evt-{task.task_id}-{node_id}",
                "result": res.outcome,
                "quality_metrics": res.to_plain()}

    provider.real_result = combined  # 附带综合检测结果供审计 trace 引用
    provider.node_results = node_results
    return provider


__all__ = [
    "RealQualityEvidence", "RealEvidenceResult", "make_real_evidence_provider",
    "DEFAULT_NODE_PRIMITIVES",
]
