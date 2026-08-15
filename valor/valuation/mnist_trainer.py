"""MNIST 训练器（Phase：真实 MNIST 交易的数据/估值支撑）。

用 torch 小 MLP 在本地下载的真实 MNIST（784 特征，data/raw/mnist/）上训练，
返回模型与测试准确率。作为 MNIST 场景下 Data-VOI/Oracle 的估值模型基础。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class MNISTMLP:
    """小型多层感知机（784→128→64→10）。"""

    def __init__(self, hidden1: int = 128, hidden2: int = 64, seed: int = 0) -> None:
        import torch
        import torch.nn as nn

        self._nn = nn.Sequential(
            nn.Linear(784, hidden1), nn.ReLU(),
            nn.Linear(hidden1, hidden2), nn.ReLU(),
            nn.Linear(hidden2, 10),
        )
        self._torch = torch
        self._nn.eval()

    def to_tensor(self, X) -> "torch.Tensor":
        return self._torch.tensor(np.asarray(X, dtype=np.float32) / 255.0)


def train_mnist_mlp(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    *,
    epochs: int = 5,
    batch_size: int = 256,
    lr: float = 1e-3,
    seed: int = 0,
    max_samples: int | None = None,
) -> dict:
    """在 MNIST 上训练 MLP，返回 {model, test_acc, train_loss}。

    Args:
        max_samples: 若给出，只取前 N 样本（快速跑通用）。
    """
    import torch
    import torch.nn as nn

    if max_samples is not None:
        X_train = X_train.iloc[:max_samples]
        y_train = y_train.iloc[:max_samples]

    torch.manual_seed(seed)
    model = MNISTMLP(seed=seed)
    opt = torch.optim.Adam(model._nn.parameters(), lr=lr)
    loss_fn = nn.CrossEntropyLoss()

    Xt = model.to_tensor(X_train)
    yt = torch.tensor(y_train.to_numpy(dtype=np.int64))
    n = len(Xt)
    for epoch in range(epochs):
        model._nn.train()
        perm = torch.randperm(n)
        total_loss = 0.0
        steps = 0
        for i in range(0, n, batch_size):
            idx = perm[i:i + batch_size]
            opt.zero_grad()
            out = model._nn(Xt[idx])
            loss = loss_fn(out, yt[idx])
            loss.backward()
            opt.step()
            total_loss += loss.item()
            steps += 1
        model._nn.eval()

    # 测试准确率
    Xe = model.to_tensor(X_test)
    with torch.no_grad():
        preds = model._nn(Xe).argmax(dim=1).numpy()
    acc = float(np.mean(preds == y_test.to_numpy()))
    return {"model": model, "test_acc": acc,
            "train_loss": total_loss / max(steps, 1)}
