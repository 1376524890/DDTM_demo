"""VALOR Adapters —— 数据集/训练器适配层（P1）。

把 MNIST、CNN、torch DataLoader 等细节从交易机制中隔离，VALOR 估值层只消费
PredictionArtifact（y_true / y_pred / probability / training_metadata）。
"""

from __future__ import annotations

from .base import (
    DatasetAdapter,
    DatasetManifest,
    PredictionArtifact,
    RoleSplit,
    TrainerAdapter,
)
from .mnist import MNISTDatasetAdapter, MNISTTrainerAdapter

__all__ = [
    "DatasetAdapter",
    "DatasetManifest",
    "PredictionArtifact",
    "RoleSplit",
    "TrainerAdapter",
    "MNISTDatasetAdapter",
    "MNISTTrainerAdapter",
]
