"""MNIST DatasetAdapter + TrainerAdapter（P1）。

DatasetAdapter：加载本地真实 MNIST（data/raw/mnist/），五角色划分。
TrainerAdapter：小 MLP（784→128→64→10）确定性训练，产出 PredictionArtifact。

论文核心是数据交易机制，不是 MNIST SOTA：用小型稳定、确定性较强的网络，
CPU 可跑，大量重复实验可承受。
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import (
    DatasetAdapter,
    DatasetManifest,
    PredictionArtifact,
    RoleSplit,
    TrainerAdapter,
)


class MNISTDatasetAdapter(DatasetAdapter):
    """本地真实 MNIST 数据集适配器。"""

    name = "mnist"

    def load(self) -> tuple[pd.DataFrame, pd.Series]:
        from valor.data.download import load_dataset

        handle = load_dataset("mnist")
        return handle.X, handle.y

    def split(
        self,
        *,
        seed: int,
        historical_frac: float,
        buyer_base_frac: float,
        seller_candidate_frac: float,
        transaction_eval_frac: float,
    ) -> RoleSplit:
        X, y = self.load()
        n = len(X)
        total = historical_frac + buyer_base_frac + seller_candidate_frac + transaction_eval_frac
        if total >= 1.0:
            raise ValueError("前四角色比例之和必须 < 1（为 FinalEvaluation 留样本）")
        for f in (historical_frac, buyer_base_frac, seller_candidate_frac, transaction_eval_frac):
            if not (0 <= f <= 1):
                raise ValueError("角色比例必须在 [0,1]")

        rng = np.random.default_rng(seed)
        idx = rng.permutation(n)

        def take(frac: float, start: int):
            m = int(round(frac * n))
            return idx[start:start + m], start + m

        hist, p = take(historical_frac, 0)
        base, p = take(buyer_base_frac, p)
        cand, p = take(seller_candidate_frac, p)
        teval, p = take(transaction_eval_frac, p)
        final = idx[p:]

        return RoleSplit(
            historical_idx=hist,
            buyer_base_idx=base,
            seller_candidate_idx=cand,
            transaction_eval_idx=teval,
            final_evaluation_idx=final,
        )

    def manifest(self, split: RoleSplit, seed: int) -> DatasetManifest:
        X, y = self.load()
        return DatasetManifest(
            name=self.name,
            version="official-784",
            n_samples=len(X),
            n_features=X.shape[1],
            classes=[int(c) for c in sorted(y.unique())],
            role_counts=split.counts(),
            split_seed=seed,
        )


class MNISTTrainerAdapter(TrainerAdapter):
    """小 MLP 训练器（784→128→64→10）。"""

    def __init__(
        self,
        *,
        epochs: int = 5,
        batch_size: int = 256,
        lr: float = 1e-3,
        hidden1: int = 128,
        hidden2: int = 64,
    ) -> None:
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.hidden1 = hidden1
        self.hidden2 = hidden2

    def fit_predict(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_eval: pd.DataFrame,
        y_eval: pd.Series,
        *,
        seed: int,
    ) -> PredictionArtifact:
        import torch
        import torch.nn as nn

        from valor.valuation.mnist_trainer import MNISTMLP

        torch.manual_seed(seed)
        model = MNISTMLP(hidden1=self.hidden1, hidden2=self.hidden2, seed=seed)
        opt = torch.optim.Adam(model._nn.parameters(), lr=self.lr)
        loss_fn = nn.CrossEntropyLoss()

        Xt = model.to_tensor(X_train)
        yt = torch.tensor(y_train.to_numpy(dtype=np.int64))
        n = len(Xt)
        train_loss = 0.0
        steps = 0
        for _ in range(self.epochs):
            model._nn.train()
            perm = torch.randperm(n)
            for i in range(0, n, self.batch_size):
                idx = perm[i:i + self.batch_size]
                opt.zero_grad()
                out = model._nn(Xt[idx])
                loss = loss_fn(out, yt[idx])
                loss.backward()
                opt.step()
                train_loss += loss.item()
                steps += 1
        model._nn.eval()

        Xe = model.to_tensor(X_eval)
        with torch.no_grad():
            logits = model._nn(Xe)
        prob = torch.softmax(logits, dim=1).numpy()
        y_pred = prob.argmax(axis=1)

        classes = [int(c) for c in sorted(y_eval.unique())]
        return PredictionArtifact(
            y_true=y_eval.to_numpy(dtype=np.int64),
            y_pred=y_pred.astype(np.int64),
            probability=prob,
            classes=classes,
            training_metadata={
                "trainer": "MNISTMLP",
                "epochs": self.epochs,
                "batch_size": self.batch_size,
                "lr": self.lr,
                "hidden1": self.hidden1,
                "hidden2": self.hidden2,
                "n_train": len(X_train),
                "n_eval": len(X_eval),
                "train_loss": train_loss / max(steps, 1),
                "seed": seed,
            },
        )

    def trainer_manifest(self) -> dict[str, Any]:
        return {
            "trainer": "MNISTMLP",
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "lr": self.lr,
            "hidden1": self.hidden1,
            "hidden2": self.hidden2,
        }


__all__ = ["MNISTDatasetAdapter", "MNISTTrainerAdapter"]
