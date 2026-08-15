"""P1 MNIST adapter 集成测试（小规模快速验证）。

完整 MNIST 五角色划分验证 + 小 MLP 训练产出 PredictionArtifact。
"""

from __future__ import annotations

import numpy as np

from valor.adapters import MNISTDatasetAdapter, MNISTTrainerAdapter
from valor.data.download import load_dataset


def test_mnist_role_split_five_way():
    ada = MNISTDatasetAdapter()
    split = ada.split(
        seed=0,
        historical_frac=0.25, buyer_base_frac=0.20,
        seller_candidate_frac=0.05, transaction_eval_frac=0.10,
    )
    counts = split.counts()
    X, y = ada.load()
    assert counts["historical"] + counts["buyer_base"] + counts["seller_candidate"] \
        + counts["transaction_eval"] + counts["final_evaluation"] == len(X)
    assert counts["final_evaluation"] > 0


def test_mnist_manifest_hashable():
    ada = MNISTDatasetAdapter()
    split = ada.split(seed=0, historical_frac=0.25, buyer_base_frac=0.20,
                      seller_candidate_frac=0.05, transaction_eval_frac=0.10)
    m = ada.manifest(split, seed=0)
    assert m.n_features == 784
    assert m.classes == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_mnist_trainer_small_prediction():
    """小规模训练跑通，产出 PredictionArtifact。"""
    ada = MNISTDatasetAdapter()
    X, y = ada.load()
    tr = MNISTTrainerAdapter(epochs=1)
    art = tr.fit_predict(
        X.iloc[:300], y.iloc[:300], X.iloc[::20], y.iloc[::20], seed=0,
    )
    assert art.y_pred.shape == art.y_true.shape
    assert art.probability is not None
    assert art.probability.shape[1] == 10
    assert set(np.unique(art.y_pred)).issubset(set(range(10)))
    assert "trainer" in tr.trainer_manifest()
