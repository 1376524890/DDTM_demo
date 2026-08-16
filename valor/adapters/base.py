"""DatasetAdapter / TrainerAdapter / PredictionArtifact 抽象（P1）。

对齐交接文档第三节：交易编排层不应知道 CNN/784 维/torch DataLoader 等细节。
VALOR 估值/交易层永远只消费：

    y_true  y_pred  probability  training_metadata

不关心训练器究竟是 LogisticRegression / MLP / CNN / ResNet。以后换 CIFAR-10、
Fashion-MNIST 只需新写一个 adapter，机制不动。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PredictionArtifact:
    """估值层唯一消费的预测产物。"""

    y_true: np.ndarray
    y_pred: np.ndarray
    probability: np.ndarray | None  # shape (n, n_classes) 或 None
    classes: list[Any]
    training_metadata: dict[str, Any] = field(default_factory=dict)

    def to_plain(self) -> dict[str, Any]:
        return {
            "y_true": self.y_true.tolist(),
            "y_pred": self.y_pred.tolist(),
            "probability": None if self.probability is None else self.probability.tolist(),
            "classes": [int(c) if isinstance(c, np.integer) else c for c in self.classes],
            "training_metadata": self.training_metadata,
        }


@dataclass(frozen=True)
class DatasetManifest:
    """数据集冻结清单（可哈希，入 RunManifest.dataset_hash）。"""

    name: str
    version: str
    n_samples: int
    n_features: int
    classes: list[Any]
    role_counts: dict[str, int]
    split_seed: int

    def to_plain(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "n_samples": self.n_samples,
            "n_features": self.n_features,
            "classes": self.classes,
            "role_counts": self.role_counts,
            "split_seed": self.split_seed,
        }


@dataclass(frozen=True)
class RoleSplit:
    """五角色数据划分（交接文档第四节）。

    Historical Calibration Pool / Buyer Base D_base / Seller Candidate D /
    Transaction Evaluation / FinalEvaluation —— 五角色互不相交。

    FinalEvaluation 绝不能进入估值、Audit-VOI、定价和交易决策。
    """

    historical_idx: np.ndarray
    buyer_base_idx: np.ndarray
    seller_candidate_idx: np.ndarray
    transaction_eval_idx: np.ndarray
    final_evaluation_idx: np.ndarray

    def __post_init__(self) -> None:
        self._assert_disjoint()

    def _assert_disjoint(self) -> None:
        sets = {
            "historical": set(map(int, self.historical_idx)),
            "buyer_base": set(map(int, self.buyer_base_idx)),
            "seller_candidate": set(map(int, self.seller_candidate_idx)),
            "transaction_eval": set(map(int, self.transaction_eval_idx)),
            "final_evaluation": set(map(int, self.final_evaluation_idx)),
        }
        names = list(sets)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                inter = sets[names[i]] & sets[names[j]]
                if inter:
                    raise ValueError(
                        f"角色 {names[i]} 与 {names[j]} 重叠 {len(inter)} 行（五角色互斥违反）"
                    )

    def frame(self, df: pd.DataFrame, idx: np.ndarray) -> pd.DataFrame:
        return df.iloc[np.sort(idx)].reset_index(drop=True)

    def counts(self) -> dict[str, int]:
        return {
            "historical": len(self.historical_idx),
            "buyer_base": len(self.buyer_base_idx),
            "seller_candidate": len(self.seller_candidate_idx),
            "transaction_eval": len(self.transaction_eval_idx),
            "final_evaluation": len(self.final_evaluation_idx),
        }


class DatasetAdapter(ABC):
    """数据集适配器抽象。"""

    name: str = ""

    @abstractmethod
    def load(self) -> tuple[pd.DataFrame, pd.Series]:
        """加载全量数据，返回 (X, y)。"""

    @abstractmethod
    def split(
        self,
        *,
        seed: int,
        historical_frac: float,
        buyer_base_frac: float,
        seller_candidate_frac: float,
        transaction_eval_frac: float,
    ) -> RoleSplit:
        """五角色划分；FinalEvaluation 取剩余。"""

    @abstractmethod
    def manifest(self, split: RoleSplit, seed: int) -> DatasetManifest:
        """冻结数据集清单。"""


class TrainerAdapter(ABC):
    """训练器适配器抽象。估值层只消费 PredictionArtifact。"""

    @abstractmethod
    def fit_predict(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_eval: pd.DataFrame,
        y_eval: pd.Series,
        *,
        seed: int,
    ) -> PredictionArtifact:
        """训练并在 eval 上预测，返回 PredictionArtifact。"""

    @abstractmethod
    def trainer_manifest(self) -> dict[str, Any]:
        """训练器冻结清单（trainer_hash 输入）。"""
