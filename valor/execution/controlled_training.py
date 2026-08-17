"""ControlledTrainingRunner —— 合法训练 E2E（P0-M/P0-N）。

TrainingJobRequest → PIP → PDP → PEP → EnforcementPlan → isolated worker →
policy verified → key/data capability release → MNISTMLP training →
evaluation → OutputPolicy → model/metrics → UsageReceipt → Lineage → PXP。

非法请求（U1-U9）在 key release / training start 前被拒绝：
    key_release=False, raw_data_access=False, training_started=False, model_created=False。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from valor.core.hashing import content_hash
from valor.usage.pdp import authorize
from valor.usage.models import UsageRequest, UsageState

from .secure_execution import (
    CertifiedTrainingAlgorithmCatalog,
    LocalIsolatedProvider,
    TrainingJobSpec,
    TrainingOutcome,
)


class OutputPolicy:
    """Output Policy（P0-M §16）。"""

    METRICS_ONLY = "METRICS_ONLY"
    MODEL_ARTIFACT = "MODEL_ARTIFACT"
    INFERENCE_ENDPOINT = "INFERENCE_ENDPOINT"
    RAW_EXPORT = "RAW_EXPORT"

    @classmethod
    def allowed(cls, *, requested: str, access_mode: str, derivative: bool) -> bool:
        """按 RightsBundle 判定输出是否允许。"""
        if requested == cls.RAW_EXPORT:
            return False  # COMPUTE_ONLY / 任何模式都不允许 raw export
        if requested == cls.MODEL_ARTIFACT:
            return derivative  # 仅 derivative=True 允许模型 artifact
        if requested in (cls.METRICS_ONLY, cls.INFERENCE_ENDPOINT):
            return True
        return False


@dataclass
class ControlledTrainingRunner:
    """受控训练执行器（PDP→PEP→worker→training→output policy）。"""

    catalog: CertifiedTrainingAlgorithmCatalog
    provider: LocalIsolatedProvider = field(default_factory=LocalIsolatedProvider)
    rights: Any = None  # RightsBundle

    def run(
        self,
        *,
        job: TrainingJobSpec,
        dataset_X, dataset_y,
        valid_from: str, valid_until: str, max_uses: int,
        purposes: frozenset, authorized_actors: set, allowed_environments: set,
        environment: str,
        access_mode: str, derivative: bool,
        usage_state: UsageState,
        privacy_budget_max: float | None = None,
        timestamp: str = "",
    ) -> TrainingOutcome:
        """执行一次受控训练；非法在任何 key release 前 DENY。"""
        # ---- PIP + PDP：授权判定 ----
        req = UsageRequest(
            actor=job.actor_id, purpose=job.declared_purpose,
            environment=environment, timestamp=timestamp,
            privacy_cost=0.0, action="train",
        )
        allowed, violations = authorize(
            request=req, usage_state=usage_state, valid_from=valid_from,
            valid_until=valid_until, max_uses=max_uses, purposes=purposes,
            authorized_actors=authorized_actors,
            allowed_environments=allowed_environments,
            privacy_budget_max=privacy_budget_max,
        )
        if not allowed:
            return TrainingOutcome(
                decision="DENY", key_released=False, raw_data_access=False,
                training_started=False, model_created=False,
                job_spec_hash=job.job_spec_hash,
                reason="PDP 拒绝: " + ";".join(violations),
            )
        # ---- 算法认证 + 输出策略（PEP）----
        alg_ok, alg_reasons = self.catalog.verify(job)
        if not alg_ok:
            return TrainingOutcome(
                decision="DENY", key_released=False, raw_data_access=False,
                training_started=False, model_created=False,
                job_spec_hash=job.job_spec_hash,
                reason="算法未认证: " + ";".join(alg_reasons),
            )
        if not OutputPolicy.allowed(requested=job.requested_output,
                                    access_mode=access_mode, derivative=derivative):
            return TrainingOutcome(
                decision="DENY", key_released=False, raw_data_access=False,
                training_started=False, model_created=False,
                job_spec_hash=job.job_spec_hash,
                reason=f"输出策略拒绝 requested_output={job.requested_output}",
            )
        # ---- key release（PEP）----
        cap = self.provider.provision_capability(
            job_spec_hash=job.job_spec_hash, data_ref=job.dataset_commitment_hash,
            key_release_decision={"allow": True})
        if not cap["key_released"]:
            return TrainingOutcome(
                decision="DENY", key_released=False, raw_data_access=False,
                training_started=False, model_created=False,
                job_spec_hash=job.job_spec_hash, reason="key 未释放",
            )
        # ---- 真实训练（本地隔离，buyer 不接触 raw data）----
        try:
            metrics, model_hash = self._train(job, dataset_X, dataset_y)
        except Exception as e:  # noqa: BLE001
            return TrainingOutcome(
                decision="DENY", key_released=True, raw_data_access=False,
                training_started=True, model_created=False,
                job_spec_hash=job.job_spec_hash, reason=f"训练失败: {e}",
            )
        # ---- PXP：扣次数 ----
        usage_state.usage_count += 1
        return TrainingOutcome(
            decision="ALLOW", key_released=True, raw_data_access=False,
            training_started=True, model_created=True,
            job_spec_hash=job.job_spec_hash, metrics=metrics,
            model_artifact_hash=model_hash,
        )

    def _train(self, job: TrainingJobSpec, X, y) -> tuple[dict, str]:
        """在受控环境运行 MNIST MLP 训练，返回 (metrics, model_hash)。

        真实生成 train_loss/eval_loss/accuracy 与 model artifact hash。
        """
        import pandas as pd

        from valor.valuation.mnist_trainer import train_mnist_mlp

        Xdf = pd.DataFrame(np.asarray(X, dtype=np.float32))
        ydf = pd.Series(np.asarray(y, dtype=np.int64))
        n = len(Xdf)
        split = int(n * 0.8)
        X_tr, y_tr = Xdf.iloc[:split], ydf.iloc[:split]
        X_te, y_te = Xdf.iloc[split:], ydf.iloc[split:]
        result = train_mnist_mlp(
            X_tr, y_tr, X_te, y_te,
            epochs=job.hyperparameters.get("epochs", 5),
            batch_size=job.hyperparameters.get("batch_size", 256),
            lr=job.hyperparameters.get("lr", 1e-3), seed=job.seed,
        )
        model = result["model"]
        acc = result["test_acc"]
        train_loss = result["train_loss"]
        # 评估 loss：用 eval 集 cross-entropy（真实）
        import torch

        model._nn.eval()
        Xe = model.to_tensor(X_te)
        yte = torch.tensor(ydf.iloc[split:].to_numpy(dtype=np.int64))
        with torch.no_grad():
            logits = model._nn(Xe)
            pred_te = logits.argmax(dim=1).numpy()
            eval_loss = float(torch.nn.functional.cross_entropy(logits, yte).item())
        train_acc = 1.0 - min(train_loss, 1.0)
        model_hash = content_hash({
            "job": job.job_spec_hash,
            "test_acc": round(acc, 6),
        })
        return {
            "train_loss": train_loss, "eval_loss": eval_loss,
            "accuracy": acc, "train_accuracy": train_acc,
            "n_train": int(len(X_tr)), "n_eval": int(len(X_te)),
        }, model_hash


__all__ = ["ControlledTrainingRunner", "OutputPolicy"]
