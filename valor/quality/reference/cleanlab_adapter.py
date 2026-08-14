"""Cleanlab reference（规范 §10 / §72）。

调用锁定版本 cleanlab 计算 confident joint 与 label issues，作为
NativeConfidentLearning 的 reference。两个实现不需内部代码相同，但须在相同
OOF probabilities 下输出等价（confident joint 一致或版本语义等价、issue
ranking 一致性可计算、注入噪声上 TP/FP/FN/TN）。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..models import PrimitiveOutput


class CleanlabReferenceAdapter:
    """锁定版本 cleanlab 参考实现。"""

    def run_confident_learning(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        probabilities: np.ndarray,
        model_spec_hash: str = "",
    ) -> PrimitiveOutput:
        import cleanlab
        from cleanlab.count import compute_confident_joint
        from cleanlab.filter import find_label_issues

        labels = y.to_numpy().astype(int)
        probs = np.asarray(probabilities, dtype=float)
        # cleanlab>=2.x：compute_confident_joint(labels, pred_probs)
        joint = compute_confident_joint(labels, probs)
        total = int(joint.sum())
        estimated_error_rate = (
            float((joint.sum() - np.trace(joint))) / total if total else 0.0
        )
        issues = find_label_issues(
            labels, probs, return_indices_ranked_by="self_confidence"
        )
        metrics = {
            "n_samples": int(len(labels)),
            "estimated_label_error_rate": estimated_error_rate,
            "n_issues": int(len(issues)),
            "issue_rate": len(issues) / len(labels) if len(labels) else 0.0,
        }
        return PrimitiveOutput(
            algorithm_id="confident_learning_reference",
            metrics=metrics,
            detail={
                "cleanlab_version": cleanlab.__version__,
                "confident_joint": joint.tolist(),
                "issue_indices": list(issues),
                "model_spec_hash": model_spec_hash,
            },
        )
